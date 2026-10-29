"""The shared export layer: an indicator's result in the container `output=` names.

With `output=None` (the default) the `_api` runners restore the input's own
container through `Prepared.restore` and never touch this module. Otherwise
`exporter` resolves the target once, before any work, and the runner calls the
returned function with the cased output names, the results in documented
order, and the input's pandas index (None when there is none).

Each target has one fixed shape, whatever the input was:

- `"list"`, `"tuple"`, `"numpy"`: one sequence for one output, a tuple of them
  for several; the index is dropped.
- `"pandas"`: a Series for one output, a DataFrame for several, with the
  index (a default `RangeIndex` when the input had none).
- `"dict"`: the index first (NumPy array of its values), then one NumPy array
  per output.
- `"json"`, `"json_bytes"`: an object of arrays, the index first, NaN as `null`.
- `"csv"`, `"csv_bytes"`: a header row, the index as the first column, NaN as
  an empty field, numbers in Python's shortest round-trip `repr`, `\\n` endings.

The index is named after its name, or `index` when unnamed; a MultiIndex gives
one field per level, named after the level or `level_<n>` (as pandas'
`reset_index` does). In JSON and CSV, dates become ISO 8601 strings: an index
whose values are all tz-naive midnights is written as dates (`2024-01-02`),
anything else as full timestamps (`2024-01-02T09:30:00`, with its offset when
tz-aware); missing values are `null` or an empty field. Other index values must
be numbers or strings.
"""

import datetime as dt
import importlib
import math
from collections.abc import Callable, Sequence
from typing import Any, Literal, cast, get_args

import numpy as np

from ._types import Float64Array
from ._validation import (
    RESTORE_ARRAY,
    RESTORE_LIST,
    RESTORE_TUPLE,
    csv_fields,
    csv_quote,
    csv_text,
    json_dump,
    nulls,
)

#: The containers `output=` converts a result to.
type Output = Literal[
    "list", "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv", "csv_bytes"
]

#: Every valid `output=` name, in documented order.
TARGETS: tuple[str, ...] = get_args(Output.__value__)

#: `export(names, results, index)`: the cased output names, the results in
#: documented order, and the input's pandas index or None.
type Export = Callable[[Sequence[str], Sequence[Float64Array], Any], Any]


