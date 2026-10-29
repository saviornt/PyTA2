"""Average Directional Index, a trend indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_int

#: ADX's inputs, in the order `_native.adx` takes them and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: ADX's outputs, in the order they are returned. Title-case input gives
#: "ADX", "ADX_Plus_DI", "ADX_Minus_DI" (ADX and DI are abbreviations).
OUTPUTS = ("adx", "adx_plus_di", "adx_minus_di")
_NAMES = OutputNames("adx", OUTPUTS, abbreviations=("adx", "di"))


def _params(period: object) -> tuple[int]:
    """Validates ADX's `period`: at least 2 (TA-Lib's minimum)."""
    return (validate_int("period", period, 2),)


def adx(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Average Directional Index (ADX) with +DI and -DI (Wilder; TA-Lib's convention).

    +DM is the rise of the high over the previous high when it is positive and
    larger than the fall of the low, else 0; -DM is the mirror. Their Wilder
    sums over `period` rows, divided by the Wilder sum of the true range, give
    `adx_plus_di` and `adx_minus_di` (in percent); DX is 100 * |+DI - -DI| /
    (+DI + -DI), and `adx` is its Wilder average, seeded with the mean of the
    first `period` DX values. Identical to TA-Lib's ADX, PLUS_DI and MINUS_DI.
    Needs at least 2 * `period` rows. Each output keeps its own warm-up: the
    first `period` DI values and the first 2 * `period` - 1 ADX values are NaN.

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        period: Wilder's smoothing period for the directional movement, the
            true range and ADX, at least 2 (default 14).
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (ADX uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Three outputs, "adx", "adx_plus_di" and "adx_minus_di" in that order,
        each float64 and the same length as `data`. A DataFrame gives a
        DataFrame with those three columns (index kept); a dict or JSON object
        gives one key per output (dict values keep the high column's container
        type); JSON records get the three keys on every record. A 2-D array or
        a tuple of arrays gives a tuple of three outputs (`adx, plus_di,
        minus_di = pyta.adx(array)`). JSON writes NaN as null. Names follow the
        input's casing ("ADX_PLUS_DI" for "HIGH, LOW, CLOSE", "ADX_Plus_DI" for
        "High, Low, Close"; see docs/API.md). Rows before the last leading NaN
        of any column are skipped and carried over as NaN in every output, so
        indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; `period` below 2; a required column
            missing (the message names the required and the available columns);
            an invalid `columns=` or any `column=`; NaN after the leading run, or
            a non-finite or out-of-range value; high below low on a row; or
            fewer than 2 * `period` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns(_native.adx, _NAMES, data, _params(period), columns, SLOTS, column, output)


def adx_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """ADX, +DI and -DI of many datasets.

    See `pyta.adx` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Wilder's smoothing period, at least 2, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (ADX uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.adx`; None
            (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.adx` returns for its input, or the exception
        explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; an invalid `period`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns_batch(
        _native.adx_batch, _NAMES, datasets, _params(period), columns, SLOTS, column, output
    )
