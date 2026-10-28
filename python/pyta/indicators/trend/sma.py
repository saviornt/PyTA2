"""SMA, a trend indicator (single call and batch)."""

from typing import Any

from pyta import _native
from pyta._api import run, run_batch
from pyta._validation import CLOSE


def sma[T](data: T, period: int, *, column: str | None = None, columns: None = None) -> T:
    """Simple Moving Average.

    Each value is the mean of the current price and the preceding
    `period - 1` prices. The first `period - 1` results are NaN (warm-up).

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Window length, an integer of at least 1.
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (SMA uses one column); raises ValueError.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "sma_<period>"; a
        DataFrame, dict, or JSON object holds one "sma_<period>" column; JSON
        writes NaN as null. Leading NaN in the input is skipped and carried
        over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: Invalid period, a `columns=`, empty, non-finite or out-of-range input, or a
            period larger than the series.
    """
    return run(_native.sma, "sma", data, period, column, CLOSE, columns)


def sma_batch[D: (list[Any], dict[Any, Any])](
    datasets: D, period: int, *, column: str | None = None, columns: None = None
) -> D:
    """Simple Moving Average of many datasets.

    See `pyta.sma` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Window length, an integer of at least 1, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (SMA uses one column); raises ValueError.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `column`
            has the wrong type.
        ValueError: Invalid `period`, or a `columns=`.
    """
    return run_batch(_native.sma_batch, "sma", datasets, period, column, CLOSE, columns)
