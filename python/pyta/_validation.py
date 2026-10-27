"""Input normalization and parameter validation.

Every supported input container is reduced to one 1-D, C-contiguous float64
array, together with a function that rebuilds the caller's container from a
result. Element-level checks (finite, non-empty) stay in Rust.
"""

import json
import operator
import sys
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

import numpy as np
from pydantic import Field, TypeAdapter

from ._types import Float64Array, Prepared

_MAX_PERIOD = 2**31 - 1
_PERIOD = TypeAdapter(Annotated[int, Field(ge=1, le=_MAX_PERIOD)])

_DEFAULT_COLUMN = "close"
_ALIASES: dict[str, tuple[str, ...]] = {
    "close": ("close", "closing", "close_price", "closing_price"),
}


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

    return _PERIOD.validate_python(index)


def normalize(data: object, column: str | None = None) -> Prepared:
    """Converts any supported container to a `Prepared` float64 series."""
    if isinstance(data, str | bytes | bytearray):
        return _from_json(data, column)
    if isinstance(data, np.ndarray):
        return _from_array(data, column)
    if isinstance(data, list | tuple):
        return _from_sequence(data, column)
    if isinstance(data, Mapping):
        return _from_mapping(data, column)

    # pandas is only inspected if the caller has already imported it, so
    # `import pyta` never loads it and a missing pandas is never an error.
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(data, pd.DataFrame):
            return _from_pandas_frame(pd, data, column)
        if isinstance(data, pd.Series):
            return _from_pandas_series(pd, data, column)

    raise TypeError(
        f"unsupported input type {type(data).__name__}; expected a list, tuple, NumPy array, "
        "pandas Series or DataFrame, dict, or JSON string"
    )


# --- column selection -----------------------------------------------------------------------


def _normalize_name(name: object) -> str:
    return str(name).strip().casefold()


def _pick(keys: Sequence[object], column: str | None) -> object:
    """Chooses one key: explicit `column`, else the only key, else 'close'."""
    lookup: dict[str, object] = {}

    for key in keys:
        normalized = _normalize_name(key)

        if normalized in lookup:
            raise ValueError(
                f"column names {lookup[normalized]!r} and {key!r} are the same "
                "after trimming whitespace and ignoring case"
            )

        lookup[normalized] = key

    if column is None and len(lookup) == 1:
        return next(iter(lookup.values()))

    wanted = _normalize_name(_DEFAULT_COLUMN if column is None else column)

    for candidate in _ALIASES.get(wanted, (wanted,)):
        if candidate in lookup:
            return lookup[candidate]

    available = ", ".join(repr(key) for key in keys)

    if column is None:
        raise ValueError(
            f"no 'close' column found; pass column=... (available columns: {available})"
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
    except ValueError as error:  # ragged nested sequences
        raise ValueError(f"expected a flat sequence of numbers: {error}") from error

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


def _from_pandas_frame(pd: Any, data: Any, column: str | None) -> Prepared:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select a column")

    label = _pick(list(data.columns), column)
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


def _from_mapping(data: Mapping, column: str | None) -> Prepared:
    key = _pick(list(data), column)
    inner = _from_column(data[key], key)

    return Prepared(inner.values, lambda out, name: {name: inner.restore(out, name)})


def _nulls(values: Float64Array) -> list[float | None]:
    """Python floats with NaN replaced by None, since JSON has no NaN."""
    boxed = values.astype(object)
    boxed[np.isnan(values)] = None
    return boxed.tolist()


def _from_json(data: str | bytes | bytearray, column: str | None) -> Prepared:
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
        if parsed and all(isinstance(row, dict) for row in parsed):  # records
            key = _pick(list(parsed[0]), column)
            values = _from_sequence([row.get(key) for row in parsed], None).values

            return Prepared(values, lambda out, name: dump([{name: v} for v in _nulls(out)]))

        _reject_column(column, "JSON array")
        values = _from_sequence(parsed, None).values

        return Prepared(values, lambda out, _name: dump(_nulls(out)))

    if isinstance(parsed, dict):  # columns
        key = _pick(list(parsed), column)

        if not isinstance(parsed[key], list):
            raise TypeError(f"JSON column {key!r} must be an array of numbers")

        values = _from_sequence(parsed[key], None).values

        return Prepared(values, lambda out, name: dump({name: _nulls(out)}))

    raise TypeError(
        "JSON input must be an array of numbers, an array of records, or an object of arrays"
    )
