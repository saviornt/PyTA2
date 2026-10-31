# Parabolic SAR

**Category:** Trend · **Function:** `pyta.sar` · **Batch:** `pyta.batch.sar` · **Columns:** high, low

## What it is

The Parabolic SAR ("stop and reverse") is a trailing stop that follows the price and flips to the other side when the price crosses it. J. Welles Wilder introduced it in *New Concepts in Technical Trading Systems* (1978). It is always either long or short:

1. **In an uptrend** the SAR sits below the price. Each bar it moves towards the **extreme point** (EP), the highest high of the trend so far, by a fraction of the distance: `SAR + AF * (EP - SAR)`. It never rises above the lows of the last two bars.
2. **The acceleration factor** (AF) starts at `acceleration` (0.02) and grows by `acceleration` each time the trend makes a new extreme, up to `maximum` (0.2). The SAR therefore starts slowly and speeds up as the trend runs: the parabolic curve that gives it its name.
3. **Stop and reverse.** When a bar's low reaches the SAR, the trend reverses: the SAR jumps to the old EP (moved out to the bar's high if needed), the AF resets to `acceleration`, and the EP becomes the bar's low. A downtrend is the mirror image, with the SAR above the price, the lowest low as EP and the highs as the limit.

The defaults, 0.02 and 0.2, are Wilder's and TA-Lib's. Values are prices, on the same scale as the input.

## What it is for

- **Trailing stops.** A long position is closed when the price falls to the SAR; the stop tightens as the trend accelerates, so it locks in more of a strong move.
- **Trend direction.** SAR below the price means the indicator is long; above, short. Many charts plot it as dots above or below the bars.
- **Always-in systems.** Wilder used it as a complete stop-and-reverse system: each reversal closes one position and opens the opposite one.

In a sideways market the SAR reverses often and gives many losing signals; it is commonly filtered with a trend-strength indicator such as [ADX](adx.md).

## Usage

The SAR needs the high and low columns, so pass data in a container that has column names. PyTA finds them by name and ignores the rest (dates, open, close, volume, ...):

```python
import pyta

data = {
    "high": [10.0, 12.0, 14.0, 15.0, 13.0, 12.0, 12.0, 12.0, 13.0],
    "low": [8.0, 9.0, 10.0, 9.0, 11.0, 7.0, 6.0, 10.0, 6.0],
}

pyta.sar(data, acceleration=0.25, maximum=0.5)
# {'sar': [nan, 8.0, 9.0, 15.0, 15.0, 15.0, 13.0, 6.0, 13.0]}
```

Here the SAR starts long below the price, reverses to short on row 3 (the low touches it), and back to long on row 7.

A DataFrame (or a dict, or JSON) gains one column:

```python
pyta.sar(df)                                  # acceleration 0.02, maximum 0.2
pyta.sar(df, acceleration=0.01, maximum=0.1)  # slower
pyta.sar(yfinance_df).columns                 # ['SAR']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.sar(df, columns=["low", "high"])
```

Unnamed input takes its columns in the order **high, low**:

```python
import numpy as np

values = pyta.sar(np.column_stack([highs, lows]))   # (rows, 2) or (2, rows)
values = pyta.sar((highs, lows))                    # tuple of arrays
```

The SAR is also in the trend namespace; both names are the same function:

```python
pyta.trend.sar(df)   # same as pyta.sar
from pyta.trend import sar
```

Many datasets in one call:

