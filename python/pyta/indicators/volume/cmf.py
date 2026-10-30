"""Chaikin Money Flow, a volume indicator on high, low, close and volume."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, VOLUME, Slot, validate_period

#: CMF's inputs, in the order `_native.cmf` takes them and unnamed input uses.
SLOTS = (
    Slot("high", (HIGH,)),
    Slot("low", (LOW,)),
    Slot("close", (CLOSE, ADJ_CLOSE)),
    Slot("volume", (VOLUME,)),
)

#: CMF's output name; title-case input gives "CMF".
OUTPUTS = ("cmf",)
_NAMES = OutputNames("cmf", OUTPUTS, abbreviations=("cmf",))


@overload
def cmf[T](
    data: T,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def cmf(
    data: object,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def cmf(
    data: object,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Chaikin Money Flow (Marc Chaikin), as StockCharts defines it.

    Each row's money-flow multiplier, ((close - low) - (high - close)) /
    (high - low), runs from -1 (close at the low) to 1 (close at the high),
    0 for a one-price bar; times the row's volume it is the money-flow
    volume. CMF is the sum of the money-flow volumes over the last `period`
    rows, the current row included, divided by the sum of their volumes:
    from -1 to 1. A window without any volume gives NaN. Needs at least
    `period` rows. The first `period - 1` results are NaN (warm-up).

    Args:
        data: High, low, close and volume: a pandas DataFrame, dict of
            columns, JSON (array of records or object of arrays) or CSV text
            holding at least those columns (others are ignored; adj_close
            stands in for a missing close), or unnamed columns in the order
            high, low, close, volume: a 2-D NumPy array or list of lists with
            4 columns, or a tuple of four arrays.
        period: Rows in each sum, at least 1 (default 20, StockCharts'; TA-Lib
            has no CMF).
        columns: The four columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close; volume). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (CMF uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values between
        -1 and 1 and the same length. A DataFrame, dict, or JSON object holds
        one "cmf" column, cased like the input's columns ("CMF" for "HIGH,
        LOW, CLOSE, VOLUME" or "High, Low, Close, Volume"; see docs/API.md); a
        dict keeps the high column's container type; a 2-D array gives a 1-D
        array and a tuple a tuple. JSON writes NaN as null. Rows before the
        last leading NaN of any column are skipped and carried over as NaN, so
        indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; an invalid `period`; a required
            column missing (the message names the required and the available
            columns); an invalid `columns=` or any `column=`; NaN after the
            leading run, or a non-finite or out-of-range value; high below low
            or a negative volume on a row; or fewer than `period` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns(_native.cmf, _NAMES, data, params, columns, SLOTS, column, output)


def cmf_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Chaikin Money Flow of many datasets.

    See `pyta.cmf` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows in each sum, at least 1, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (CMF uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.cmf`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; an invalid `period`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns_batch(
        _native.cmf_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
