"""Money Flow Index, a momentum indicator on high, low, close and volume (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, VOLUME, Slot, validate_int

#: MFI's inputs, in the order `_native.mfi` takes them and unnamed input uses.
SLOTS = (
    Slot("high", (HIGH,)),
    Slot("low", (LOW,)),
    Slot("close", (CLOSE, ADJ_CLOSE)),
    Slot("volume", (VOLUME,)),
)

#: MFI's output name; title-case input gives "MFI".
OUTPUTS = ("mfi",)
_NAMES = OutputNames("mfi", OUTPUTS, abbreviations=("mfi",))


def _params(period: object) -> tuple[int]:
    """Validates MFI's `period`: at least 2 (TA-Lib's minimum)."""
    return (validate_int("period", period, 2),)


@overload
def mfi[T](
    data: T,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def mfi(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def mfi(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Money Flow Index (Gene Quong and Avrum Soudack), as TA-Lib's `MFI`.

    Each row's money flow is its typical price, (high + low + close) / 3,
    times its volume: positive when the typical price rose from the previous
    row, negative when it fell, neither when it is unchanged (within
    rounding). MFI is 100 * positive / (positive + negative) over the last
    `period` rows, from 0 to 100; a window with no money flow at all gives
    0, as TA-Lib 0.8.3 does. Needs at least `period + 1` rows. The first
    `period` results are NaN (warm-up).

    Args:
        data: High, low, close and volume: a pandas DataFrame, dict of
            columns, JSON (array of records or object of arrays) or CSV text
            holding at least those columns (others are ignored; adj_close
            stands in for a missing close), or unnamed columns in the order
            high, low, close, volume: a 2-D NumPy array or list of lists with
            4 columns, or a tuple of four arrays.
        period: Rows of money flow in each sum, at least 2 (default 14).
        columns: The four columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close; volume). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (MFI uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values between
        0 and 100 and the same length. A DataFrame, dict, or JSON object holds
        one "mfi" column, cased like the input's columns ("MFI" for
        "HIGH, LOW, CLOSE, VOLUME" or "High, Low, Close, Volume"; see
        docs/API.md); a dict keeps the high column's container type; a 2-D
        array gives a 1-D array and a tuple a tuple. JSON writes NaN as null.
        Rows before the last leading NaN of any column are skipped and carried
        over as NaN, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; `period` below 2; a required column
            missing (the message names the required and the available columns);
            an invalid `columns=` or any `column=`; NaN after the leading run,
            or a non-finite or out-of-range value; high below low or a negative
            volume on a row; or fewer than `period + 1` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(period)
    return run_columns(_native.mfi, _NAMES, data, params, columns, SLOTS, column, output)


def mfi_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Money Flow Index of many datasets.

    See `pyta.mfi` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows of money flow in each sum, at least 2, shared by every
            dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (MFI uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.mfi`;
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
        _native.mfi_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
