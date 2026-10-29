"""RSI, a momentum indicator (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_period

#: RSI's output name; title-case input gives "RSI".
OUTPUTS = ("rsi",)
_NAMES = OutputNames("rsi", OUTPUTS, abbreviations=("rsi",))


@overload
def rsi[T](
    data: T,
    period: int = 14,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def rsi(
    data: object,
    period: int = 14,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def rsi(
    data: object,
    period: int = 14,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
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
        columns: Not valid here (RSI uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "rsi"; a
        DataFrame, dict, or JSON object holds one "rsi" column; JSON
        writes NaN as null. The name follows the input column's casing
        ("RSI" for "CLOSE" or "Close"; see docs/API.md). Leading NaN in the
        input is skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: An unknown `output`; invalid period, a `columns=`, empty, non-finite or
            out-of-range input, or fewer than `period + 1` values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(
        _native.rsi, _NAMES, data, (validate_period(period),), column, CLOSE, columns, output
    )


def rsi_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Relative Strength Index of many datasets.

    See `pyta.rsi` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of price changes in the first average, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (RSI uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.rsi`;
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
    return run_batch(_native.rsi_batch, _NAMES, datasets, params, column, CLOSE, columns, output)
