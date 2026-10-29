"""Parabolic SAR, a trend indicator on high and low (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import HIGH, LOW, Slot, validate_ascending, validate_positive_float

#: SAR's inputs, in the order `_native.sar` takes them and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)))

#: SAR's output name; title-case input gives "SAR".
OUTPUTS = ("sar",)
_NAMES = OutputNames("sar", OUTPUTS, abbreviations=("sar",))


def _params(acceleration: object, maximum: object) -> tuple[float, float]:
    """Validates SAR's parameters: both finite and above 0, `acceleration <= maximum`."""
    params = (
        validate_positive_float("acceleration", acceleration),
        validate_positive_float("maximum", maximum),
    )
    validate_ascending(("acceleration", params[0]), ("maximum", params[1]), strict=False)
    return params


@overload
def sar[T](
    data: T,
    acceleration: float = 0.02,
    maximum: float = 0.2,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def sar(
    data: object,
    acceleration: float = 0.02,
    maximum: float = 0.2,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def sar(
    data: object,
    acceleration: float = 0.02,
    maximum: float = 0.2,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Parabolic SAR, Wilder's stop and reverse (TA-Lib's convention).

    The SAR trails the price from below in an uptrend and from above in a
    downtrend. Each row it moves towards the trend's extreme point (the highest
    high or lowest low so far) by the acceleration factor, which starts at
    `acceleration` and grows by `acceleration` at every new extreme up to
    `maximum`; it is never placed inside the last two rows' range. When a row's
    low reaches the SAR in an uptrend (or its high in a downtrend), the trend
    reverses and the SAR jumps to the old extreme point. The first direction is
    TA-Lib's: short when row 1's low falls further than its high rises, else
    long. Matches TA-Lib's SAR within one unit in the last place. Needs at
    least 2 rows; the first result is NaN (warm-up).

    Args:
        data: High and low prices: a pandas DataFrame, dict of columns, JSON
            (array of records or object of arrays) or CSV text holding at least
            those columns (others are ignored), or unnamed columns in the order
            high, low: a 2-D NumPy array or list of lists with 2 columns, or a
            tuple of two arrays.
        acceleration: The acceleration factor's start and its step, a finite
            number above 0 and at most `maximum` (default 0.02).
        maximum: The acceleration factor's cap, a finite number above 0
            (default 0.2).
        columns: The two columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low). Names follow
            the same rules as `column=` in single-column indicators. By default
            the columns are found by role.
        column: Not valid here (SAR uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values and the
        same length. A DataFrame, dict, or JSON object holds one "sar" column,
        cased like the input's columns ("SAR" for "HIGH, LOW" or "High, Low";
        see docs/API.md); a dict keeps the high column's container type; a 2-D
        array gives a 1-D array and a tuple a tuple. JSON writes NaN as null.
        Rows before the last leading NaN of either column are skipped and
        carried over as NaN, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `acceleration`, `maximum` or `columns` type (bool included).
        ValueError: An unknown `output`; `acceleration` or `maximum` not a
            finite number above 0, or `acceleration` above `maximum` (TA-Lib
            lowers it silently); a required column missing (the message names
            the required and the available columns); an invalid `columns=` or
            any `column=`; NaN after the leading run, or a non-finite or
            out-of-range value; high below low on a row; or fewer than 2 rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(acceleration, maximum)
    return run_columns(_native.sar, _NAMES, data, params, columns, SLOTS, column, output)


def sar_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    acceleration: float = 0.02,
    maximum: float = 0.2,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Parabolic SAR of many datasets.

    See `pyta.sar` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        acceleration: The acceleration factor's start and step, shared by every
            dataset.
        maximum: The acceleration factor's cap, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (SAR uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.sar`; None
            (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `acceleration`,
            `maximum` or `columns` has the wrong type.
        ValueError: An unknown `output`; an invalid `acceleration` or
            `maximum`, `acceleration` above `maximum`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(acceleration, maximum)
    return run_columns_batch(
        _native.sar_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
