"""Bollinger Bands, a volatility indicator with three outputs (single call and batch)."""

from typing import Any

from pyta import _native
from pyta._api import run, run_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_int, validate_positive_float

#: Bollinger Bands' outputs, in the order they are returned. Title-case input
#: gives "BBANDS_Upper", "BBANDS_Middle", "BBANDS_Lower" (the parts are words).
OUTPUTS = ("bbands_upper", "bbands_middle", "bbands_lower")
_NAMES = OutputNames("bbands", OUTPUTS, abbreviations=("bbands",))


def _params(period: object, k: object) -> tuple[int, float]:
    """Validates BBANDS' parameters: `period` at least 2 (TA-Lib's minimum), `k` above 0."""
    return (validate_int("period", period, 2), validate_positive_float("k", k))


def bbands(
    data: object,
    period: int = 20,
    k: float = 2.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> Any:
    """Bollinger Bands (TA-Lib's BBANDS with a simple moving average).

    `bbands_middle` is the simple moving average of the last `period` values;
    `bbands_upper` and `bbands_lower` lie `k` population standard deviations
    (dividing by `period`) of the same window above and below it. One `k`
    serves both bands. Needs at least `period` values. The first `period - 1`
    results of every output are NaN (warm-up). A flat window gives three
    equal bands.

    Args:
        data: Prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, JSON (str or bytes) or CSV text.
        period: Number of values in each window, at least 2 (default 20).
        k: Width of each band in standard deviations (TA-Lib's `nbdevup` and
            `nbdevdn`, here one value), a finite number above 0; an int is
            accepted (default 2.0).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (BBANDS uses one column); raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Three outputs, "bbands_upper", "bbands_middle" and "bbands_lower" in
        that order, each float64 and the same length as `data`. A DataFrame
        gives a DataFrame with those three columns (index kept); a dict or
        JSON object gives one key per output (dict values keep the input
        column's container type); JSON records get the three keys on every
        record. A list, tuple, NumPy array or pandas Series gives a tuple of
        three of the same kind (`upper, middle, lower = pyta.bbands(close)`; a
        Series is named by its output and keeps its index), and a JSON array
        of numbers gives a JSON object keyed by output name. JSON writes NaN as
        null. Names follow the input column's casing ("BBANDS_UPPER" for
        "CLOSE", "BBANDS_Upper" for "Close"; see docs/API.md). Leading NaN in
        the input is skipped and carried over in every output.

    Raises:
        TypeError: Unsupported input type or dtype, or a `period` or `k` of the
            wrong type.
        ValueError: An unknown `output`; `period` below 2, `k` not a finite
            number above 0, a `columns=`, empty, non-finite or out-of-range
            input, or fewer than `period` values.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run(_native.bbands, _NAMES, data, _params(period, k), column, CLOSE, columns, output)


def bbands_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    period: int = 20,
    k: float = 2.0,
    *,
    column: str | None = None,
    columns: None = None,
    output: Output | None = None,
) -> D:
    """Bollinger Bands of many datasets.

    See `pyta.bbands` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        period: Number of values in each window, at least 2, shared by every dataset.
        k: Width of each band in standard deviations, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (BBANDS uses one column); raises ValueError.
        output: Container to return for every dataset, as for `pyta.bbands`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.bbands` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `period`, `k` or
            `column` has the wrong type.
        ValueError: An unknown `output`; invalid `period` or `k`, or a `columns=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    return run_batch(
        _native.bbands_batch, _NAMES, datasets, _params(period, k), column, CLOSE, columns, output
    )
