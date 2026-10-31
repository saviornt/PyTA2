"""Input normalization and parameter validation.

Every supported input container is reduced to one 1-D, C-contiguous float64
array, together with a function that rebuilds the caller's container from an
indicator's named results. Element-level checks (finite, non-empty) stay in Rust.
Text input is JSON when its first non-whitespace character is `[` or `{`, else
CSV with a header row. Numbers written as strings are read by one parser
(`parse_numbers`) in every container.
"""

import csv
import functools
import io
import itertools
import json
import logging
import math
import operator
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, cast

import numpy as np
from numpy.typing import NDArray
from pydantic import Field, TypeAdapter, ValidationError

from ._types import Float64Array, Prepared, Restore

_log = logging.getLogger("pyta.validation")

_MAX_PERIOD = 2**31 - 1
_AT_LEAST_1 = TypeAdapter(Annotated[int, Field(ge=1, le=_MAX_PERIOD)])
_AT_LEAST_2 = TypeAdapter(Annotated[int, Field(ge=2, le=_MAX_PERIOD)])

_SEPARATORS = re.compile(r"[\s._-]+")
#: A leading number and dot before a letter, as AlphaVantage numbers its fields ("1. open").
_NUMBERING = re.compile(r"\A\s*\d+\.\s*(?=[^\W\d_])")


@functools.lru_cache(maxsize=4096)
def squash(name: object) -> str:
    """Name without case, whitespace, dots, underscores or hyphens, for matching.

    A leading number and dot before a letter is ignored too, so "1. open" and
    "5. adjusted close" match as "open" and "adjusted close".

    Cached: the same column names come back on every call.
    """
    return _SEPARATORS.sub("", _NUMBERING.sub("", str(name), count=1).casefold())


#: What error messages say `squash` ignores.
IGNORED = "case, whitespace, the separators . _ - and a leading number such as '1. '"


# --- role registry --------------------------------------------------------------------------

# A role is what a column holds (close prices, volume, ...). Indicators name
# the roles they calculate on; `normalize` finds the matching column under any
# of the role's aliases. Each alias belongs to exactly one role: "close" never
# falls back to the adjusted close.
_ROLE_ALIASES: dict[str, tuple[str, ...]] = {}
_ROLE_OF: dict[str, str] = {}


def register_role(name: str, *aliases: str) -> str:
    """Adds a column role and returns its name, for use as a constant.

    The name is always an alias of its role. Aliases are compared without case,
    whitespace or the separators `. _ -`, so "Adj Close" and "adj_close" are one
    spelling. A fundamental role such as `eps` is one call; nothing else changes.

    Raises:
        ValueError: The role exists, or an alias already belongs to a role.
    """
    if name in _ROLE_ALIASES:
        raise ValueError(f"role {name!r} is already registered")

    squashed = tuple(dict.fromkeys(squash(alias) for alias in (name, *aliases)))
    taken = [alias for alias in squashed if alias in _ROLE_OF]

    if taken:
        owners = ", ".join(f"{alias!r} ({_ROLE_OF[alias]})" for alias in taken)
        raise ValueError(f"aliases of role {name!r} already belong to other roles: {owners}")

    _ROLE_ALIASES[name] = squashed
    _ROLE_OF.update(dict.fromkeys(squashed, name))

    return name


OPEN = register_role("open", "opening", "openprice", "openingprice", "o")
HIGH = register_role("high", "highest", "highprice", "highestprice", "h")
LOW = register_role("low", "lowest", "lowprice", "lowestprice", "l")
CLOSE = register_role("close", "closing", "closeprice", "closingprice", "c")
ADJ_CLOSE = register_role(
    "adj_close",
    "adjustedclose",
    "adjcloseprice",
    "adjustedcloseprice",
    "adjclosing",
    "adjustedclosing",
)
VOLUME = register_role("volume", "volumes", "vol", "v")


def role_of(name: object) -> str | None:
    """The role `name` is an alias of, or None."""
    return _ROLE_OF.get(squash(name))


def role_aliases(role: str) -> tuple[str, ...]:
    """The squashed aliases of `role`, its own name first."""
    return _ROLE_ALIASES[role]


