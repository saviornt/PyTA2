"""TRIX (triple-smoothed EMA rate of change), a momentum indicator (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_period

#: TRIX's output name; title-case input gives "TRIX".
OUTPUTS = ("trix",)
_NAMES = OutputNames("trix", OUTPUTS, abbreviations=("trix",))


@overload
def trix[T](
    data: T,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def trix(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def trix(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """TRIX (Jack Hutson), as TA-Lib's `TRIX`.

    The one-row rate of change, in percent, of a triple-smoothed EMA: EMA1 of
    the prices, EMA2 of EMA1 and EMA3 of EMA2, all over `period` and each
    seeded with the mean of its input's first `period` values, then
    (EMA3 / previous EMA3 - 1) * 100. A previous EMA3 that is zero relative to
    the current one gives 0, as in `pyta.roc`. Needs at least `3 * period - 1` values. The first
    `3 * (period - 1) + 1` results are NaN (warm-up). The signal line is not
    part of TRIX: take `pyta.ema` of the result.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, JSON or CSV (str or bytes).
        period: Period of each of the three EMAs, at least 1 (TA-Lib's
            default, 30; Hutson and StockCharts use 15).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (TRIX uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "trix"; a
        DataFrame, dict, or JSON object holds one "trix" column; JSON
        writes NaN as null. The name follows the input column's casing
        ("TRIX" for "CLOSE" or "Close"; see docs/API.md). Leading NaN in the
        input is skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: An unknown `output`; invalid period, a `columns=`, empty,
            non-finite or out-of-range input, or fewer than `3 * period - 1`
            values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(
        _native.trix, _NAMES, data, (validate_period(period),), column, CLOSE, columns, output
    )


def trix_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """TRIX of many datasets.

    See `pyta.trix` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Period of each of the three EMAs, at least 1, shared by every
            dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (TRIX uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.trix`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `column`
            has the wrong type.
        ValueError: An unknown `output`; invalid `period`, or a `columns=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_batch(_native.trix_batch, _NAMES, datasets, params, column, CLOSE, columns, output)
