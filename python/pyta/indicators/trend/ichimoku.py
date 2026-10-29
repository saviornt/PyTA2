"""Ichimoku Cloud, a trend indicator on high, low and close, five outputs (single and batch)."""

from collections.abc import Sequence
from typing import Any

from pyta import _native
from pyta._api import run_columns, run_columns_batch
from pyta._export import Output
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot, validate_int

#: The Ichimoku Cloud's inputs, in the order `_native.ichimoku` takes them and
#: unnamed input uses.
SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))

#: The Ichimoku Cloud's outputs, in the order they are returned. Title-case
#: input gives "Ichimoku_Tenkan", "Ichimoku_Kijun", "Ichimoku_Senkou_A",
#: "Ichimoku_Senkou_B", "Ichimoku_Chikou" (no part is an abbreviation).
OUTPUTS = (
    "ichimoku_tenkan",
    "ichimoku_kijun",
    "ichimoku_senkou_a",
    "ichimoku_senkou_b",
    "ichimoku_chikou",
)
_NAMES = OutputNames("ichimoku", OUTPUTS, abbreviations=())


def _params(tenkan: object, kijun: object, senkou: object) -> tuple[int, int, int]:
    """Validates the Ichimoku Cloud's windows: each at least 1, in any order."""
    return (
        validate_int("tenkan", tenkan, 1),
        validate_int("kijun", kijun, 1),
        validate_int("senkou", senkou, 1),
    )


def ichimoku(
    data: object,
    tenkan: int = 9,
    kijun: int = 26,
    senkou: int = 52,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> Any:
    """Ichimoku Cloud (Ichimoku Kinko Hyo, Goichi Hosoda), unshifted.

    `ichimoku_tenkan` (conversion line) is (highest high + lowest low) / 2 over
    the last `tenkan` rows, `ichimoku_kijun` (base line) the same over `kijun`
    rows and `ichimoku_senkou_b` (leading span B) over `senkou` rows, each
    window including the current row (each equals `pyta.donchian`'s middle
    line over that window). `ichimoku_senkou_a` (leading span A) is
    (tenkan + kijun) / 2 and `ichimoku_chikou` (lagging span) is close.

    Every line is on the row it is calculated from, so the output is as long
    as the input and nothing is dropped. Charts draw both senkou spans `kijun`
    rows ahead (the cloud) and the chikou span `kijun` rows back; shift them
    yourself to plot (for example pandas' `shift(kijun)` and `shift(-kijun)`).
    Needs at least max(`tenkan`, `kijun`, `senkou`) rows. Each output keeps its
    own warm-up: the first `tenkan - 1`, `kijun - 1`, max(`tenkan`, `kijun`) - 1
    and `senkou - 1` values of the first four are NaN; the chikou span has none.

    Args:
        data: High, low and close prices: a pandas DataFrame, dict of columns,
            JSON (array of records or object of arrays) or CSV text holding at
            least those columns (others are ignored; adj_close stands in for a
            missing close), or unnamed columns in the order high, low, close: a
            2-D NumPy array or list of lists with 3 columns, or a tuple of three
            arrays.
        tenkan: Rows in the conversion line's window, at least 1 (default 9).
        kijun: Rows in the base line's window, at least 1 (default 26).
        senkou: Rows in leading span B's window, at least 1 (default 52). The
            three windows may be in any order.
        columns: The three columns to use, in any order, for named input; each
            name is assigned to the input for its role (high; low; close or
            adj_close). Names follow the same rules as `column=` in
            single-column indicators. By default the columns are found by role.
        column: Not valid here (the Ichimoku Cloud uses several columns);
            raises ValueError.
        output: Container to return instead of the input's own: "list",
            "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv" or
            "csv_bytes", each in one fixed shape, with a pandas index carried to
            the named targets (see docs/API.md "Output conversion"). None (the
            default) keeps the input's container.

    Returns:
        Five outputs, "ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a",
        "ichimoku_senkou_b" and "ichimoku_chikou" in that order, each float64
        and the same length as `data`. A DataFrame gives a DataFrame with those
        five columns (index kept); a dict or JSON object gives one key per
        output (dict values keep the high column's container type); JSON
        records get the five keys on every record. A 2-D array or a tuple of
        arrays gives a tuple of five outputs (`tenkan, kijun, senkou_a,
        senkou_b, chikou = pyta.ichimoku(array)`). JSON writes NaN as null.
        Names follow the input's casing ("ICHIMOKU_TENKAN" for "HIGH, LOW,
        CLOSE", "Ichimoku_Senkou_A" for "High, Low, Close"; see docs/API.md).
        Rows before the last leading NaN of any column are skipped and carried
        over as NaN in every output, so indicators can be chained.

    Raises:
        TypeError: Unsupported input type or dtype, a one-series input, or a
            wrong `tenkan`, `kijun`, `senkou` or `columns` type.
        ValueError: An unknown `output`; `tenkan`, `kijun` or `senkou` below 1;
            a required column missing (the message names the required and the
            available columns); an invalid `columns=` or any `column=`; NaN
            after the leading run, or a non-finite or out-of-range value; high
            below low on a row; or fewer than max(`tenkan`, `kijun`, `senkou`)
            rows.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(tenkan, kijun, senkou)
    return run_columns(_native.ichimoku, _NAMES, data, params, columns, SLOTS, column, output)


def ichimoku_batch[D: (list[Any], dict[Any, Any])](
    datasets: D,
    tenkan: int = 9,
    kijun: int = 26,
    senkou: int = 52,
    *,
    columns: Sequence[str] | None = None,
    column: None = None,
    output: Output | None = None,
) -> D:
    """Ichimoku Cloud of many datasets.

    See `pyta.ichimoku` for the calculation, the outputs and the accepted containers.

    Args:
        datasets: A list or mapping of datasets, each in any supported container.
        tenkan: The conversion line's window, shared by every dataset.
        kijun: The base line's window, shared by every dataset.
        senkou: Leading span B's window, shared by every dataset.
        columns: Columns to use for every named dataset, in any order.
        column: Not valid here (the Ichimoku Cloud uses several columns);
            raises ValueError.
        output: Container to return for every dataset, as for `pyta.ichimoku`;
            None (the default) keeps each dataset's own container.

    Returns:
        A list or dict of the same shape and order. Each entry is the five
        outputs in the form `pyta.ichimoku` returns for its input, or the
        exception explaining why it failed.

    Raises:
        TypeError: `datasets` is not a list or mapping, or `tenkan`, `kijun`,
            `senkou` or `columns` has the wrong type.
        ValueError: An unknown `output`; an invalid `tenkan`, `kijun` or
            `senkou`, or a `column=`.
        ModuleNotFoundError: `output="pandas"` and pandas is not installed.
    """
    params = _params(tenkan, kijun, senkou)
    return run_columns_batch(
        _native.ichimoku_batch, _NAMES, datasets, params, columns, SLOTS, column, output
    )