def exporter(output: object) -> Export:
    """The export function for an `output=` name, checked before any work is done.

    Raises:
        ValueError: `output` is not one of `TARGETS`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    found = _EXPORTS.get(output) if isinstance(output, str) else None

    if found is None:
        raise ValueError(
            f"output must be None or one of {', '.join(map(repr, TARGETS))}; got {output!r}"
        )

    if found is _to_pandas:
        _pandas()

    return found


def _pandas() -> Any:
    """pandas, imported only when `output="pandas"` asks for it."""
    try:
        return importlib.import_module("pandas")
    except ImportError:  # also a `None` entry in `sys.modules`
        raise ModuleNotFoundError(
            "output='pandas' needs pandas, which is not installed; install PyTA's pandas "
            "extra (pip install 'pyta[pandas]') or choose another output",
            name="pandas",
        ) from None


# --- unnamed targets ------------------------------------------------------------------------


def _to_numpy(names: Sequence[str], results: Sequence[Float64Array], _index: Any) -> Any:
    return RESTORE_ARRAY(names, results)


def _to_list(names: Sequence[str], results: Sequence[Float64Array], _index: Any) -> Any:
    return RESTORE_LIST(names, results)


def _to_tuple(names: Sequence[str], results: Sequence[Float64Array], _index: Any) -> Any:
    return RESTORE_TUPLE(names, results)


# --- named targets --------------------------------------------------------------------------


def _to_pandas(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> Any:
    pd = _pandas()

    if len(results) == 1:
        return pd.Series(results[0], index=index, name=names[0])
    return pd.DataFrame(dict(zip(names, results, strict=True)), index=index)


def _index_fields(index: Any, names: Sequence[str]) -> list[tuple[str, Any]]:
    """The index as (name, values) fields placed before the outputs; empty without one.

    Raises:
        ValueError: An index name equals an output name or another level's name.
    """
    if index is None:
        return []

    if index.nlevels > 1:
        fields = [
            (f"level_{level}" if name is None else str(name), index.get_level_values(level))
            for level, name in enumerate(index.names)
        ]
    else:
        fields = [("index" if index.name is None else str(index.name), index)]

    taken = set(names)

    for name, _ in fields:
        if name in taken:
            raise ValueError(
                f"the input's index is named {name!r}, which is also an output or another "
                "index level's name; rename the index (for example with rename_axis) or use "
                "an output without names"
            )
        taken.add(name)

    return fields


def _to_dict(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> dict[str, Any]:
    out: dict[str, Any] = {name: values.to_numpy() for name, values in _index_fields(index, names)}
    out.update(zip(names, results, strict=True))
    return out


def _midnight(value: dt.datetime) -> bool:
    """True for a tz-naive datetime with no time of day (nanoseconds included)."""
    return (
        value.tzinfo is None
        and value.hour == value.minute == value.second == value.microsecond == 0
        and getattr(value, "nanosecond", 0) == 0
    )


def _plain(name: str, values: Any) -> list[object]:
    """Index values as JSON- and CSV-ready Python values (dates as ISO 8601, gaps as None).

    Raises:
        TypeError: A value that is not a number, string, date or datetime.
    """
    items: list[object] = list(values.tolist())
    dates_only = all(
        _midnight(item) for item in items if isinstance(item, dt.datetime) and item == item
    )
    plain: list[object] = []

    for position, value in enumerate(items):
        item = cast(object, value.item()) if isinstance(value, np.generic) else value

        if isinstance(item, dt.datetime):
            # NaT is a datetime that is not equal to itself.
            if item != item:
                plain.append(None)
            else:
                plain.append(item.date().isoformat() if dates_only else item.isoformat())
        elif isinstance(item, dt.date):
            plain.append(item.isoformat())
        elif isinstance(item, float):
            if math.isnan(item):
                plain.append(None)
            elif math.isinf(item):
                raise TypeError(
                    f"index {name!r} value {item!r} at position {position} cannot be written "
                    "to JSON or CSV; replace infinite index values first"
                )
            else:
                plain.append(item)
        elif item is None or isinstance(item, str | int):
            plain.append(item)
        else:
            raise TypeError(
                f"index {name!r} value {item!r} at position {position} ({type(item).__name__}) "
                "cannot be written to JSON or CSV; an index must hold numbers, strings, dates "
                "or datetimes. Convert it first (for example with reset_index) or use "
                "output='pandas' or 'dict'"
            )

    return plain


def _json_object(
    names: Sequence[str], results: Sequence[Float64Array], index: Any
) -> dict[str, Any]:
    out: dict[str, Any] = {
        name: _plain(name, values) for name, values in _index_fields(index, names)
    }
    out.update(zip(names, map(nulls, results), strict=True))
    return out


_DUMP_TEXT = json_dump(False)
_DUMP_BYTES = json_dump(True)


def _to_json(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> Any:
    return _DUMP_TEXT(_json_object(names, results, index))


def _to_json_bytes(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> Any:
    return _DUMP_BYTES(_json_object(names, results, index))


def _csv_value(item: object) -> str:
    """One index value as a CSV field: empty for a gap, shortest `repr` for a float."""
    if item is None:
        return ""
    if isinstance(item, float):
        return repr(item)
    return csv_quote(str(item))


def _to_csv(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> str:
    fields = _index_fields(index, names)
    header = [*(csv_quote(name) for name, _ in fields), *names]
    columns = [
        *([_csv_value(item) for item in _plain(name, values)] for name, values in fields),
        *map(csv_fields, results),
    ]
    return csv_text(header, columns)


def _to_csv_bytes(names: Sequence[str], results: Sequence[Float64Array], index: Any) -> bytes:
    return _to_csv(names, results, index).encode()


_EXPORTS: dict[str, Export] = {
    "list": _to_list,
    "tuple": _to_tuple,
    "numpy": _to_numpy,
    "pandas": _to_pandas,
    "dict": _to_dict,
    "json": _to_json,
    "json_bytes": _to_json_bytes,
    "csv": _to_csv,
    "csv_bytes": _to_csv_bytes,
}

assert tuple(_EXPORTS) == TARGETS, "every output target needs an export function"
