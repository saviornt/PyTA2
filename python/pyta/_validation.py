"""Input normalization and parameter validation.

Every supported input container is reduced to one 1-D, C-contiguous float64
array, together with a function that rebuilds the caller's container from an
indicator's named results. Element-level checks (finite, non-empty) stay in Rust.
"""

import functools
import json
import logging
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


@functools.lru_cache(maxsize=4096)
def squash(name: object) -> str:
    """Name without case, whitespace, dots, underscores or hyphens, for matching.

    Cached: the same column names come back on every call.
    """
    return _SEPARATORS.sub("", str(name).casefold())


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


def normalize(data: object, column: str | None, default_column: str) -> Prepared:
    """Converts any supported container to a `Prepared` float64 series.

    `column` is the caller's explicit choice. When it is None, the input's
    only column is used, or else `default_column`: the role the indicator
    calculates on (`CLOSE`, `HIGH`, ...).
    """
    if isinstance(data, str | bytes | bytearray):
        return _from_json(data, column, default_column)
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
        "pandas Series or DataFrame, dict, or JSON string"
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
                "after ignoring case, whitespace and the separators . _ -"
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


def to_float64(values: NDArray[Any]) -> Float64Array:
    """Converts a real numeric array to 1-D, C-contiguous float64 without copying if possible."""
    if values.ndim != 1:
        raise ValueError(f"expected a 1-D series, got an array with shape {values.shape}")

    kind = values.dtype.kind

    if kind == "O":
        # Object arrays arise from lists containing None (a gap) and from
        # JSON nulls. Strings and bools must not be silently converted.
        if any(isinstance(item, str | bytes | bool | np.bool_) for item in values):
            raise TypeError("input must contain only numbers (or None for gaps)")
        converted = values.astype(np.float64)
    elif kind in "iuf":
        converted = values
    else:
        raise TypeError(f"unsupported dtype {values.dtype}; expected a real numeric dtype")

    return np.ascontiguousarray(converted, dtype=np.float64)


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


def restore_json_object(dump: Callable[[Any], str | bytes]) -> Restore:
    """A `Restore` for a JSON object of arrays: one key per output."""
    return lambda names, results: dump(
        {name: nulls(values) for name, values in zip(names, results, strict=True)}
    )


# --- containers -----------------------------------------------------------------------------


def _from_array(data: NDArray[Any], column: str | None) -> Prepared:
    _reject_column(column, "array")

    if isinstance(data, np.ma.MaskedArray):
        data = np.ma.filled(data.astype(np.float64), np.nan)

    return Prepared(to_float64(data), RESTORE_ARRAY)


def _from_sequence(data: Sequence[object], column: str | None) -> Prepared:
    _reject_column(column, "list/tuple")

    try:
        array = np.asarray(data)
    except ValueError:  # ragged nested sequences
        raise ValueError("expected a flat sequence of numbers, got nested sequences") from None

    values = to_float64(array)

    return Prepared(values, RESTORE_TUPLE if isinstance(data, tuple) else RESTORE_LIST)


def from_pandas_series(pd: Any, data: Any, column: str | None) -> Prepared:
    _reject_column(column, "Series")

    dtype = data.dtype
    types = pd.api.types

    if (
        not types.is_numeric_dtype(dtype)
        or types.is_bool_dtype(dtype)
        or types.is_complex_dtype(dtype)
    ):
        raise TypeError(f"unsupported Series dtype {dtype}; expected a real numeric dtype")

    if isinstance(dtype, np.dtype):
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
    return Prepared(to_float64(values), restore, () if label is None else (label,))


def _from_pandas_frame(pd: Any, data: Any, column: str | None, default_column: str) -> Prepared:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select a column")

    label = _pick(list(data.columns), column, default_column)
    series = from_pandas_series(pd, data[label], None)

    return Prepared(series.values, restore_frame(pd, data.index), (label,))


def from_column(value: object, key: object) -> Prepared:
    """Normalizes one column of a dict (list, tuple, array, or Series)."""
    if isinstance(value, np.ndarray):
        return _from_array(cast(NDArray[Any], value), None)
    if isinstance(value, list | tuple):
        return _from_sequence(cast(Sequence[object], value), None)

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
    return Prepared(inner.values, restore_columns(inner.restore), (key,))


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
        parsed = json.loads(data)
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
            values = _from_sequence([row.get(key) for row in parsed], None).values

            return Prepared(values, restore_records(dump), (key,))

        _reject_column(column, "JSON array")
        values = _from_sequence(parsed, None).values

        # One output is an array like the input; several are an object keyed by name.
        def restore(names: Sequence[str], results: Sequence[Float64Array]) -> str | bytes:
            if len(results) == 1:
                return dump(nulls(results[0]))
            return dump({name: nulls(out) for name, out in zip(names, results, strict=True)})

        return Prepared(values, restore)

    if isinstance(parsed, dict):  # columns
        parsed = cast(dict[Any, Any], parsed)
        key = _pick(list(parsed), column, default_column)

        if not isinstance(parsed[key], list):
            raise TypeError(f"JSON column {key!r} must be an array of numbers")

        values = _from_sequence(parsed[key], None).values

        return Prepared(values, restore_json_object(dump), (key,))

    raise TypeError(
        "JSON input must be an array of numbers, an array of records, or an object of arrays"
    )
