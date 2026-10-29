"""STDDEV, a volatility indicator (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_int, validate_positive_float

#: STDDEV's output name; title-case input gives "STDDEV".
OUTPUTS = ("stddev",)
_NAMES = OutputNames("stddev", OUTPUTS, abbreviations=("stddev",))


def _params(period: object, k: object) -> tuple[int, float]:
    """Validates STDDEV's parameters: `period` at least 2 (TA-Lib's minimum), `k` above 0."""
    return (validate_int("period", period, 2), validate_positive_float("k", k))


@overload
def stddev[T](
    data: T,
    period: int = 5,
    k: float = 1.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def stddev(
    data: object,
    period: int = 5,
    k: float = 1.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def stddev(
    data: object,
    period: int = 5,
    k: float = 1.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """Rolling population standard deviation, multiplied by `k` (TA-Lib's STDDEV).

    Each value is the standard deviation of the last `period` values,
    dividing by `period` (population, not sample), times `k`. Needs at least
    `period` values. The first `period - 1` results are NaN (warm-up). A flat
    window gives exactly 0.

    Args:
        data: Prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, JSON (str or bytes) or CSV text.
        period: Number of values in each window, at least 2.
        k: Multiplier (TA-Lib's `nbdev`), a finite number above 0; an int is
            accepted.
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (STDDEV uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "stddev"; a
        DataFrame, dict, or JSON object holds one "stddev" column; JSON
        writes NaN as null. The name follows the input column's casing
        ("STDDEV" for "CLOSE" or "Close"; see docs/API.md). Leading NaN in the
        input is skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, or a `period` or `k` of the
            wrong type.
        ValueError: An unknown `output`; `period` below 2, `k` not a finite
            number above 0, a `columns=`, empty, non-finite or out-of-range
            input, or fewer than `period` values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(_native.stddev, _NAMES, data, _params(period, k), column, CLOSE, columns, output)


def stddev_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 5,
    k: float = 1.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Rolling population standard deviation of many datasets.

    See `pyta.stddev` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of values in each window, shared by every dataset.
        k: Multiplier, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (STDDEV uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.stddev`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period`, `k` or
            `column` has the wrong type.
        ValueError: An unknown `output`; invalid `period` or `k`, or a `columns=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_batch(
        _native.stddev_batch, _NAMES, datasets, _params(period, k), column, CLOSE, columns, output
    )