def role_names() -> tuple[str, ...]:
    """Every registered role, in registration order."""
    return tuple(_ROLE_ALIASES)


@dataclass(frozen=True, slots=True)
class Slot:
    """One input of a multi-column indicator.

    `roles` are the roles the slot accepts, in preference order: CCI's close
    slot takes the close, or else the adjusted close.
    """

    name: str
    roles: tuple[str, ...]

    def describe(self) -> str:
        """The slot as an error message names it: "close (close or adj_close)"."""
        if self.roles == (self.name,):
            return self.name
        return f"{self.name} ({' or '.join(self.roles)})"


def _validate_int(name: str, value: object, minimum: int, adapter: TypeAdapter[int]) -> int:
    """Returns `value` as an int in [minimum, 2**31 - 1], with errors naming `name`.

    Wrong types raise `TypeError`; out-of-range values raise `ValueError`.
    A plain in-range `int` is returned as is: Pydantic would return the same
    value, and skipping it saves about 1 µs per call (measured in a 100-row
    CCI call, where Pydantic's cost in context exceeds its ~0.4 µs alone).
    """
    if type(value) is int and minimum <= value <= _MAX_PERIOD:
        return value

    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not bool")

    try:
        index = operator.index(value)  # type: ignore[arg-type]
    except TypeError:
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}") from None

    try:
        return adapter.validate_python(index)
    except ValidationError:
        # Replace Pydantic's multi-line report with one actionable sentence.
        raise ValueError(
            f"{name} must be between {minimum} and {_MAX_PERIOD}, got {index}"
        ) from None


def validate_period(period: object) -> int:
    """Returns `period` as an int in [1, 2**31 - 1].

    Wrong types raise `TypeError`; out-of-range values raise `ValueError`.
    """
    # Inlined fast path of `_validate_int`: this runs on every call.
    if type(period) is int and 1 <= period <= _MAX_PERIOD:
        return period

    return _validate_int("period", period, 1, _AT_LEAST_1)


def validate_fast(fast: object) -> int:
    """Returns MACD's `fast` period as an int in [2, 2**31 - 1] (TA-Lib's lower bound)."""
    return _validate_int("fast", fast, 2, _AT_LEAST_2)


def validate_slow(slow: object) -> int:
    """Returns MACD's `slow` period as an int in [2, 2**31 - 1] (TA-Lib's lower bound)."""
    return _validate_int("slow", slow, 2, _AT_LEAST_2)


def validate_signal(signal: object) -> int:
    """Returns MACD's `signal` period as an int in [1, 2**31 - 1]."""
    return _validate_int("signal", signal, 1, _AT_LEAST_1)


@functools.cache
def _at_least(minimum: int) -> TypeAdapter[int]:
    """The Pydantic adapter for ints in [minimum, 2**31 - 1], built once per minimum."""
    return TypeAdapter(Annotated[int, Field(ge=minimum, le=_MAX_PERIOD)])


def validate_int(name: str, value: object, minimum: int = 1) -> int:
    """Returns the integer parameter `name` as an int in [minimum, 2**31 - 1].

    For integer parameters other than `period` (ULTOSC's `short`, `medium`,
    `long`). Wrong types (including bool) raise `TypeError`; out-of-range
    values raise `ValueError`.
    """
    if type(value) is int and minimum <= value <= _MAX_PERIOD:
        return value

    return _validate_int(name, value, minimum, _at_least(minimum))


def validate_positive_float(name: str, value: object, maximum: float | None = None) -> float:
    """Returns the parameter `name` as a finite float above 0 (and at most `maximum`).

    An int (or NumPy integer) is accepted and converted; a NumPy float is a
    float. Wrong types, including bool, raise `TypeError`; zero, negative,
    non-finite or too-large values raise `ValueError`.
    """
    # Fast path: a plain float in range, as most calls pass (false for NaN).
    if type(value) is float and 0.0 < value < math.inf and (maximum is None or value <= maximum):
        return value

    if isinstance(value, bool):
        raise TypeError(f"{name} must be a number, not bool")

    if isinstance(value, float):  # also float subclasses, such as numpy.float64
        number = float(value)
    else:
        try:
            number = float(operator.index(value))  # type: ignore[arg-type]
        except TypeError:
            raise TypeError(f"{name} must be a number, got {type(value).__name__}") from None
        except OverflowError:  # an int beyond the float range
            number = math.inf

    if not 0.0 < number < math.inf:
        raise ValueError(f"{name} must be a finite number greater than 0, got {value!r}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be at most {maximum}, got {value!r}")

    return number


