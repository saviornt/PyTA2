"""VWAP (Volume-Weighted Average Price), a volume indicator on high, low, close and volume."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, VOLUME, Slot

#: VWAP's inputs, in the order `_native.vwap` takes them and unnamed input uses.
SLOTS = (
    Slot("high", (HIGH,)),
    Slot("low", (LOW,)),
    Slot("close", (CLOSE, ADJ_CLOSE)),
    Slot("volume", (VOLUME,)),
)

#: VWAP's output name; title-case input gives "VWAP".
OUTPUTS = ("vwap",)
_NAMES = OutputNames("vwap", OUTPUTS, abbreviations=("vwap",))


@overload
def vwap[T](
    data: T,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def vwap(
    data: object,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def vwap(
    data: object,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Volume-Weighted Average Price, cumulative from the first row.

    Each row's typical price, (high + low + close) / 3, is weighted by its
    volume: VWAP = sum(typical price * volume) / sum(volume) over every row so
    far. There is no session reset; slice the data per session (for example
    with a pandas groupby by date) for the intraday convention. Rows before
    the first row with volume are NaN. No parameters: one row is enough.

    Args:
        data: High, low, close and volume: a pandas DataFrame, dict of
            columns, JSON (array of records or object of arrays) or CSV text
            holding at least those columns (others are ignored; adj_close
            stands in for a missing close), or unnamed columns in the order
            high, low, close, volume: a 2-D NumPy array or list of lists with
            4 columns, or a tuple of four arrays.
        columns: The four columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close; volume). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (VWAP uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A DataFrame, dict, or JSON object holds one "vwap"
        column, cased like the input's columns ("VWAP" for "HIGH, LOW, CLOSE,
        VOLUME" or "High, Low, Close, Volume"; see docs/API.md); a dict keeps
        the high column's container type; a 2-D array gives a 1-D array and a
        tuple a tuple. JSON writes NaN as null. Rows before the last leading
        NaN of any column are skipped and carried over as NaN, so indicators
        can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `columns` type.
        ValueError: An unknown `output`; a required column missing (the
            message names the required and the available columns); an invalid
            `columns=` or any `column=`; NaN after the leading run, or a
            non-finite or out-of-range value; or high below low or a negative
            volume on a row.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns(_native.vwap, _NAMES, data, (), columns, SLOTS, column, output)


def vwap_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Volume-Weighted Average Price of many datasets (for example, one per session).

    See `pyta.vwap` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (VWAP uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.vwap`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `columns` has the
            wrong type.
        ValueError: An unknown `output`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns_batch(
        _native.vwap_batch, _NAMES, datasets, (), columns, SLOTS, column, output
    )
