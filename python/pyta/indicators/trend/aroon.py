"""Aroon, a trend indicator on high and low, three outputs (single call and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import HIGH, LOW, Slot, validate_int

#: Aroon's inputs, in the order `_native.aroon` takes them and unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)))

#: Aroon's outputs, in the order they are returned (TA-Lib's AROON returns down
#: before up). Title-case input gives "Aroon_Up", "Aroon_Down", "Aroon_Osc" (no
#: part is an abbreviation).
OUTPUTS = ("aroon_up", "aroon_down", "aroon_osc")
_NAMES = OutputNames("aroon", OUTPUTS, abbreviations=())


def _params(period: object) -> tuple[int]:
    """Validates Aroon's `period`: at least 2 (TA-Lib's minimum)."""
    return (validate_int("period", period, 2),)


def aroon(
    data: object,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Aroon Up, Aroon Down and Aroon Oscillator (Chande; TA-Lib's convention).

    Each row looks back over `period` + 1 rows: the current row and the
    `period` before it. `aroon_up` is 100 * (`period` - rows since the highest
    high) / `period`, `aroon_down` the same with the lowest low; a tie goes to
    the most recent row. `aroon_osc` is `aroon_up` - `aroon_down`. Identical to
    TA-Lib's AROON and AROONOSC. Needs at least `period` + 1 rows; the first
    `period` results of every output are NaN (warm-up). A flat window gives 100,
    100 and 0.

    Args:
        data: High and low prices: a pandas DataFrame, dict of columns, JSON
            (array of records or object of arrays) or CSV text holding at least
            those columns (others are ignored), or unnamed columns in the order
            high, low: a 2-D NumPy array or list of lists with 2 columns, or a
            tuple of two arrays.
        period: Number of rows looked back from the current row, at least 2
            (default 14, TA-Lib's; Chande used 25).
        columns: The two columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low). Names follow
            the same rules as `column=` in single-column indicators. By default
            the columns are found by role.
        column: Not valid here (Aroon uses several columns); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Three outputs, "aroon_up", "aroon_down" and "aroon_osc" in that order,
        each float64 and the same length as `data`. A DataFrame gives a
        DataFrame with those three columns (index kept); a dict or JSON object
        gives one key per output (dict values keep the high column's container
        type); JSON records get the three keys on every record. A 2-D array or
        a tuple of arrays gives a tuple of three outputs (`up, down, osc =
        pyta.aroon(array)`). JSON writes NaN as null. Names follow the input's
        casing ("AROON_UP" for "HIGH, LOW", "Aroon_Up" for "High, Low"; see
        docs/API.md). Rows before the last leading NaN of either column are
        skipped and carried over as NaN in every output, so indicators can be
        chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period` or `columns` type.
        ValueError: An unknown `output`; `period` below 2; a required column
            missing (the message names the required and the available columns);
            an invalid `columns=` or any `column=`; NaN after the leading run, or
            a non-finite or out-of-range value; high below low on a row; or
            fewer than `period` + 1 rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns(_native.aroon, _NAMES, data, _params(period), columns, SLOTS, column, output)


def aroon_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 14,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Aroon Up, Aroon Down and Aroon Oscillator of many datasets.

    See `pyta.aroon` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Rows looked back from the current row, at least 2, shared by
            every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (Aroon uses several columns); raises ValueError.
        output: Container to return for every dataset, as for `pyta.aroon`; None
            (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.aroon` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period` or `columns`
            has the wrong type.
        ValueError: An unknown `output`; an invalid `period`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_columns_batch(
        _native.aroon_batch, _NAMES, datasets, _params(period), columns, SLOTS, column, output
    )