def validate_bool(name: str, value: object) -> bool:
    """Returns the flag parameter `name` as a bool (Ichimoku's `shift`).

    Only `True`, `False` or a NumPy bool is accepted; anything else, including
    0, 1, None and strings, raises `TypeError`, so a misspelt or misplaced
    argument is not read as a flag.
    """
    if value is False or value is True:
        return value
    if isinstance(value, np.bool_):
        return value is np.True_  # NumPy bools are singletons

    raise TypeError(f"{name} must be True or False, got {type(value).__name__}")


def validate_ascending(*named: tuple[str, float], strict: bool) -> None:
    """Checks that already validated parameters are in ascending order, as given.

    `strict` requires each value to be less than the next (ULTOSC's
    `short < medium < long`); otherwise equal neighbours are allowed (SAR's
    `acceleration <= maximum`). Out-of-order values raise `ValueError` naming
    both parameters; PyTA never reorders or clamps them.
    """
    for (lower, low), (upper, high) in itertools.pairwise(named):
        if low < high or (low == high and not strict):
            continue

        relation = "less than" if strict else "at most"
        raise ValueError(
            f"{lower} must be {relation} {upper}, got {lower}={low} and {upper}={high}"
        )


def normalize(data: object, column: str | None, default_column: str) -> Prepared:
    """Converts any supported container to a `Prepared` float64 series.

    `column` is the caller's explicit choice. When it is None, the input's
    only column is used, or else `default_column`: the role the indicator
    calculates on (`CLOSE`, `HIGH`, ...).
    """
    if isinstance(data, str | bytes | bytearray):
        if is_json(data):
            return _from_json(data, column, default_column)
        return _from_csv(data, column, default_column)
    if isinstance(data, np.ndarray):
        return _from_array(cast(NDArray[Any], data), column)
    if isinstance(data, list | tuple):
        return _from_sequence(cast(Sequence[object], data), column)
    if isinstance(data, Mapping):
        return _from_mapping(cast(Mapping[object, object], data), column, default_column)

    # pandas is only inspected if the caller has already imported it, so
    # `import pyta` never loads it and a missing pandas is never an error.
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(data, pd.DataFrame):
            return _from_pandas_frame(pd, data, column, default_column)
        if isinstance(data, pd.Series):
            return from_pandas_series(pd, data, column)

    raise TypeError(
        f"unsupported input type {type(data).__name__}; expected a list, tuple, NumPy array, "
        "pandas Series or DataFrame, dict, or JSON or CSV text"
    )


# --- column selection -----------------------------------------------------------------------


def _pick(keys: Sequence[object], column: str | None, default_column: str) -> object:
    """Chooses one key: explicit `column`, else the only key, else `default_column`.

    An explicit `column` must name a known role (any alias of it), even when
    the input has a column spelled that way, so calls read the same on every
    data source. The wanted name is tried as written, then under the other
    aliases of its role (for example "adjusted close" for `ADJ_CLOSE`).
    """
    if column is not None and squash(column) not in _ROLE_OF:
        raise ValueError(
            f"column {column!r} is not a recognized column name; use one of "
            f"{', '.join(_ROLE_ALIASES)} (or an alias such as 'adjusted close'). "
            "Rename the input's columns if they use other names"
        )

    lookup: dict[str, object] = {}

    for key in keys:
        squashed = squash(key)

        if squashed in lookup:
            raise ValueError(
                f"column names {lookup[squashed]!r} and {key!r} are the same "
                f"after ignoring {IGNORED}"
            )

        lookup[squashed] = key

    if column is None and len(lookup) == 1:
        return next(iter(lookup.values()))

    wanted = squash(default_column if column is None else column)
    role = _ROLE_OF.get(wanted)

    for candidate in (wanted, *(_ROLE_ALIASES[role] if role else ())):
        if candidate in lookup:
            key = lookup[candidate]
            _log.debug("using column %r for %r", key, default_column if column is None else column)
            return key

    available = ", ".join(repr(key) for key in keys)

    if column is None:
        raise ValueError(
            f"no {default_column!r} column found; available columns: {available}. "
            "Pass column= to choose one"
        )

    raise ValueError(f"column {column!r} not found; available columns: {available}")


