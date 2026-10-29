"""MACD, a trend indicator with three outputs (single call and batch)."""

from typing import Any

from pyta import _native
from pyta._api import run, run_batch
from pyta._outputs import OutputNames
from pyta._validation import CLOSE, validate_fast, validate_signal, validate_slow

#: MACD's outputs, in the order they are returned. Title-case input gives
#: "MACD", "MACD_Signal", "MACD_Hist" ("signal" and "hist" are words).
OUTPUTS = ("macd", "macd_signal", "macd_hist")
_NAMES = OutputNames("macd", OUTPUTS, abbreviations=("macd",))


def _params(fast: object, slow: object, signal: object) -> tuple[int, int, int]:
    """MACD's validated parameters, in the order `_native.macd` takes them."""
    return validate_fast(fast), validate_slow(slow), validate_signal(signal)


def macd(
    data: object,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    *,
    column: str | None = None,
    columns: None = None,
) -> Any:
    """Moving Average Convergence/Divergence (TA-Lib convention).

    `macd` is the `fast` EMA minus the `slow` EMA, both starting at row
    `slow - 1` (the fast EMA is seeded with the mean of the `fast` prices
    ending there); `macd_signal` is the `signal` EMA of `macd`; `macd_hist` is
    `macd - macd_signal`. Needs at least `slow + signal - 1` values. Warm-up
    (NaN) differs per output: `macd` has a value from row `slow - 1`,
    `macd_signal` and `macd_hist` from row `slow + signal - 2`. If `slow` is
    less than `fast`, the two are swapped (as TA-Lib does), so the result is
    the same; `fast == slow` gives all 0.

    Args:
        data: Closing prices as a list, tuple, NumPy array, pandas Series or
            DataFrame, dict of columns, or JSON (str or bytes).
        fast: Period of the fast EMA, at least 2 (default 12).
        slow: Period of the slow EMA, at least 2 (default 26).
        signal: Period of the signal line's EMA, at least 1 (default 9).
        column: Column to use for DataFrame, dict, and JSON-object input.
            Defaults to the close column, or the only column if there is just
            one. Must be a standard name (open, high, low, close, adj_close,
            volume) or an alias; case, whitespace and . _ - are ignored.
            See docs/API.md.
        columns: Not valid here (MACD uses one column); raises ValueError.

    Returns:
        Three outputs, "macd", "macd_signal" and "macd_hist" in that order,
        each float64 and the same length as `data`. A DataFrame gives a
        DataFrame with those three columns (index kept); a dict or JSON object
        gives one key per output (dict values keep the input column's
        container type); JSON records get the three keys on every record. A
        list, tuple, NumPy array or pandas Series gives a tuple of three of
        the same kind (`macd, signal, hist = pyta.macd(close)`; a Series is
        named by its output and keeps its index), and a JSON array of numbers
        gives a JSON object keyed by output name. JSON writes NaN as null.
        Names follow the input column's casing ("MACD_SIGNAL" for "CLOSE",
        "MACD_Signal" for "Close"; see docs/API.md). Leading NaN in the input
        is skipped and carried over in every output.

    Raises:
        TypeError: Unsupported input type or dtype, or a non-integer `fast`,
            `slow` or `signal`.
        ValueError: `fast` or `slow` below 2 or `signal` below 1, a `columns=`,
            empty, non-finite or out-of-range input, or fewer than
            `slow + signal - 1` values.
    """
    params = _params(fast, slow, signal)
    return run(_native.macd, _NAMES, data, params, column, CLOSE, columns)


def macd_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    *,
    column: str | None = None,
    columns: None = None,
) -> D:
    """Moving Average Convergence/Divergence of many datasets.

    See `pyta.macd` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        fast: Period of the fast EMA, at least 2, shared by every dataset.
        slow: Period of the slow EMA, at least 2, shared by every dataset.
        signal: Period of the signal line's EMA, at least 1, shared by every dataset.
        column: Column to use for every dataset that has columns.
        columns: Not valid here (MACD uses one column); raises ValueError.

    Returns:
        A list or dict of the same shape and order. Each entry is the three
        outputs in the form `pyta.macd` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `fast`, `slow`,
            `signal` or `column` has the wrong type.
        ValueError: Invalid `fast`, `slow` or `signal`, or a `columns=`.
    """
    params = _params(fast, slow, signal)
    return run_batch(_native.macd_batch, _NAMES, datasets, params, column, CLOSE, columns)
