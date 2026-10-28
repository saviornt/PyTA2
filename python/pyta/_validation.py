"""Input normalization and parameter validation.

Every supported input container is reduced to one 1-D, C-contiguous float64
array, together with a function that rebuilds the caller's container from a
result. Element-level checks (finite, non-empty) stay in Rust.
"""

import json
import logging
import operator
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

import numpy as np
from pydantic import Field, TypeAdapter, ValidationError

from ._types import Float64Array, Prepared

_log = logging.getLogger("pyta.validation")

_MAX_PERIOD = 2**31 - 1
_PERIOD = TypeAdapter(Annotated[int, Field(ge=1, le=_MAX_PERIOD)])

# Column roles. Indicators name the role they calculate on (for example `CLOSE`);
# `normalize` finds the matching column under any of the role's aliases.
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
ADJ_CLOSE = "adj_close"
VOLUME = "volume"

# Aliases are written without case, spaces, dots, underscores or hyphens (see
# `_squash`), so "Adj Close", "adj_close" and "ADJ.CLOSE" are one spelling.
# A role is never matched by another role's aliases: "close" does not
# fall back to the adjusted close.
_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    OPEN: ("open", "opening", "openprice", "openingprice", "o"),
    HIGH: ("high", "highest", "highprice", "highestprice", "h"),
    LOW: ("low", "lowest", "lowprice", "lowestprice", "l"),
    CLOSE: ("close", "closing", "closeprice", "closingprice", "c"),
    ADJ_CLOSE: (
        "adjclose",
        "adjustedclose",
        "adjcloseprice",
        "adjustedcloseprice",
        "adjclosing",
        "adjustedclosing",
    ),
    VOLUME: ("volume", "volumes", "vol", "v"),
}
_ROLE_OF: dict[str, str] = {
    alias: role for role, aliases in _ROLE_ALIASES.items() for alias in aliases
}
_SEPARATORS = re.compile(r"[\s._-]+")


def validate_period(period: object) -> int:
    """Returns `period` as an int in [1, 2**31 - 1].

    Wrong types raise `TypeError`; out-of-range values raise `ValueError`.
    """
    if isinstance(period, bool):
        raise TypeError("period must be an integer, not bool")

    try:
        index = operator.index(period)  # type: ignore[arg-type]
    except TypeError:
        raise TypeError(f"period must be an integer, got {type(period).__name__}") from None

    try:
        return _PERIOD.validate_python(index)
    except ValidationError:
        # Replace Pydantic's multi-line report with one actionable sentence.
        raise ValueError(f"period must be between 1 and {_MAX_PERIOD}, got {index}") from None


def normalize(data: object, column: str | None, default_column: str) -> Prepared:
    """Converts any supported container to a `Prepared` float64 series.

    `column` is the caller's explicit choice. When it is None, the input's
    only column is used, or else `default_column`: the role the indicator
    calculates on (`CLOSE`, `HIGH`, ...).
    """
    if isinstance(data, str | bytes | bytearray):
        return _from_json(data, column, default_column)
    if isinstance(data, np.ndarray):
        return _from_array(data, column)
    if isinstance(data, list | tuple):
        return _from_sequence(data, column)
    if isinstance(data, Mapping):
        return _from_mapping(data, column, default_column)

    # pandas is only inspected if the caller has already imported it, so
    # `import pyta` never loads it and a missing pandas is never an error.
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(data, pd.DataFrame):
            return _from_pandas_frame(pd, data, column, default_column)
        if isinstance(data, pd.Series):
            return _from_pandas_series(pd, data, column)

    raise TypeError(
        f"unsupported input type {type(data).__name__}; expected a list, tuple, NumPy array, "
        "pandas Series or DataFrame, dict, or JSON string"
    )


# --- column selection -----------------------------------------------------------------------


def _squash(name: object) -> str:
    """Name without case, whitespace, dots, underscores or hyphens, for matching."""
    return _SEPARATORS.sub("", str(name).casefold())


def _pick(keys: Sequence[object], column: str | None, default_column: str) -> object:
    """Chooses one key: explicit `column`, else the only key, else `default_column`.

    An explicit `column` must name a known role (any alias of it), even when
    the input has a column spelled that way, so calls read the same on every
    data source. The wanted name is tried as written, then under the other
    aliases of its role (for example "adjusted close" for `ADJ_CLOSE`).
    """
    if column is not None and _squash(column) not in _ROLE_OF:
        raise ValueError(
            f"column {column!r} is not a recognized column name; use one of "
            f"{', '.join(_ROLE_ALIASES)} (or an alias such as 'adjusted close'). "
            "Rename the input's columns if they use other names"
        )

    lookup: dict[str, object] = {}

    for key in keys:
        squashed = _squash(key)

        if squashed in lookup:
            raise ValueError(
                f"column names {lookup[squashed]!r} and {key!r} are the same "
                "after ignoring case, whitespace and the separators . _ -"
            )

        lookup[squashed] = key

    if column is None and len(lookup) == 1:
        return next(iter(lookup.values()))

    wanted = _squash(default_column if column is None else column)
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


