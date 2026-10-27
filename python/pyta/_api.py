"""Shared execution boundary between the public API and the native module."""

from collections.abc import Callable
from typing import Any

import numpy as np

from ._types import Float64Array
from ._validation import normalize, validate_period

type NativeIndicator = Callable[[Float64Array, int], Float64Array]


def run(
    native: NativeIndicator,
    label: str,
    data: object,
    period: object,
    column: str | None = None,
) -> Any:
    """Validates inputs, runs one single-series indicator, and restores the container."""
    period = validate_period(period)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    prepared = normalize(data, column)
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


def _calculate(native: NativeIndicator, values: Float64Array, period: int) -> Float64Array:
    """Runs the native calculation, skipping and re-padding a leading NaN run.

    Leading NaNs (for example the warm-up of another indicator) are skipped so
    indicators can be chained. NaN after the first valid value is rejected.
    """
    first = _leading_nan_count(values)

    if first == 0:
        return native(values, period)

    length = values.shape[0]

    if first == length:
        raise ValueError("input contains no valid values")

    valid = values[first:]
    bad = np.flatnonzero(~np.isfinite(valid))

    if bad.size:
        # Rust would report an index relative to the trimmed slice.
        raise ValueError(f"input contains a non-finite value at index {first + int(bad[0])}")

    result = native(valid, period)

    padded = np.empty(length, dtype=np.float64)
    padded[:first] = np.nan
    padded[first:] = result

    return padded
