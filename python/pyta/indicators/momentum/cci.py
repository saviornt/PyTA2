"""CCI, a momentum indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_period

#: CCI's inputs, in the order `_native.cci` takes them and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: CCI's output name; title-case input gives "CCI".
OUTPUTS = ("cci",)
_NAMES = OutputNames("cci", OUTPUTS, abbreviations=("cci",))


def cci[T](
    data: T,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
) -> T:
    """Commodity Channel Index (TA-Lib convention).

    The typical price is (high + low + close) / 3; CCI is its distance from its
    `period` mean, divided by 0.015 times the mean absolute deviation. Needs at
    least `period` rows. The first `period - 1` results are NaN (warm-up). A
    flat window gives 0.

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            or JSON (array of records or object of arrays) holding at least
            those columns (others are ignored), or unnamed columns in the order
            high, low, close: a 2-D NumPy array of shape (rows, 3) or a tuple
            of three arrays.
        period: Number of typical prices in each window, at least 1.
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in single-column
            indicators. By default the columns are found by role.
        column: Not valid here (CCI uses several columns); raises ValueError.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A DataFrame, dict, or JSON object holds one "cci"
        column, cased like the input's columns ("CCI" for "HIGH, LOW, CLOSE"
        or "High, Low, Close"; see docs/API.md); a dict keeps the high
        column's container type;
        a 2-D array gives a 1-D array and a tuple a tuple. JSON writes NaN as
        null. Rows before the last leading NaN of any column are skipped and
        carried over as NaN, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: Invalid period; a required column missing (the message
            names the required and the available columns); an invalid
            `columns=` or any `column=`; NaN after the leading run, or a
            non-finite or out-of-range value; high below low on a row; or
            fewer than `period` rows.
    """
    params = (validate_period(period),)
    return run_columns(_native.cci, _NAMES, data, params, columns, SLOTS, column)


def cci_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
) -> D:
    """Commodity Channel Index of many datasets.

    See `pyta.cci` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of typical prices in each window, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (CCI uses several columns); raises ValueError.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: Invalid `period`, or a `column=`.
    """
    params = (validate_period(period),)
    return run_columns_batch(_native.cci_batch, _NAMES, datasets, params, columns, SLOTS, column)