def _reject_column(column: str | None, kind: str) -> None:
    if column is not None:
        raise ValueError(f"column= is not valid for {kind} input, which has no columns")


# --- dtype conversion -----------------------------------------------------------------------


def to_float64(values: NDArray[Any], name: object = None) -> Float64Array:
    """Converts a real numeric array to 1-D, C-contiguous float64 without copying if possible.

    Strings holding numbers are parsed (`parse_numbers`); `name` is the column
    the values came from, for error messages (None when there is none).
    """
    if values.ndim != 1:
        raise ValueError(
            f"{_where(name)}expected a 1-D series, got an array with shape {values.shape}"
        )

    kind = values.dtype.kind

    if kind in "iuf":
        converted = values
    elif kind == "O":
        # Object arrays arise from lists containing None (a gap), JSON nulls
        # and strings mixed with gaps. Bools must not be silently converted.
        if any(isinstance(item, str | bytes | bool | np.bool_) for item in values):
            return parse_numbers(values, name)
        try:
            converted = values.astype(np.float64)
        except TypeError, ValueError:  # an item that is not a number: name it
            return parse_numbers(values, name)
    elif kind in "US":  # strings (NumPy makes a list of str and numbers one)
        return parse_numbers(values, name)
    elif kind == "b":
        raise TypeError(f"{_where(name)}holds booleans, which are not numbers")
    else:
        raise TypeError(
            f"{_where(name)}holds {_KIND_NAMES.get(kind, 'values')} ({values.dtype}), "
            "which are not real numbers"
        )

    return np.ascontiguousarray(converted, dtype=np.float64)


_KIND_NAMES = {"c": "complex numbers", "M": "dates", "m": "time spans", "V": "raw bytes"}


def _where(name: object) -> str:
    """The start of a value error message: "column 'close' " or "input "."""
    return "input " if name is None else f"column {name!r} "


def _number(item: object) -> float:
    """One value as a float: a number, None (a gap), or a string holding a number.

    Strings ignore surrounding whitespace; empty is a gap, and so is `NaN`.

    Raises:
        TypeError: A bool, or anything else that is not a number.
        ValueError: A string that is not a number.
    """
    if isinstance(item, str | bytes):
        text = item.strip()
        return float(text) if text else math.nan
    if item is None:
        return math.nan
    if isinstance(item, bool | np.bool_):
        raise TypeError("bool")

    return float(cast(float, item))


def parse_numbers(items: Sequence[object] | NDArray[Any], name: object = None) -> Float64Array:
    """The one parser for values that may be strings, used by every container.

    Each item is a number, None (a gap), or a string holding a number (`"187.15"`,
    `" 1e3 "`); an empty string or `NaN` text is a gap.

    Raises:
        TypeError: An item is not a number or numeric string, naming `name`
            (the column, when there is one) and the item's index.
    """
    try:
        return np.fromiter(map(_number, items), np.float64, len(items))
    except TypeError, ValueError:
        pass

    for index, item in enumerate(cast(Sequence[object], items)):
        try:
            _number(item)
        except TypeError, ValueError:
            if isinstance(item, bool | np.bool_):
                reason = "booleans are not numbers"
            elif isinstance(item, str | bytes):
                reason = "expected a number, an empty field or NaN"
            else:
                reason = f"expected a number, got {type(item).__name__}"
            raise TypeError(
                f"{_where(name)}value {_shown(cast(object, item))} at index {index} is not "
                f"a number; {reason}"
            ) from None

    raise AssertionError("unreachable: every item parsed on the second pass")  # pragma: no cover


def _shown(item: object) -> str:
    """An item for an error message, shortened if long."""
    value = cast(object, item.item()) if isinstance(item, np.generic) else item
    text = repr(value)
    return text if len(text) <= 40 else f"{text[:37]}..."


