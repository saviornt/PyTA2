"""Stochastic Oscillator, a momentum indicator on high, low and close, two outputs."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_int

#: The Stochastic's inputs, in the order `_native.stoch` takes them and
#: unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: The Stochastic's outputs, in the order they are returned. Title-case input
#: gives "Stoch_K", "Stoch_D".
OUTPUTS = ("stoch_k", "stoch_d")
_NAMES = OutputNames("stoch", OUTPUTS, abbreviations=())


def _params(k: object, k_smooth: object, d: object) -> tuple[int, int, int]:
    """Validates the Stochastic's windows: each at least 1."""
    return (
        validate_int("k", k, 1),
        validate_int("k_smooth", k_smooth, 1),
        validate_int("d", d, 1),
    )


def stoch(
    data: object,
    k: int = 14,
    k_smooth: int = 3,
    d: int = 3,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Stochastic Oscillator (George Lane), the full stochastic: %K and %D.

    Raw %K is 100 * (close - lowest low) / (highest high - lowest low) over
    the last `k` rows, the current row included; it is 0 on a flat window (the
    range zero within rounding, as TA-Lib). `stoch_k` is the simple moving
    average of raw %K over `k_smooth` rows and `stoch_d` the simple moving
    average of `stoch_k` over `d` rows, as TA-Lib's `STOCH` with SMA. With
    `k_smooth=1` this is the fast stochastic; the defaults 14/3/3 are Lane's
    slow stochastic (TA-Lib defaults to `k=5`; pass it for TA-Lib's numbers).

    Needs at least `k + k_smooth + d - 2` rows. Each output keeps its own
    warm-up: the first `k + k_smooth - 2` values of `stoch_k` and the first
    `k + k_smooth + d - 3` of `stoch_d` are NaN (TA-Lib also blanks `stoch_k`
    until `stoch_d` starts).

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        k: Rows in the highest-high and lowest-low window, at least 1
            (default 14).
        k_smooth: Rows in the moving average that smooths raw %K, at least 1
            (default 3).
        d: Rows in the moving average of %K that gives %D, at least 1
            (default 3).
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (the Stochastic uses several columns); raises
            ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Two outputs, "stoch_k" and "stoch_d" in that order, each float64 and
        the same length as `data`, between 0 and 100. A DataFrame gives a
        DataFrame with those two columns (index kept); a dict or JSON object
        gives one key per output (dict values keep the high column's container
        type); JSON records get the two keys on every record. A 2-D array or a
        tuple of arrays gives a tuple of two outputs
        (`stoch_k, stoch_d = pyta.stoch(array)`). JSON writes NaN as null.
        Names follow the input's casing ("STOCH_K" for "HIGH, LOW, CLOSE",
        "Stoch_K" for "High, Low, Close"; see docs/API.md). Rows before the
        last leading NaN of any column are skipped and carried over as NaN in
        every output, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `k`, `k_smooth`, `d` or `columns` type.
        ValueError: An unknown `output`; `k`, `k_smooth` or `d` below 1; a
            required column missing (the message names the required and the
            available columns); an invalid `columns=` or any `column=`; NaN
            after the leading run, or a non-finite or out-of-range value; high
            below low on a row; or fewer than `k + k_smooth + d - 2` rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(k, k_smooth, d)
    return run_columns(_native.stoch, _NAMES, data, params, columns, SLOTS, column, output)


def stoch_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    k: int = 14,
    k_smooth: int = 3,
    d: int = 3,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Stochastic Oscillator of many datasets.

    See `pyta.stoch` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        k: The highest-high and lowest-low window, shared by every dataset.
        k_smooth: The window of the average that smooths raw %K, shared by
            every dataset.
        d: The window of the average of %K that gives %D, shared by every
            dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (the Stochastic uses several columns); raises
            ValueError.
        output: Container to return for every dataset, as for `pyta.stoch`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the two
        outputs in the form `pyta.stoch` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `k`, `k_smooth`, `d`
            or `columns` has the wrong type.
        ValueError: An unknown `output`; an invalid `k`, `k_smooth` or `d`, or a
            `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(k, k_smooth, d)
    return run_columns_batch(
        _native.stoch_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
