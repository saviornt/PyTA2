"""Keltner Channels, a volatility indicator on high, low and close (single call and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import (
    ADJ_CLOSE,
    CLOSE,
    HIGH,
    LOW,
    Slot,
    validate_int,
    validate_period,
    validate_positive_float,
)

#: Keltner Channels' inputs, in the order `_native.keltner` takes them and
#: unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: Keltner Channels' outputs, in the order they are returned. Title-case input
#: gives "Keltner_Upper", "Keltner_Middle", "Keltner_Lower" (no part is an
#: abbreviation).
OUTPUTS = ("keltner_upper", "keltner_middle", "keltner_lower")
_NAMES = OutputNames("keltner", OUTPUTS, abbreviations=())


def _params(period: object, atr_period: object, k: object) -> tuple[int, int, float]:
    """Validates Keltner's parameters: both periods at least 1, `k` above 0."""
    return (
        validate_period(period),
        validate_int("atr_period", atr_period, 1),
        validate_positive_float("k", k),
    )


def keltner(
    data: object,
    period: int = 20,
    atr_period: int = 10,
    k: float = 2.0,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Keltner Channels (the modern definition: EMA of close +/- k * ATR).

    `keltner_middle` is the EMA of close over `period` (TA-Lib's convention,
    identical to `pyta.ema`); `keltner_upper` and `keltner_lower` lie `k` times
    the ATR over `atr_period` (Wilder's, identical to `pyta.atr`) above and
    below it. Needs at least max(`period`, `atr_period` + 1) rows. Each output
    keeps its own warm-up: the first `period - 1` middle values are NaN, and
    the first max(`period - 1`, `atr_period`) of each band. A flat series
    gives three equal lines. Chester Keltner's 1960 original (averages of the
    typical price and of high - low) is not what this computes.

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        period: Number of rows in the EMA's seed average, which sets its weight
            2 / (period + 1); at least 1 (default 20).
        atr_period: The ATR's period (Wilder's smoothing), at least 1 (default
            10).
        k: Width of each band in ATRs, a finite number above 0; an int is
            accepted (default 2.0).
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (Keltner Channels use several columns); raises
            ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Three outputs, "keltner_upper", "keltner_middle" and "keltner_lower" in
        that order, each float64 and the same length as `data`. A DataFrame
        gives a DataFrame with those three columns (index kept); a dict or JSON
        object gives one key per output (dict values keep the high column's
        container type); JSON records get the three keys on every record. A
        2-D array or a tuple of arrays gives a tuple of three outputs
        (`upper, middle, lower = pyta.keltner(array)`). JSON writes NaN as
        null. Names follow the input's casing ("KELTNER_UPPER" for "HIGH, LOW,
        CLOSE", "Keltner_Upper" for "High, Low, Close"; see docs/API.md). Rows
        before the last leading NaN of any column are skipped and carried over
        as NaN in every output, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `period`, `atr_period`, `k` or `columns` type.
        ValueError: An unknown `output`; `period` or `atr_period` below 1, or
            `k` not a finite number above 0; a required column missing (the
            message names the required and the available columns); an invalid
            `columns=` or any `column=`; NaN after the leading run, or a
            non-finite or out-of-range value; high below low on a row; or fewer
            than max(`period`, `atr_period` + 1) rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(period, atr_period, k)
    return run_columns(_native.keltner, _NAMES, data, params, columns, SLOTS, column, output)


def keltner_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 20,
    atr_period: int = 10,
    k: float = 2.0,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Keltner Channels of many datasets.

    See `pyta.keltner` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: The EMA's period, shared by every dataset.
        atr_period: The ATR's period, shared by every dataset.
        k: Width of each band in ATRs, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (Keltner Channels use several columns); raises
            ValueError.
        output: Container to return for every dataset, as for `pyta.keltner`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.keltner` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period`,
            `atr_period`, `k` or `columns` has the wrong type.
        ValueError: An unknown `output`; an invalid `period`, `atr_period` or
            `k`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(period, atr_period, k)
    return run_columns_batch(
        _native.keltner_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
