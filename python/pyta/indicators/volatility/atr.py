"""ATR, a volatility indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_period

#: ATR's inputs, in the order `_native.atr` takes them and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: ATR's output name; title-case input gives "ATR".
OUTPUTS = ("atr",)
_NAMES = OutputNames("atr", OUTPUTS, abbreviations=("atr",))


@overload
def atr[T](
    data: T,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def atr(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def atr(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Average True Range (Wilder; TA-Lib convention).

    The true range of a row is the largest of high - low, |high - previous
    close| and |low - previous close|; the first row has none. The first ATR is
    the mean of the true ranges of rows 1 to `period`; each later one is
    Wilder's smoothing, (previous * (period - 1) + true range) / period. Needs
    at least `period + 1` rows. The first `period` results are NaN (warm-up). A
    flat series gives 0.

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            or JSON (array of records or object of arrays) holding at least
            those columns (others are ignored), or unnamed columns in the order
            high, low, close: a 2-D NumPy array of shape (rows, 3) or a tuple
            of three arrays.
        period: Number of true ranges in the first average and Wilder's
            smoothing period, at least 1.
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in single-column
            indicators. By default the columns are found by role.
        column: Not valid here (ATR uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A DataFrame, dict, or JSON object holds one "atr"
        column, cased like the input's columns ("ATR" for "HIGH, LOW, CLOSE"
        or "High, Low, Close"; see docs/API.md); a dict keeps the high
        column's container type;
        a 2-D array gives a 1-D array and a tuple a tuple. JSON writes NaN as
        null. Rows before the last leading NaN of any column are skipped and
        carried over as NaN, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; invalid period; a required column missing (the message
            names the required and the available columns); an invalid `columns=` or any `column=`;
            NaN after the leading run, or a non-finite or out-of-range value; high below low on a
            row; or fewer than `period + 1` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns(_native.atr, _NAMES, data, params, columns, SLOTS, column, output)


def atr_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Average True Range of many datasets.

    See `pyta.atr` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Wilder's smoothing period, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (ATR uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.atr`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; invalid `period`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns_batch(
        _native.atr_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
