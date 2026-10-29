"""DEMA, a trend indicator (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_period

#: DEMA's output name; title-case input gives "DEMA".
OUTPUTS = ("dema",)
_NAMES = OutputNames("dema", OUTPUTS, abbreviations=("dema",))


@overload
def dema[T](
    data: T,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def dema(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def dema(
    data: object,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """Double Exponential Moving Average (Mulloy; TA-Lib convention).

    `DEMA = 2 * EMA1 - EMA2`, where EMA1 is the `period` EMA of the prices and
    EMA2 the `period` EMA of EMA1, each seeded with the simple average of its
    first `period` inputs (TA-Lib's seed). Needs at least `2 * period - 1`
    values. The first `2 * (period - 1)` results are NaN (warm-up). `period=1`
    returns the input unchanged.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        period: Period of both EMAs, at least 1 (TA-Lib's default, 30).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (DEMA uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "dema"; a
        DataFrame, dict, or JSON object holds one "dema" column; JSON
        writes NaN as null. The name follows the input column's casing
        ("DEMA" for "CLOSE" or "Close"; see docs/API.md). Leading NaN in the
        input is skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: An unknown `output`; invalid period, a `columns=`, empty,
            non-finite or out-of-range input, or fewer than `2 * period - 1`
            values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(
        _native.dema, _NAMES, data, (validate_period(period),), column, CLOSE, columns, output
    )


def dema_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 30,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Double Exponential Moving Average of many datasets.

    See `pyta.dema` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Period of both EMAs, at least 1, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (DEMA uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.dema`;
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
    return run_batch(_native.dema_batch, _NAMES, datasets, params, column, CLOSE, columns, output)
