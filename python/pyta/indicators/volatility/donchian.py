"""Donchian Channels, a volatility indicator on high and low, three outputs (single and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import HIGH, LOW, Slot, validate_period

#: Donchian Channels' inputs, in the order `_native.donchian` takes them and
#: unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)))

#: Donchian Channels' outputs, in the order they are returned. Title-case input
#: gives "Donchian_Upper", "Donchian_Middle", "Donchian_Lower" (no part is an
#: abbreviation).
OUTPUTS = ("donchian_upper", "donchian_middle", "donchian_lower")
_NAMES = OutputNames("donchian", OUTPUTS, abbreviations=())


def donchian(
    data: object,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Donchian Channels (TA-Lib's MAX(high) and MIN(low); the current row included).

    `donchian_upper` is the highest high of the last `period` rows and
    `donchian_lower` the lowest low, both including the current row;
    `donchian_middle` is (upper + lower) / 2. Needs at least `period` rows. The
    first `period - 1` results of every output are NaN (warm-up). With
    `period=1`, upper is the high and lower the low. StockCharts' Price
    Channels use the `period` rows before the current one: shift these outputs
    by one row for breakout signals.

    Args:
        data: High and low prices: a pandas DataFrame, dict of columns, JSON
            (array of records or object of arrays) or CSV text holding at least
            those columns (others are ignored), or unnamed columns in the order
            high, low: a 2-D NumPy array or list of lists with 2 columns, or a
            tuple of two arrays.
        period: Number of rows in each window, the current row included, at
            least 1 (default 20).
        columns: The two columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low). Names follow
            the same rules as `column=` in single-column indicators. By default
            the columns are found by role.
        column: Not valid here (Donchian Channels use several columns); raises
            ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Three outputs, "donchian_upper", "donchian_middle" and
        "donchian_lower" in that order, each float64 and the same length as
        `data`. A DataFrame gives a DataFrame with those three columns (index
        kept); a dict or JSON object gives one key per output (dict values keep
        the high column's container type); JSON records get the three keys on
        every record. A 2-D array or a tuple of arrays gives a tuple of three
        outputs (`upper, middle, lower = pyta.donchian(array)`). JSON writes
        NaN as null. Names follow the input's casing ("DONCHIAN_UPPER" for
        "HIGH, LOW", "Donchian_Upper" for "High, Low"; see docs/API.md). Rows
        before the last leading NaN of either column are skipped and carried
        over as NaN in every output, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; `period` below 1; a required column
            missing (the message names the required and the available columns);
            an invalid `columns=` or any `column=`; NaN after the leading run, or
            a non-finite or out-of-range value; high below low on a row; or
            fewer than `period` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns(_native.donchian, _NAMES, data, params, columns, SLOTS, column, output)


def donchian_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 20,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Donchian Channels of many datasets.

    See `pyta.donchian` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of rows in each window, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (Donchian Channels use several columns); raises
            ValueError.
        output: Container to return for every dataset, as for `pyta.donchian`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.donchian` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; invalid `period`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = (validate_period(period),)
    return run_columns_batch(
        _native.donchian_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
