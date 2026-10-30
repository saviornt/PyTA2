"""On-Balance Volume, a volume indicator on close and volume (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, VOLUME, Slot

#: OBV's inputs, in the order `_native.obv` takes them and unnamed input uses.
SLOTS = (Slot("close", (CLOSE, ADJ_CLOSE)), Slot("volume", (VOLUME,)))

#: OBV's output name; title-case input gives "OBV".
OUTPUTS = ("obv",)
_NAMES = OutputNames("obv", OUTPUTS, abbreviations=("obv",))


@overload
def obv[T](
    data: T,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def obv(
    data: object,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def obv(
    data: object,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """On-Balance Volume (Joseph Granville), as TA-Lib's `OBV`.

    A running total of volume: it starts at the first row's volume, then
    adds the row's volume when the close rose from the previous row,
    subtracts it when the close fell, and is unchanged when the close is
    equal. No parameters and no warm-up: one row is enough.

    Args:
        data: Close and volume: a pandas DataFrame, dict of columns, JSON
            (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order close, volume: a
            2-D NumPy array or list of lists with 2 columns, or a tuple of two
            arrays.
        columns: The two columns to use, in any order, for named input; each
            name is assigned to the input for its role (close or adj_close;
            volume). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (OBV uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A DataFrame, dict, or JSON object holds one "obv"
        column, cased like the input's columns ("OBV" for "CLOSE, VOLUME" or
        "Close, Volume"; see docs/API.md); a dict keeps the close column's
        container type; a 2-D array gives a 1-D array and a tuple a tuple.
        Rows before the last leading NaN of either column are skipped and
        carried over as NaN, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `columns` type.
        ValueError: An unknown `output`; a required column missing (the
            message names the required and the available columns); an invalid
            `columns=` or any `column=`; NaN after the leading run, or a
            non-finite or out-of-range value; or a negative volume on a row.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns(_native.obv, _NAMES, data, (), columns, SLOTS, column, output)


def obv_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """On-Balance Volume of many datasets.

    See `pyta.obv` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (OBV uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.obv`;
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
        _native.obv_batch, _NAMES, datasets, (), columns, SLOTS, column, output
    )
