"""Ultimate Oscillator, a momentum indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any, overload

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_ascending, validate_int

#: The Ultimate Oscillator's inputs, in the order `_native.ultosc` takes them
#: and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: The Ultimate Oscillator's output name; title-case input gives "ULTOSC".
OUTPUTS = ("ultosc",)
_NAMES = OutputNames("ultosc", OUTPUTS, abbreviations=("ultosc",))


def _params(short: object, medium: object, long: object) -> tuple[int, int, int]:
    """Validates the three windows: each at least 1, and `short < medium < long`."""
    params = (
        validate_int("short", short, 1),
        validate_int("medium", medium, 1),
        validate_int("long", long, 1),
    )
    validate_ascending(
        ("short", params[0]), ("medium", params[1]), ("long", params[2]), strict=True
    )
    return params


@overload
def ultosc[T](
    data: T,
    short: int = 7,
    medium: int = 14,
    long: int = 28,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: None = None,
) -> T: ...


@overload
def ultosc(
    data: object,
    short: int = 7,
    medium: int = 14,
    long: int = 28,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output,
) -> Any: ...


def ultosc(
    data: object,
    short: int = 7,
    medium: int = 14,
    long: int = 28,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Ultimate Oscillator (Larry Williams), as TA-Lib's `ULTOSC`.

    Each row's buying pressure is close - true low and its true range
    true high - true low, the true low and high including the previous close.
    Over the last `short`, `medium` and `long` rows the averages are
    sum(pressure) / sum(range), and the oscillator is
    100 * (4 * short average + 2 * medium average + long average) / 7, from
    0 to 100. A window whose true ranges sum to 0 drops its term (the divisor
    stays 7), as TA-Lib 0.8.3 does. Needs at least `long + 1` rows. The first
    `long` results are NaN (warm-up).

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        short: Rows in the shortest window, weighted 4, at least 1 (default 7).
        medium: Rows in the middle window, weighted 2, above `short`
            (default 14).
        long: Rows in the longest window, weighted 1, above `medium`
            (default 28). The windows are not reordered: out of order raises.
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (the Ultimate Oscillator uses several
            columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        The same kind of container as `data`, holding float64 values between
        0 and 100 and the same length. A DataFrame, dict, or JSON object holds
        one "ultosc" column, cased like the input's columns ("ULTOSC" for
        "HIGH, LOW, CLOSE" or "High, Low, Close"; see docs/API.md); a dict
        keeps the high column's container type; a 2-D array gives a 1-D array
        and a tuple a tuple. JSON writes NaN as null. Rows before the last
        leading NaN of any column are skipped and carried over as NaN, so
        indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `short`, `medium`, `long` or `columns` type.
        ValueError: An unknown `output`; a window below 1 or the windows not
            in increasing order; a required column missing (the message names
            the required and the available columns); an invalid `columns=` or
            any `column=`; NaN after the leading run, or a non-finite or
            out-of-range value; high below low on a row; or fewer than
            `long + 1` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(short, medium, long)
    return run_columns(_native.ultosc, _NAMES, data, params, columns, SLOTS, column, output)


def ultosc_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    short: int = 7,
    medium: int = 14,
    long: int = 28,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Ultimate Oscillator of many datasets.

    See `pyta.ultosc` for the calculation and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        short: Rows in the shortest window, at least 1, shared by every dataset.
        medium: Rows in the middle window, above `short`, shared.
        long: Rows in the longest window, above `medium`, shared.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (the Ultimate Oscillator uses several
            columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.ultosc`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the result in
        its input's container type, or the exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or a window or
            `columns` has the wrong type.
        ValueError: An unknown `output`; a window below 1 or the windows not
            in increasing order, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(short, medium, long)
    return run_columns_batch(
        _native.ultosc_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
