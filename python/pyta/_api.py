"""Shared execution boundary between the public API and the native module."""

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np

from ._native import MAX_ABS_INPUT
from ._types import Float64Array, Prepared
from ._validation import normalize, validate_period

type NativeIndicator = Callable[[Float64Array, int], Float64Array]
type NativeBatchIndicator = Callable[[list[Float64Array], int], list[Float64Array | Exception]]


def run(
    native: NativeIndicator,
    label: str,
    data: object,
    period: object,
    column: str | None,
    default_column: str,
) -> Any:
    """Validates inputs, runs one single-series indicator, and restores the container.

    `default_column` is the column role the indicator calculates on; it is used
    when the caller passes no `column` and the input has more than one.
    """
    period = validate_period(period)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    prepared = normalize(data, column, default_column)
    result = _calculate(native, prepared.values, period)

    return prepared.restore(result, f"{label}_{period}")


def _leading_nan_count(values: Float64Array) -> int:
    """Number of NaN values before the first non-NaN value."""
    # The common case (no leading gap) is decided in O(1).
    if values.shape[0] == 0 or not np.isnan(values[0]):
        return 0

    valid = ~np.isnan(values)

    if not valid.any():
        return values.shape[0]

    return int(valid.argmax())


def _trim(values: Float64Array) -> tuple[int, Float64Array]:
    """Splits off a leading NaN run, returning its length and the remaining values.

    Leading NaNs (for example the warm-up of another indicator) are skipped so
    indicators can be chained. NaN after the first valid value is rejected.
    """
    first = _leading_nan_count(values)

    if first == 0:
        return 0, values

    if first == values.shape[0]:
        raise ValueError("input contains no valid values; every value is NaN or missing")

    valid = values[first:]
    # Same test as Rust's validation; false for NaN and infinity too.
    bad = np.flatnonzero(~(np.abs(valid) <= MAX_ABS_INPUT))

    if bad.size:
        # Rust would report an index relative to the trimmed slice.
        index = first + int(bad[0])

        if np.isfinite(values[index]):
            limit = f"{MAX_ABS_INPUT:.0e}".replace("e+", "e")
            raise ValueError(
                f"value at index {index} is too large in magnitude; "
                f"values must be between -{limit} and {limit}"
            )

        raise ValueError(
            f"non-finite value (NaN or infinity) at index {index}; "
            "only leading NaN values are skipped"
        )

    return first, valid


def _pad(result: Float64Array, first: int, length: int) -> Float64Array:
    """Restores a skipped leading NaN run in front of a result."""
    if first == 0:
        return result

    padded = np.empty(length, dtype=np.float64)
    padded[:first] = np.nan
    padded[first:] = result

    return padded


def _calculate(native: NativeIndicator, values: Float64Array, period: int) -> Float64Array:
    """Runs the native calculation, skipping and re-padding a leading NaN run."""
    first, valid = _trim(values)

    return _pad(native(valid, period), first, values.shape[0])


def run_batch(
    native: NativeBatchIndicator,
    label: str,
    datasets: object,
    period: object,
    column: str | None,
    default_column: str,
) -> Any:
    """Runs one indicator over many datasets and returns results in the same shape.

    `period` and `column` are shared by every dataset, so an invalid one raises.
    A dataset that is malformed or fails to calculate is not raised: its
    exception is returned in its place so the other datasets still complete.
    """
    period = validate_period(period)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    if isinstance(datasets, Mapping):
        keys: list[Any] | None = list(datasets)
        items = list(datasets.values())
    elif isinstance(datasets, list):
        keys = None
        items = datasets
    else:
        raise TypeError(
            f"datasets must be a list or a mapping of datasets, got {type(datasets).__name__}"
        )

    outcomes: list[Any] = [None] * len(items)
    pending: list[tuple[int, Prepared, int]] = []
    arrays: list[Float64Array] = []

    # Python cleans and validates each dataset; a malformed one fails alone.
    for position, item in enumerate(items):
        try:
            prepared = normalize(item, column, default_column)
            first, valid = _trim(prepared.values)
        except (TypeError, ValueError) as error:
            outcomes[position] = error
            continue

        pending.append((position, prepared, first))
        arrays.append(valid)

    results = native(arrays, period) if arrays else []

    for (position, prepared, first), result in zip(pending, results, strict=True):
        if isinstance(result, BaseException):
            outcomes[position] = result
        else:
            padded = _pad(result, first, prepared.values.shape[0])
            outcomes[position] = prepared.restore(padded, f"{label}_{period}")

    return outcomes if keys is None else dict(zip(keys, outcomes, strict=True))
