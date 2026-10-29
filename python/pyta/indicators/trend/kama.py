"""KAMA, a trend indicator (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_period

#: KAMA's output name; title-case input gives "KAMA".
OUTPUTS = ("kama",)
_NAMES = OutputNames("kama", OUTPUTS, abbreviations=("kama",))


@overload
def kama[T](
    data: T,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def kama(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def kama(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """Kaufman Adaptive Moving Average (Kaufman; TA-Lib convention).

    The efficiency ratio `ER = |price - price period rows back| / (sum of the
    period one-row absolute changes)` sets the smoothing constant
    `SC = (ER * (2/3 - 2/31) + 2/31) ** 2` (fast 2, slow 30, fixed as in
    TA-Lib), and `KAMA = previous KAMA + SC * (price - previous KAMA)`. The
    first previous KAMA is the price at row `period - 1` (TA-Lib's seed).
    Needs at least `period + 1` values. The first `period` results are NaN
    (warm-up). `period=1` returns the input unchanged.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Rows in the efficiency ratio's window, at least 1 (TA-Lib's
            default, 30; Kaufman used 10).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (KAMA uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "kama"; a
        DataFrame, dict, or JSON object holds one "kama" column; JSON
        writes NaN as null. The name follows the input column's casing
        ("KAMA" for "CLOSE" or "Close"; see docs/API.md). Leading NaN in the
        input is skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: An unknown `output`; invalid period, a `columns=`, empty,
            non-finite or out-of-range input, or fewer than `period + 1`
            values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(
        _native.kama, _NAMES, data, (validate_period(period),), column, CLOSE, columns, output
    )


def kama_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Kaufman Adaptive Moving Average of many datasets.

    See `pyta.kama` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows in the efficiency ratio's window, at least 1, shared by
            every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (KAMA uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.kama`;
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
    return run_batch(_native.kama_batch, _NAMES, datasets, params, column, CLOSE, columns, output)