```python
results = pyta.batch.sar([df1, df2, df3])              # list of results, in order
pyta.batch.trend.sar({"SPY": spy, "QQQ": qqq})         # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High and low prices; other columns are ignored |
| `acceleration` | `float` | `0.02` | The acceleration factor's start and the step it grows by at each new extreme; a finite number above 0 and at most `maximum` |
| `maximum` | `float` | `0.2` | The acceleration factor's cap; a finite number above 0 |
| `columns` | list of `str` or `None` | `None` | The two columns to use, in any order: a high and a low. `None` finds them by name. Names are standard column names or aliases, such as `High`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

Both parameters accept ints and NumPy numbers; `bool` raises `TypeError`. `column=` (singular) is for single-column indicators and raises `ValueError` here.

The start and the step are the same number, as in Wilder's book and TA-Lib's `SAR`. TA-Lib's `SAREXT`, which sets them apart (and per direction), is not provided.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |

A missing column raises `ValueError` naming the required and the available columns.

## Output

- One output, `sar`, the same length as the input, `float64`.
- The first row is `NaN` (warm-up); every later row has a value. TA-Lib's `SAR` also starts at row 1.
- At least 2 rows are required.
- A DataFrame, dict or JSON object gets one `sar` column or key (a dict keeps the container type of its high column); a 2-D array gives a 1-D array and a tuple a tuple.
- The name follows the input's casing: `SAR` for `HIGH, LOW` or `High, Low` (SAR is an abbreviation).

On every row from 1, the value is at or below that row's low (long) or at or above its high (short), never strictly inside the bar.

## Edge cases

| Situation | SAR |
|---|---|
| A low exactly equal to the SAR in an uptrend (or a high equal to it in a downtrend) | the trend **reverses** (TA-Lib's `<=` and `>=` tests) |
| The first bar | No value: it only seeds the direction and the first SAR (see the implementation notes) |
| A flat series | Every value is that price: each bar touches the SAR and reverses |
| `acceleration` equal to `maximum` | Valid: the factor is constant |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in either column | Rows up to the last leading `NaN` of either column are skipped, then re-padded with `NaN` |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than 2 rows | `ValueError` |
| `acceleration` or `maximum` zero, negative, `NaN` or infinite | `ValueError` |
| `acceleration` above `maximum` | `ValueError` naming both (TA-Lib lowers `acceleration` to `maximum` silently) |
| A list, 1-D array or Series (one series) | `TypeError`: SAR needs two columns |

## Implementation notes

### TA-Lib's calculation

PyTA follows TA-Lib 0.8.3's `TA_SAR` step by step, and matches its output on the three reference series in `tests/fixtures/` (300 real SPY sessions at 0.02/0.2 and 0.01/0.1, and 120 synthetic edge-case rows) within one unit in the last place:

- **First direction.** Wilder started each trade from the previous one, which a function given only a price history cannot do. TA-Lib takes the directional movement of bar 1 (its `MINUS_DM` with period 1): **short** when the low fell (`low[0] - low[1] > 0`) by more than the high rose, otherwise **long**, a tie included.
- **First SAR and EP.** Long: SAR = `low[0]`, EP = `high[1]`; short: SAR = `high[0]`, EP = `low[1]`. Bar 0 is consumed, so the first value is on bar 1. On bar 1, the "previous bar" used to limit the SAR is bar 1 itself, as in TA-Lib.
- **Reversal.** Tested before anything else on each bar: `low <= SAR` when long, `high >= SAR` when short. The written SAR is the old EP, limited to the previous and current bar's high (long to short) or low (short to long); then AF resets and EP becomes the bar's low or high, and the next SAR is computed and limited the same way.
- **No reversal.** The SAR carried into the bar is written; a new extreme moves EP and adds `acceleration` to AF, capped at `maximum`; the next SAR is `SAR + AF * (EP - SAR)`, limited to the previous and current bar's lows (long) or highs (short).
- **Multiply-add.** TA-Lib writes the step as a fused multiply-add (`fma`), which rounds once; PyTA uses a plain multiply and add, which rounds twice. On the reference series 8 to 33 values out of about 300 differ, each by one unit in the last place (at most 2.1e-16 relative). A fused multiply-add would match bit for bit, but PyTA's builds do not assume an FMA instruction, and the library call made the kernel about 16% slower. PyTA promises agreement with TA-Lib 0.8.3 within `1e-9`, not bit for bit, and uses plain multiplies and adds everywhere, never a fused multiply-add or code picked by CPU at run time ([API: Agreement with TA-Lib](../../API.md#agreement-with-ta-lib)).

### Differences from other sources

- **Other platforms start differently.** MetaStock uses the first bar's high or low, TradeStation the second bar's close, and some platforms always start long. The values differ at the start; once a reversal has happened on both, they track the same trade and usually agree from then on (up to rounding). Compare platforms only after the first reversal.
- **Wilder's worksheet** started from the extreme point of the previous trade and rounded each step; values agree with PyTA's after the first reversal, to that rounding.
- **Parameter order.** TA-Lib lowers an `acceleration` above `maximum` to `maximum` without telling the caller; PyTA raises `ValueError` instead, so a swapped pair of arguments is caught. Both reject negative values; PyTA also rejects 0, which TA-Lib accepts (a SAR that never moves).

### Calculation

The Rust kernel (`pyta-trend`) is one pass over the rows; the cost is proportional to the number of rows and independent of the parameters.

## See also

[ADX](adx.md) · [ATR](../volatility/atr.md) · [Donchian Channels](../volatility/donchian.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
