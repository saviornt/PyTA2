"""Input normalization for multi-column indicators.

Every supported container is reduced to one 1-D, C-contiguous float64 array
per slot of the indicator, in slot order, together with a function that
rebuilds the caller's container from the indicator's named results. Named
containers are matched by role; unnamed ones (2-D arrays, lists of rows or
columns, tuples of arrays, JSON arrays of arrays) use the slot order, and give a
tuple of outputs for a multi-output indicator. A list or tuple of pandas Series
is matched by name when every Series is named by a role, else taken in order.
CSV text (a header row, then one row per period) is matched by name like a dict.
"""

import functools
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from ._types import Float64Array, Prepared, PreparedColumns, Restore
from ._validation import (
    IGNORED,
    RESTORE_ARRAY,
    RESTORE_LIST,
    RESTORE_TUPLE,
    Slot,
    from_column,
    from_pandas_series,
    is_json,
    json_dump,
    read_csv,
    restore_columns,
    restore_csv,
    restore_frame,
    restore_json_array,
    restore_json_object,
    restore_records,
    restore_series,
    role_aliases,
    role_names,
    role_of,
    squash,
    to_float64,
)

_log = logging.getLogger("pyta.validation")

#: Pairs of roles (upper, lower) that must hold row by row when an indicator
#: uses both: a high below its low is a data error, not a market move.
ORDERED_ROLES: tuple[tuple[str, str], ...] = (("high", "low"),)


def validate_columns(columns: object) -> list[str] | None:
    """Returns `columns` as a list of names, or None.

    Raises:
        TypeError: `columns` is not a list or tuple of str.
    """
    if columns is None:
        return None

    if isinstance(columns, list | tuple):
        names = cast(Sequence[object], columns)

        if all(isinstance(name, str) for name in names):
            return [cast(str, name) for name in names]

    raise TypeError(
        f"columns must be a list of column names, got {type(columns).__name__}"
        if not isinstance(columns, list | tuple)
        else "columns must contain only str column names"
    )


def needs(label: str, slots: Sequence[Slot]) -> str:
    """What an indicator needs, for error messages: "cci needs high, low and close"."""
    described = [slot.describe() for slot in slots]
    listed = ", ".join(described[:-1]) + f" and {described[-1]}" if len(slots) > 1 else described[0]
    return f"{label} needs the columns {listed}"