def _to_float64(values: np.ndarray) -> Float64Array:
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


# --- containers -----------------------------------------------------------------------------


def _from_array(data: np.ndarray, column: str | None) -> Prepared:
    _reject_column(column, "array")

    if isinstance(data, np.ma.MaskedArray):
        data = data.astype(np.float64).filled(np.nan)

    return Prepared(_to_float64(data), lambda out, _name: out)


def _from_sequence(data: list | tuple, column: str | None) -> Prepared:
    _reject_column(column, "list/tuple")

    try:
        array = np.asarray(data)
    except ValueError:  # ragged nested sequences
        raise ValueError("expected a flat sequence of numbers, got nested sequences") from None

    values = _to_float64(array)

    if isinstance(data, tuple):
        return Prepared(values, lambda out, _name: tuple(out.tolist()))

    return Prepared(values, lambda out, _name: out.tolist())


def _from_pandas_series(pd: Any, data: Any, column: str | None) -> Prepared:
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

    return Prepared(
        _to_float64(values),
        lambda out, name: pd.Series(out, index=data.index, name=name),
    )


def _from_pandas_frame(pd: Any, data: Any, column: str | None, default_column: str) -> Prepared:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select a column")

    label = _pick(list(data.columns), column, default_column)
    series = _from_pandas_series(pd, data[label], None)

    return Prepared(
        series.values,
        lambda out, name: pd.DataFrame({name: out}, index=data.index),
    )


def _from_column(value: object, key: object) -> Prepared:
    """Normalizes one column of a dict (list, tuple, array, or Series)."""
    if isinstance(value, np.ndarray):
        return _from_array(value, None)
    if isinstance(value, list | tuple):
        return _from_sequence(value, None)

    pd = sys.modules.get("pandas")
    if pd is not None and isinstance(value, pd.Series):
        return _from_pandas_series(pd, value, None)

    raise TypeError(
        f"column {key!r} must be a list, tuple, NumPy array or pandas Series, "
        f"got {type(value).__name__}"
    )


def _from_mapping(data: Mapping, column: str | None, default_column: str) -> Prepared:
    key = _pick(list(data), column, default_column)
    inner = _from_column(data[key], key)

    return Prepared(inner.values, lambda out, name: {name: inner.restore(out, name)})


def _nulls(values: Float64Array) -> list[float | None]:
    """Python floats with NaN replaced by None, since JSON has no NaN."""
    boxed = values.astype(object)
    boxed[np.isnan(values)] = None
    return boxed.tolist()


def _from_json(data: str | bytes | bytearray, column: str | None, default_column: str) -> Prepared:
    """Accepts a JSON array of numbers, array of records, or object of arrays.

    `null` is a gap (NaN). The result is returned as JSON of the same shape
    and the same type (str or bytes), with NaN written as `null`.
    """
    try:
        parsed = json.loads(data)
    except ValueError as error:  # JSONDecodeError and UnicodeDecodeError
        raise ValueError(f"invalid JSON input: {error}") from error

    as_bytes = not isinstance(data, str)

    def dump(obj: Any) -> str | bytes:
        text = json.dumps(obj, allow_nan=False, separators=(",", ":"))
        return text.encode() if as_bytes else text

    if isinstance(parsed, list):
        records = sum(isinstance(row, dict) for row in parsed)

        if 0 < records < len(parsed):
            raise TypeError("JSON array mixes records and numbers; use one or the other")

        if records:
            key = _pick(list(parsed[0]), column, default_column)
            values = _from_sequence([row.get(key) for row in parsed], None).values

            return Prepared(values, lambda out, name: dump([{name: v} for v in _nulls(out)]))

        _reject_column(column, "JSON array")
        values = _from_sequence(parsed, None).values

        return Prepared(values, lambda out, _name: dump(_nulls(out)))

    if isinstance(parsed, dict):  # columns
        key = _pick(list(parsed), column, default_column)

        if not isinstance(parsed[key], list):
            raise TypeError(f"JSON column {key!r} must be an array of numbers")

        values = _from_sequence(parsed[key], None).values

        return Prepared(values, lambda out, name: dump({name: _nulls(out)}))

    raise TypeError(
        "JSON input must be an array of numbers, an array of records, or an object of arrays"
    )