# --- restoring results ----------------------------------------------------------------------


def one_series(single: Callable[[Float64Array, str], Any]) -> Restore:
    """A `Restore` for a one-series container, from its single-output form.

    One output is returned in that form; several are a tuple of them, in the
    indicator's documented order.
    """

    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> Any:
        if len(results) == 1:
            return single(results[0], names[0])
        return tuple(map(single, results, names, strict=True))

    return restore


def _as_list(out: Float64Array, _name: str) -> list[float]:
    return out.tolist()


def _as_tuple(out: Float64Array, _name: str) -> tuple[float, ...]:
    return tuple(out.tolist())


def _restore_array(_names: Sequence[str], results: Sequence[Float64Array]) -> Any:
    """`one_series` for a NumPy array, written out: it runs on every array call."""
    return results[0] if len(results) == 1 else tuple(results)


#: Restores for unnamed one-series containers, shared by every call.
RESTORE_ARRAY: Restore = _restore_array
RESTORE_LIST = one_series(_as_list)
RESTORE_TUPLE = one_series(_as_tuple)


def restore_columns(inner: Restore) -> Restore:
    """A `Restore` for a dict: one key per output, each value restored by `inner`.

    `inner` is the restore of the input column's own container, so each output
    keeps that container type. The restores for the shared `inner` ones are
    built once (see `_COLUMN_RESTORES`).
    """
    shared = _COLUMN_RESTORES.get(inner)
    return shared if shared is not None else _restore_columns(inner)


def _restore_columns(inner: Restore) -> Restore:
    """Builds the `restore_columns` closure for `inner`."""

    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> dict[str, Any]:
        if len(results) == 1:
            return {names[0]: inner(names, results)}
        return {name: inner((name,), (out,)) for name, out in zip(names, results, strict=True)}

    return restore


#: `restore_columns` for each shared inner restore, built once: building one per
#: call cost ~0.1 µs per dict of arrays.
_COLUMN_RESTORES: dict[Restore, Restore] = {
    inner: _restore_columns(inner) for inner in (RESTORE_ARRAY, RESTORE_LIST, RESTORE_TUPLE)
}


def restore_frame(pd: Any, index: Any) -> Restore:
    """A `Restore` for a DataFrame: one column per output, keeping `index`."""
    return lambda names, results: pd.DataFrame(dict(zip(names, results, strict=True)), index=index)


def restore_series(pd: Any, index: Any) -> Restore:
    """A `Restore` for pandas Series: each output a Series named by it, keeping `index`.

    One output is a Series; several are a tuple of them, in documented order.
    """

    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> Any:
        if len(results) == 1:
            return pd.Series(results[0], index=index, name=names[0])
        return tuple(
            pd.Series(out, index=index, name=name) for name, out in zip(names, results, strict=True)
        )

    return restore


def json_dump(as_bytes: bool) -> Callable[[Any], str | bytes]:
    """Serializes to compact JSON, as bytes when the input was bytes."""

    def dump(obj: Any) -> str | bytes:
        text = json.dumps(obj, allow_nan=False, separators=(",", ":"))
        return text.encode() if as_bytes else text

    return dump


def restore_records(dump: Callable[[Any], str | bytes]) -> Restore:
    """A `Restore` for a JSON array of records: each record keyed by every output name."""

    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> str | bytes:
        columns = [nulls(values) for values in results]
        return dump([dict(zip(names, row, strict=True)) for row in zip(*columns, strict=True)])

    return restore


def restore_json_array(dump: Callable[[Any], str | bytes]) -> Restore:
    """A `Restore` for an unnamed JSON array: one output is an array, several an object.

    The object is keyed by output name, as JSON has no tuple.
    """

    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> str | bytes:
        if len(results) == 1:
            return dump(nulls(results[0]))
        return dump({name: nulls(out) for name, out in zip(names, results, strict=True)})

    return restore


def restore_json_object(dump: Callable[[Any], str | bytes]) -> Restore:
    """A `Restore` for a JSON object of arrays: one key per output."""
    return lambda names, results: dump(
        {name: nulls(values) for name, values in zip(names, results, strict=True)}
    )