def normalize_columns(
    data: object, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """Converts any supported container to one float64 series per slot.

    `columns` is the caller's explicit choice of names, in any order; when it
    is None, each slot takes the first column that has one of its roles.
    """
    if isinstance(data, str | bytes | bytearray):
        if is_json(data):
            return _from_json(data, columns, label, slots)
        return _from_csv(data, columns, label, slots)
    if isinstance(data, np.ndarray):
        return _from_array(cast(NDArray[Any], data), columns, label, slots)
    if isinstance(data, tuple):
        return _from_tuple(cast(tuple[object, ...], data), columns, label, slots)
    if isinstance(data, list):
        return _from_list(cast(list[object], data), columns, label, slots)
    if isinstance(data, Mapping):
        return _from_mapping(cast(Mapping[object, object], data), columns, label, slots)

    # pandas is only inspected if the caller has already imported it.
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(data, pd.DataFrame):
            return _from_pandas_frame(pd, data, columns, label, slots)
        if isinstance(data, pd.Series):
            raise _one_column(label, slots, "a pandas Series")

    raise TypeError(
        f"unsupported input type {type(data).__name__}; expected a pandas DataFrame, dict of "
        "columns, JSON or CSV text, 2-D NumPy array, list of rows or columns, or a list or tuple "
        "of arrays or Series"
    )


def _column(value: object, key: object) -> Prepared:
    """`from_column`, with no work for a column that is already a float64 array."""
    if (
        type(value) is np.ndarray
        and value.dtype == np.float64
        and value.ndim == 1
        and value.flags.c_contiguous
    ):
        return Prepared(cast(Float64Array, value), RESTORE_ARRAY)

    return from_column(value, key)


def _one_column(label: str, slots: Sequence[Slot], kind: str) -> TypeError:
    return TypeError(
        f"{needs(label, slots)}, but {kind} holds one series; pass a DataFrame, dict of "
        "columns, JSON, a 2-D array or list of rows, or a list or tuple of columns (arrays, "
        "lists or Series)"
    )


# --- matching names to slots ----------------------------------------------------------------


def _match(
    keys: Sequence[object], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> tuple[tuple[object, str], ...]:
    """Chooses one key per slot, in slot order, with the role it was matched as."""
    chosen = _matched(tuple(keys), None if columns is None else tuple(columns), label, tuple(slots))
    _log.debug("%s: using columns %r", label, [key for key, _ in chosen])
    return chosen


@functools.lru_cache(maxsize=256)
def _matched(
    keys: tuple[object, ...], columns: tuple[str, ...] | None, label: str, slots: tuple[Slot, ...]
) -> tuple[tuple[object, str], ...]:
    """`_match`, cached: the same column names come back on every call."""
    lookup: dict[str, object] = {}

    for key in keys:
        squashed = squash(key)

        # Only a name some role uses can be ambiguous; other columns are ignored.
        if squashed in lookup and role_of(key) is not None:
            raise ValueError(
                f"column names {lookup[squashed]!r} and {key!r} are the same "
                f"after ignoring {IGNORED}"
            )

        lookup.setdefault(squashed, key)

    available = _Available(keys)

    def find(role: str, wanted: str | None = None) -> object | None:
        candidates = role_aliases(role)
        if wanted is not None:
            candidates = (wanted, *candidates)
        return next((lookup[name] for name in candidates if name in lookup), None)

    if columns is None:
        chosen: list[tuple[object, str]] = []
        missing: list[Slot] = []

        for slot in slots:
            found = next(
                ((key, role) for role in slot.roles if (key := find(role)) is not None), None
            )
            if found is None:
                missing.append(slot)
            else:
                chosen.append(found)

        if missing:
            raise ValueError(
                f"{needs(label, slots)}; missing: {', '.join(s.describe() for s in missing)}. "
                f"Available columns: {available}. Rename the input's columns, or pass "
                "columns=[...] to choose them"
            )

        return tuple(chosen)

    return _match_explicit(columns, label, slots, find, available)


class _Available:
    """The input's column names for an error message, joined only when one is raised."""

    def __init__(self, keys: Sequence[object]) -> None:
        self.keys = keys

    def __str__(self) -> str:
        return ", ".join(repr(key) for key in self.keys) or "none"


def _match_explicit(
    columns: Sequence[str],
    label: str,
    slots: Sequence[Slot],
    find: Any,
    available: _Available,
) -> tuple[tuple[object, str], ...]:
    """Assigns each explicitly named column to the slot for its role."""
    filled: dict[str, tuple[str, object, str]] = {}  # slot name -> (name, key, role)

    for name in columns:
        role = role_of(name)

        if role is None:
            raise ValueError(
                f"column {name!r} is not a recognized column name; use one of "
                f"{', '.join(role_names())} (or an alias such as 'adjusted close'). "
                f"{needs(label, slots)}"
            )

        slot = next((slot for slot in slots if role in slot.roles), None)

        if slot is None:
            raise ValueError(
                f"column {name!r} ({role}) is not an input of {label}; {needs(label, slots)}"
            )

        if slot.name in filled:
            raise ValueError(
                f"columns {filled[slot.name][0]!r} and {name!r} both fill {label}'s "
                f"{slot.describe()} input; {needs(label, slots)}"
            )

        key = find(role, squash(name))

        if key is None:
            raise ValueError(f"column {name!r} not found; available columns: {available}")

        filled[slot.name] = (name, key, role)

    empty = [slot.describe() for slot in slots if slot.name not in filled]

    if empty:
        raise ValueError(f"{needs(label, slots)}; columns= leaves out: {', '.join(empty)}")

    return tuple((filled[slot.name][1], filled[slot.name][2]) for slot in slots)


def _prepared(
    values: Sequence[Float64Array],
    labels: Sequence[object],
    roles: Sequence[str],
    restore: Restore,
    named: bool = True,
    index: Any = None,
) -> PreparedColumns:
    """Checks the columns' lengths; `named` is False when `labels` are positions.

    `index` is the input's pandas index, or None.
    """
    lengths = {array.shape[0] for array in values}

    if len(lengths) > 1:
        sizes = ", ".join(
            f"{label!r}: {array.shape[0]}" for label, array in zip(labels, values, strict=True)
        )
        raise ValueError(f"columns have different lengths ({sizes})")

    text = tuple(map(str, labels))
    return PreparedColumns(tuple(values), text, tuple(roles), restore, text if named else (), index)


# --- containers -----------------------------------------------------------------------------


def _reject_columns(columns: list[str] | None, kind: str, slots: Sequence[Slot]) -> None:
    if columns is not None:
        order = ", ".join(slot.name for slot in slots)
        raise ValueError(
            f"columns= is not valid for {kind}, which has no column names; "
            f"its columns are taken in the order {order}"
        )


def _unnamed(
    arrays: Sequence[Float64Array], label: str, slots: Sequence[Slot], kind: str
) -> tuple[list[str], list[str]]:
    """Labels and roles for unnamed columns, which follow the slot order."""
    if len(arrays) != len(slots):
        order = ", ".join(slot.name for slot in slots)
        raise ValueError(
            f"{label} takes {len(slots)} columns in the order {order}; {kind} has {len(arrays)}"
        )

    return [f"column {i} ({slot.name})" for i, slot in enumerate(slots)], [
        slot.roles[0] for slot in slots
    ]


def _from_array(
    data: NDArray[Any], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if data.ndim == 1:
        raise _one_column(label, slots, "a 1-D array")
    if data.ndim != 2:
        raise ValueError(
            f"expected a 2-D array of shape (rows, columns) or (columns, rows), got shape "
            f"{data.shape}"
        )

    _reject_columns(columns, "a 2-D array", slots)

    if isinstance(data, np.ma.MaskedArray):
        data = np.ma.filled(data.astype(np.float64), np.nan)

    arrays = _split(data, label, slots, "a 2-D array")
    labels, roles = _unnamed(arrays, label, slots, "the array")

    return _prepared(arrays, labels, roles, RESTORE_ARRAY, named=False)


def _split(table: NDArray[Any], label: str, slots: Sequence[Slot], kind: str) -> list[Float64Array]:
    """The columns of a 2-D table in either layout, chosen by the indicator's column count.

    The axis whose length equals the count holds the columns; when both do (as
    many rows as columns), the layout is (rows, columns).
    """
    count = len(slots)
    rows, width = table.shape

    if width == count:
        return [to_float64(table[:, i]) for i in range(count)]
    if rows == count:
        return [to_float64(column) for column in table]

    order = ", ".join(slot.name for slot in slots)
    raise ValueError(
        f"{label} takes {count} columns in the order {order}; expected {kind} of shape "
        f"(rows, {count}) or ({count}, rows), got shape ({rows}, {width})"
    )


def _kinds(items: Sequence[object]) -> set[str]:
    """What a list or tuple holds: "series", "sequences" and/or "numbers"."""
    pd = sys.modules.get("pandas")
    kinds: set[str] = set()

    for item in items:
        if pd is not None and isinstance(item, pd.Series):
            kinds.add("series")
        elif isinstance(item, list | tuple) or (isinstance(item, np.ndarray) and item.ndim):
            kinds.add("sequences")
        else:
            kinds.add("numbers")

    return kinds


def _mixed(label: str, slots: Sequence[Slot], kind: str, kinds: set[str]) -> TypeError:
    described = {"series": "pandas Series", "sequences": "lists or arrays", "numbers": "numbers"}
    found = " and ".join(described[name] for name in described if name in kinds)
    return TypeError(
        f"{needs(label, slots)}, but {kind} mixes {found}; pass every column in the same form"
    )


def _from_tuple(
    data: tuple[object, ...], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if not data or not all(isinstance(item, list | tuple | np.ndarray) for item in data):
        # Only tuples that are not of arrays get here, so those pay nothing for this.
        kinds = _kinds(data)

        if kinds == {"series"}:
            return _from_series(data, columns, label, slots, "tuple")
        if len(kinds) > 1:
            raise _mixed(label, slots, "the tuple", kinds)
        raise _one_column(label, slots, "a tuple of numbers")

    _reject_columns(columns, "a tuple of arrays", slots)

    arrays = [_column(item, i).values for i, item in enumerate(data)]
    labels, roles = _unnamed(arrays, label, slots, "the tuple")

    return _prepared(arrays, labels, roles, RESTORE_TUPLE, named=False)


def _from_list(
    data: list[object], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """A list of rows or of columns (lists, tuples or arrays), or a list of Series."""
    kinds = _kinds(data)

    if kinds == {"series"}:
        return _from_series(data, columns, label, slots, "list")
    if kinds != {"sequences"}:
        if len(kinds) > 1:
            raise _mixed(label, slots, "the list", kinds)
        raise _one_column(label, slots, "a list of numbers")

    _reject_columns(columns, "a list of lists", slots)

    arrays = _nested(cast(list[Sequence[object]], data), label, slots, "a list of lists")
    labels, roles = _unnamed(arrays, label, slots, "the list")

    return _prepared(arrays, labels, roles, RESTORE_LIST, named=False)


def _nested(
    items: Sequence[Sequence[object]], label: str, slots: Sequence[Slot], kind: str
) -> list[Float64Array]:
    """The columns of nested sequences: rows, or columns, by `_split`'s rule.

    Columns of unequal length are returned as they are, for `_prepared` to name.
    """
    lengths = {len(item) for item in items}

    if len(lengths) > 1:
        if len(items) == len(slots):
            return [_column(item, i).values for i, item in enumerate(items)]
        raise ValueError(
            f"{kind} must have rows of one length (or {len(slots)} columns); "
            f"got lengths {sorted(lengths)}"
        )

    try:
        table = np.asarray(items)
    except ValueError:  # deeper nesting of unequal shape
        table = None

    if table is None or table.ndim != 2:
        raise ValueError(f"{kind} must hold numbers, not further nested sequences")

    return _split(table, label, slots, kind)


def _from_series(
    items: Sequence[Any], columns: list[str] | None, label: str, slots: Sequence[Slot], kind: str
) -> PreparedColumns:
    """A list or tuple of pandas Series sharing one index.

    Matched by name like a dict when every Series is named by a role, else
    taken in slot order. The result keeps the shared index.
    """
    pd = sys.modules["pandas"]
    index = items[0].index

    for position, item in enumerate(items):
        if item.index is not index and not item.index.equals(index):
            raise ValueError(
                f"the Series in a {kind} must share one index; Series {position} "
                f"({item.name!r}) differs from Series 0 ({items[0].name!r}). Align them "
                "first, for example with pandas.concat(..., axis=1)"
            )

    restore = restore_series(pd, index)
    names: list[object] = [item.name for item in items]

    if all(name is not None and role_of(name) is not None for name in names):
        chosen = _match(names, columns, label, slots)
        by_name = dict(zip(names, items, strict=True))
        arrays = [from_pandas_series(pd, by_name[key], None).values for key, _ in chosen]

        return _prepared(
            arrays, [key for key, _ in chosen], [role for _, role in chosen], restore, index=index
        )

    if columns is not None:
        order = ", ".join(slot.name for slot in slots)
        raise ValueError(
            f"columns= needs every Series in the {kind} named by a column role (such as "
            f"'high'); Series without role names are taken in the order {order}"
        )

    arrays = [from_pandas_series(pd, item, None).values for item in items]
    labels, roles = _unnamed(arrays, label, slots, f"the {kind}")

    return _prepared(arrays, labels, roles, restore, named=False, index=index)


def _from_pandas_frame(
    pd: Any, data: Any, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select the columns")

    chosen = _match(list(data.columns), columns, label, slots)
    arrays = [from_pandas_series(pd, data[key], None).values for key, _ in chosen]

    return _prepared(
        arrays,
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_frame(pd, data.index),
        index=data.index,
    )


def _from_mapping(
    data: Mapping[object, object], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    chosen = _match(list(data), columns, label, slots)
    prepared = [_column(data[key], key) for key, _ in chosen]
    # Each output keeps the container type of the first input column.
    return _prepared(
        [column.values for column in prepared],
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_columns(prepared[0].restore),
        index=prepared[0].index,
    )


def _from_json(
    data: str | bytes | bytearray, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """Accepts a JSON array of records or of arrays (rows or columns), or an object of arrays.

    `null` is a gap (NaN). The result is returned as JSON of the same shape
    and the same type (str or bytes), with NaN written as `null`.
    """
    try:
        parsed = json.loads(data.removeprefix("\ufeff") if isinstance(data, str) else data)
    except ValueError as error:  # JSONDecodeError and UnicodeDecodeError
        raise ValueError(f"invalid JSON input: {error}") from error

    dump = json_dump(not isinstance(data, str))

    if isinstance(parsed, list):
        rows = cast(list[Any], parsed)
        records = [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]

        if not records:
            return _from_json_arrays(rows, columns, label, slots, dump)
        if len(records) < len(rows):
            raise TypeError("JSON array mixes records and numbers or arrays; use one shape")

        chosen = _match(list(records[0]), columns, label, slots)
        arrays = [
            from_column([row.get(cast(str, key)) for row in records], key).values
            for key, _ in chosen
        ]

        return _prepared(
            arrays,
            [key for key, _ in chosen],
            [role for _, role in chosen],
            restore_records(dump),
        )

    # Text starting with { is always an object (`is_json`).
    table = cast(dict[str, Any], parsed)
    chosen = _match(list(table), columns, label, slots)
    arrays: list[Float64Array] = []

    for key, _ in chosen:
        if not isinstance(table[cast(str, key)], list):
            raise TypeError(f"JSON column {key!r} must be an array of numbers")
        arrays.append(from_column(table[cast(str, key)], key).values)

    return _prepared(
        arrays,
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_json_object(dump),
    )


def _from_csv(
    data: str | bytes | bytearray, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """CSV with a header row, matched by name like a dict; only the matched columns are parsed.

    The result is CSV of the output names, of the same type (str or bytes).
    """
    table = read_csv(data)
    chosen = _match(table.header, columns, label, slots)

    return _prepared(
        [table.column(key) for key, _ in chosen],
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_csv(table.as_bytes),
    )


def _from_json_arrays(
    rows: list[Any],
    columns: list[str] | None,
    label: str,
    slots: Sequence[Slot],
    dump: Callable[[Any], str | bytes],
) -> PreparedColumns:
    """A JSON array of arrays: rows or columns, by the same rule as a list of lists."""
    nested = sum(isinstance(row, list) for row in rows)

    if not nested:
        raise _one_column(label, slots, "a JSON array of numbers")
    if nested < len(rows):
        raise TypeError("JSON array mixes arrays and numbers; use one or the other")

    _reject_columns(columns, "a JSON array of arrays", slots)

    arrays = _nested(cast(list[Sequence[object]], rows), label, slots, "a JSON array of arrays")
    labels, roles = _unnamed(arrays, label, slots, "the JSON array")

    return _prepared(arrays, labels, roles, restore_json_array(dump), named=False)
