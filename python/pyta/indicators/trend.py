"""Trend indicators."""

from .. import _native
from .._api import run


def sma[T](data: T, period: int, *, column: str | None = None) -> T:
    """Simple Moving Average.

    Each value is the mean of the current price and the preceding
    `period - 1` prices. The first `period - 1` results are NaN (warm-up).

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Window length, an integer of at least 1.
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to "close", or the only column if there is just one.
            Names ignore case and surrounding whitespace.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "sma_<period>"; a
        DataFrame, dict, or JSON object holds one "sma_<period>" column; JSON
        writes NaN as null. Leading NaN in the input is skipped and carried
        over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: Invalid period, empty or non-finite input, or a period
            larger than the series.
    """
    return run(_native.sma, "sma", data, period, column)