def csv_fields(values: Float64Array) -> list[str]:
    """CSV fields: Python's shortest round-trip `repr`, and an empty field for NaN."""
    return [repr(value) if value == value else "" for value in values.tolist()]


def csv_quote(text: str) -> str:
    """One CSV field, quoted (with `"` doubled) only when it holds `,`, `"` or a line break."""
    if any(char in text for char in ',"\r\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def csv_text(header: Sequence[str], columns: Sequence[Sequence[str]]) -> str:
    """CSV of a header row and equal-length columns of fields, each line ending in `\\n`.

    Fields are written as given (`csv_fields`, `csv_quote`), so the caller decides quoting.
    """
    rows = columns[0] if len(columns) == 1 else map(",".join, zip(*columns, strict=True))
    return "\n".join((",".join(header), *rows)) + "\n"


def restore_csv(as_bytes: bool) -> Restore:
    """A `Restore` for CSV: a header of the output names, then one row per input row.

    The input's other columns are not repeated (as for JSON records); NaN is an
    empty field and every line ends with a line feed. Bytes in give UTF-8 bytes out.
    """
    return _CSV_BYTES if as_bytes else _CSV_TEXT


def _restore_csv_text(names: Sequence[str], results: Sequence[Float64Array]) -> str:
    return csv_text(names, [csv_fields(values) for values in results])


def _restore_csv_bytes(names: Sequence[str], results: Sequence[Float64Array]) -> bytes:
    return _restore_csv_text(names, results).encode()


_CSV_TEXT: Restore = _restore_csv_text
_CSV_BYTES: Restore = _restore_csv_bytes


# --- containers -----------------------------------------------------------------------------


def _from_array(data: NDArray[Any], column: str | None, name: object = None) -> Prepared:
    _reject_column(column, "array")

    if isinstance(data, np.ma.MaskedArray):
        data = np.ma.filled(data.astype(np.float64), np.nan)

    try:
        values = to_float64(data, name)
    except ValueError:  # not 1-D
        if name is not None:  # a dict's column: `to_float64` names it
            raise
        shape = data.shape
        example = "(for example data[:, 0])" if len(shape) == 2 else ""
        raise _not_one_series(f"a {len(shape)}-D array of shape {shape}", example) from None

    return Prepared(values, RESTORE_ARRAY)


def _from_sequence(
    data: Sequence[object], column: str | None, name: object = None, kind: str | None = None
) -> Prepared:
    """A list or tuple of numbers; `kind` names it in errors when it is not one ("JSON array")."""
    _reject_column(column, "list/tuple")

    try:
        array = np.asarray(data)
    except ValueError:  # ragged nested sequences
        if name is not None:
            raise ValueError(
                f"{_where(name)}expected a flat sequence of numbers, got nested sequences"
            ) from None
        what, items = _sequence_kind(data, kind)
        raise _not_one_series(f"{what} of nested {items}") from None

    try:
        values = to_float64(array, name)
    except ValueError:  # nested sequences of one length: a table
        if name is not None:
            raise
        what, items = _sequence_kind(data, kind)
        if len(data) == 1:
            one = "an array" if kind is not None else "a sequence"
            raise _not_one_series(f"a one-item {what[2:]} holding {one}", "(data[0])") from None
        raise _not_one_series(
            f"{what} of {len(data)} {items} (a table of shape {array.shape})"
        ) from None

    return Prepared(values, RESTORE_TUPLE if isinstance(data, tuple) else RESTORE_LIST)


def _sequence_kind(data: Sequence[object], kind: str | None) -> tuple[str, str]:
    """How an error names a list or tuple ("a list", "a JSON array") and its nested items."""
    if kind is not None:
        return f"a {kind}", "arrays"
    return ("a tuple" if isinstance(data, tuple) else "a list"), "sequences"


def _not_one_series(what: str, example: str = "") -> ValueError:
    """The error for a table, or a container of one, given to a one-column indicator."""
    hint = f" {example}" if example else ""
    return ValueError(
        f"expected one series of numbers, got {what}; this indicator takes one column: pass "
        f"that column alone{hint}, or a DataFrame or dict with column= to pick it by name"
    )


def from_pandas_series(pd: Any, data: Any, column: str | None) -> Prepared:
    _reject_column(column, "Series")

    dtype = data.dtype
    types = pd.api.types

    if (
        not types.is_numeric_dtype(dtype)
        or types.is_bool_dtype(dtype)
        or types.is_complex_dtype(dtype)
    ):
        if (isinstance(dtype, np.dtype) and dtype.kind == "O") or isinstance(dtype, pd.StringDtype):
            # Strings holding numbers (a frame built from JSON text); gaps become None.
            values = parse_numbers(data.to_numpy(dtype=object, na_value=None), data.name)
        else:
            what = "booleans" if types.is_bool_dtype(dtype) else f"dtype {dtype}"
            raise TypeError(
                f"{_where(data.name)}holds {what}, which are not real numbers; expected a "
                "numeric dtype or strings holding numbers"
            )
    elif isinstance(dtype, np.dtype):
        values = data.to_numpy(dtype=np.float64, copy=False)
    else:  # nullable extension dtypes: pd.NA becomes NaN
        values = data.to_numpy(dtype=np.float64, na_value=np.nan)

    index = data.index

    # One closure per call: a single output is the common case.
    def restore(names: Sequence[str], results: Sequence[Float64Array]) -> Any:
        if len(results) == 1:
            return pd.Series(results[0], index=index, name=names[0])
        return tuple(
            pd.Series(out, index=index, name=name) for name, out in zip(names, results, strict=True)
        )

    label = data.name
    return Prepared(to_float64(values), restore, () if label is None else (label,), index)


def _from_pandas_frame(pd: Any, data: Any, column: str | None, default_column: str) -> Prepared:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select a column")

    label = _pick(list(data.columns), column, default_column)
    series = from_pandas_series(pd, data[label], None)

    return Prepared(series.values, restore_frame(pd, data.index), (label,), data.index)


def from_column(value: object, key: object) -> Prepared:
    """Normalizes one column of a dict (list, tuple, array, or Series)."""
    if isinstance(value, np.ndarray):
        return _from_array(cast(NDArray[Any], value), None, key)
    if isinstance(value, list | tuple):
        return _from_sequence(cast(Sequence[object], value), None, key)

    pd = sys.modules.get("pandas")
    if pd is not None and isinstance(value, pd.Series):
        return from_pandas_series(pd, value, None)

    raise TypeError(
        f"column {key!r} must be a list, tuple, NumPy array or pandas Series, "
        f"got {type(value).__name__}"
    )


def _from_mapping(
    data: Mapping[object, object], column: str | None, default_column: str
) -> Prepared:
    key = _pick(list(data), column, default_column)
    inner = from_column(data[key], key)

    # Each output keeps the input column's container type.
    return Prepared(inner.values, restore_columns(inner.restore), (key,), inner.index)


def nulls(values: Float64Array) -> list[float | None]:
    """Python floats with NaN replaced by None, since JSON has no NaN."""
    boxed = values.astype(object)
    boxed[np.isnan(values)] = None
    return boxed.tolist()


def _from_json(data: str | bytes | bytearray, column: str | None, default_column: str) -> Prepared:
    """Accepts a JSON array of numbers, array of records, or object of arrays.

    `null` is a gap (NaN). The result is returned as JSON of the same shape
    and the same type (str or bytes), with NaN written as `null`; several
    outputs from an array of numbers become an object keyed by output name.
    """
    try:
        parsed = json.loads(data.removeprefix("\ufeff") if isinstance(data, str) else data)
    except ValueError as error:  # JSONDecodeError and UnicodeDecodeError
        raise ValueError(f"invalid JSON input: {error}") from error

    dump = json_dump(not isinstance(data, str))

    if isinstance(parsed, list):
        parsed = cast(list[Any], parsed)
        records = sum(isinstance(row, dict) for row in parsed)

        if 0 < records < len(parsed):
            raise TypeError("JSON array mixes records and numbers; use one or the other")

        if records:
            key = _pick(list(parsed[0]), column, default_column)
            values = _from_sequence([row.get(key) for row in parsed], None, key).values

            return Prepared(values, restore_records(dump), (key,))

        _reject_column(column, "JSON array")
        values = _from_sequence(parsed, None, kind="JSON array").values

        return Prepared(values, restore_json_array(dump))

    # Text starting with { is always an object (`is_json`).
    table = cast(dict[Any, Any], parsed)
    key = _pick(list(table), column, default_column)

    if not isinstance(table[key], list):
        raise TypeError(f"JSON column {key!r} must be an array of numbers")

    values = _from_sequence(table[key], None, key).values

    return Prepared(values, restore_json_object(dump), (key,))


# --- CSV ------------------------------------------------------------------------------------

#: First characters of JSON text, as `str` characters and as bytes.
_JSON_FIRST = frozenset(("[", "{", ord("["), ord("{")))
_LEADING_TEXT = re.compile(r"[\s\ufeff]*(.)", re.DOTALL)
_LEADING_BYTES = re.compile(rb"(?:\xef\xbb\xbf)?\s*(.)", re.DOTALL)


def is_json(data: str | bytes | bytearray) -> bool:
    """True when the first non-whitespace character of `data` is `[` or `{`; else it is CSV.

    A byte-order mark is skipped. Only the leading whitespace is scanned.
    """
    if data and data[0] in _JSON_FIRST:
        return True

    if isinstance(data, str):
        match = _LEADING_TEXT.match(data)
        return match is not None and match.group(1) in "[{"

    found = _LEADING_BYTES.match(data)
    return found is not None and found.group(1) in (b"[", b"{")


@dataclass(frozen=True, slots=True)
class CsvTable:
    """CSV text split into its header and rows of fields, all as `str`."""

    header: list[str]
    rows: list[list[str]]
    as_bytes: bool

    def column(self, key: object) -> Float64Array:
        """The values of column `key` (a header name), parsed by `parse_numbers`."""
        index = self.header.index(cast(str, key))
        return parse_numbers([row[index] for row in self.rows], key)


def read_csv(data: str | bytes | bytearray) -> CsvTable:
    """Splits CSV text (delimiter `,`, header row required) into a `CsvTable`.

    Bytes are UTF-8, with or without a byte-order mark. Quoted fields and
    CRLF line endings work. Blank lines at the end are ignored; in a one-column
    file any other blank line is an empty field (a gap), as PyTA writes it.

    Raises:
        ValueError: Invalid UTF-8 or CSV, no header row, or a row whose field
            count differs from the header's.
    """
    as_bytes = not isinstance(data, str)

    if isinstance(data, str):
        text = data
    else:
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"CSV input is not valid UTF-8: {error}") from None

    reader = csv.reader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)

    try:
        header = next(reader, None)
        rows = list(reader)
    except csv.Error as error:
        raise ValueError(f"invalid CSV input: {error}") from None

    # A first line of only numbers is data, not names: reading it as a header would drop a row.
    if not header or all(_is_number_or_blank(name) for name in header):
        raise ValueError(
            "CSV input has no header row; the first line must name the columns (for example "
            "'close'). Text starting with [ or { is read as JSON"
        )

    while rows and not rows[-1]:
        rows.pop()

    width = len(header)
    for position, row in enumerate(rows):
        if len(row) != width:
            if width == 1 and not row:
                rows[position] = [""]
                continue
            raise ValueError(
                f"CSV row {position} (data rows numbered from 0 after the header) has "
                f"{len(row)} fields, but the header has {width}"
            )

    return CsvTable(header, rows, as_bytes)


def _is_number_or_blank(field: str) -> bool:
    """True for a field that reads as a number or a gap (empty or `NaN`)."""
    try:
        _number(field)
    except ValueError:
        return False
    return True


def _from_csv(data: str | bytes | bytearray, column: str | None, default_column: str) -> Prepared:
    """CSV with a header row: the column is picked as for a dict.

    The result is CSV of the output names (one row per input row, NaN an empty
    field), of the same type (str or bytes). Only the picked column is parsed.
    """
    table = read_csv(data)
    key = _pick(table.header, column, default_column)

    return Prepared(table.column(key), restore_csv(table.as_bytes), (key,))
