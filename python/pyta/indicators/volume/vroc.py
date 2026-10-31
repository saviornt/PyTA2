"""Volume ROC (Volume Rate of Change), a volume indicator on one column (single call and batch)."""

from typing import Any, overload

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import VOLUME, validate_period

#: Volume ROC's output name; title-case input gives "VROC".
OUTPUTS = ("vroc",)
_NAMES = OutputNames("vroc", OUTPUTS, abbreviations=("vroc",))


@overload
def vroc[T](
    data: T,
    period: int = 10,
    *,
    column: str | None = None,
    columns: None = None,
    output: None = None,
) -> T: ...


@overload
def vroc(
    data: object,
    period: int = 10,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output,
) -> Any: ...


def vroc(
    data: object,
    period: int = 10,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """Volume Rate of Change: TA-Lib's `ROC` applied to volume.

    The percentage change from the volume `period` rows earlier:
    (volume / earlier volume - 1) * 100. When the earlier volume is zero
    relative to the current one (at most 1e-14 of its magnitude, exactly 0
    included) the result is 0, so every result is finite. Needs at least
    `period + 1` values. The first `period` results are NaN (warm-up).

    Args:
        data: Volumes as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, JSON or CSV (str or bytes).
        period: Rows back to the volume compared with, at least 1 (TA-Lib's
            ROC default, 10; StockCharts uses 12 or 25).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the volume column, or the only column if there is
            just one. Must be a standard name (open, high, low, close,
            adj_close, volume) or an alias; case, whitespace and . _ - are
            ignored. See docs/API.md.
        columns: Not valid here (Volume ROC uses one column); raises
            ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A Series keeps its index and is named "vroc"; a
        DataFrame, dict, or JSON object holds one "vroc" column; JSON writes
        NaN as null. The name follows the input column's casing ("VROC" for
        "VOLUME" or "Volume"; see docs/API.md). Leading NaN in the input is
        skipped and carried over, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type, dtype, or period type.
        ValueError: An unknown `output`; invalid period, a `columns=`, empty,
            non-finite or out-of-range input, a negative value in a column
            named as volume, or fewer than `period + 1` values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(
        _native.vroc,
        _NAMES,
        data,
        (validate_period(period),),
        column,
        VOLUME,
        columns,
        output,
    )


def vroc_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 10,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Volume Rate of Change of many datasets.

    See `pyta.vroc` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows back to the volume compared with, at least 1, shared by
            every dataset.
        column: Column to use for every dataset that has columns (the volume
            column by default).
        columns: Not valid here (Volume ROC uses one column); raises
            ValueError.
        output: Container to return for every dataset, as for `pyta.vroc`;
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
    return run_batch(_native.vroc_batch, _NAMES, datasets, params, column, VOLUME, columns, output)
