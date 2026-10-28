"""Momentum indicator: RSI (single call and batch)."""

from typing import Any

from pyta import _native
from pyta._api import run, run_batch
from pyta._validation import CLOSE


def rsi[T](data: T, period: int = 14, *, column: str | None = None) -> T:
    """Relative Strength Index using Wilder's smoothing.

    Needs at least `period + 1` values. The first `period` results are NaN
    (warm-up). Flat prices give 0, and a series with no losses gives 100.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Number of price changes in the first average, at least 1.
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "rsi_<period>"; a
        DataFrame, dict, or JSON object holds one "rsi_<period>" column; JSON
        writes NaN as null. Leading NaN in the input is skipped and carried
        over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: Invalid period, empty, non-finite or out-of-range input, or fewer than
            `period + 1` values.
    """
    return run(_native.rsi, "rsi", data, period, column, default_column=CLOSE)


def rsi_batch[D: (list[Any], dict[Any, Any])](
    datasets: D, period: int = 14, *, column: str | None = None
) -> D:
    """Relative Strength Index of many datasets.

    See `pyta.rsi` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of price changes in the first average, shared by every dataset.
        column: Column to use for every dataset that has columns.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `column`
            has the wrong type.
        ValueError: Invalid `period`.
    """
    return run_batch(_native.rsi_batch, "rsi", datasets, period, column, default_column=CLOSE)
