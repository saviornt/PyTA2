"""Momentum indicators."""

from .. import _native
from .._api import run


def rsi[T](data: T, period: int = 14, *, column: str | None = None) -> T:
    """Relative Strength Index using Wilder's smoothing.

    Needs at least `period + 1` values. The first `period` results are NaN
    (warm-up). Flat prices give 0, and a series with no losses gives 100.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Number of price changes in the first average, at least 1.
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to "close", or the only column if there is just one.
            Names ignore case and surrounding whitespace.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "rsi_<period>"; a
        DataFrame, dict, or JSON object holds one "rsi_<period>" column; JSON
        writes NaN as null. Leading NaN in the input is skipped and carried
        over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: Invalid period, empty or non-finite input, or fewer than
            `period + 1` values.
    """
    return run(_native.rsi, "rsi", data, period, column)
