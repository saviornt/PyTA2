"""Williams %R, a momentum indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_int

#: Williams %R's inputs, in the order `_native.willr` takes them and unnamed
#: input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: Williams %R's output name; title-case input gives "WILLR".
OUTPUTS = ("willr",)
_NAMES = OutputNames("willr", OUTPUTS, abbreviations=("willr",))


def _params(period: object) -> tuple[int]:
    """Validates Williams %R's `period`: at least 2 (TA-Lib's minimum)."""
    return (validate_int("period", period, 2),)


@overload
def willr[T](
    data: T,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def willr(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def willr(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Williams %R (Larry Williams), as TA-Lib's `WILLR`.

    %R is -100 * (highest high - close) / (highest high - lowest low) over the
    last `period` rows, the current row included: 0 when the close is at the
    highest high, -100 at the lowest low. A flat window (the range zero within
    rounding) gives 0, and a close outside its window's range is clamped to
    [-100, 0], as TA-Lib 0.8.3 does. Needs at least `period` rows. The first
    `period - 1` results are NaN (warm-up).

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        period: Rows in the highest-high and lowest-low window, at least 2
            (default 14).
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (Williams %R uses several columns); raises
            ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values between
        -100 and 0 and the same length. A DataFrame, dict, or JSON object holds
        one "willr" column, cased like the input's columns ("WILLR" for
        "HIGH, LOW, CLOSE" or "High, Low, Close"; see docs/API.md); a dict
        keeps the high column's container type; a 2-D array gives a 1-D array
        and a tuple a tuple. JSON writes NaN as null. Rows before the last
        leading NaN of any column are skipped and carried over as NaN, so
        indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; `period` below 2; a required column
            missing (the message names the required and the available columns);
            an invalid `columns=` or any `column=`; NaN after the leading run,
            or a non-finite or out-of-range value; high below low on a row; or
            fewer than `period` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(period)
    return run_columns(_native.willr, _NAMES, data, params, columns, SLOTS, column, output)


def willr_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Williams %R of many datasets.

    See `pyta.willr` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows in the highest-high and lowest-low window, at least 2,
            shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (Williams %R uses several columns); raises
            ValueError.
        output: Container to return for every dataset, as for `pyta.willr`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; `period` below 2, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(period)
    return run_columns_batch(
        _native.willr_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
