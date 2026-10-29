# ADX (Average Directional Index)

**Category:** Trend · **Function:** `pyta.adx` · **Batch:** `pyta.batch.adx` · **Columns:** high, low, close

## What it is

The Average Directional Index measures how strongly a market is trending, whichever way it goes. J. Welles Wilder introduced it in *New Concepts in Technical Trading Systems* (1978), together with the two directional indicators it is built from, and PyTA returns all three lines:

1. **+DM and -DM (directional movement).** On each bar, the rise of the high over the previous high and the fall of the low below the previous low are compared. The larger one, if it is positive, is that bar's movement: a rise is +DM, a fall is -DM; the other is 0 (an inside bar, or a tie, gives 0 to both).
2. **+DI and -DI (directional indicators).** +DM, -DM and the true range (the bar's range, extended to the previous close across a gap) are each smoothed over `period` bars with Wilder's running sum. `+DI = 100 * smoothed +DM / smoothed true range`, and likewise -DI: the share of the recent range that moved up, and that moved down, in percent.
3. **DX and ADX.** `DX = 100 * |+DI - -DI| / (+DI + -DI)`: how one-sided the movement is. The ADX is Wilder's average of DX over `period` bars, starting from the mean of the first `period` DX values.

The default period is Wilder's (and TA-Lib's) 14. Each line is on a 0 to 100 scale.

## What it is for

- **Trend strength.** ADX rises while a trend, up or down, gains strength and falls as it fades. Wilder's rule of thumb: above about 25 a trend is in place; below about 20 the market is ranging, where trend-following signals work poorly.
- **Trend direction.** +DI above -DI means buyers have the upper hand; -DI above +DI, sellers. A crossover of the two DIs was Wilder's entry signal, used with ADX to filter out crossings in a trendless market.
- **Filtering other systems.** Many traders apply moving-average or breakout systems only while ADX is high, and oscillators only while it is low.

ADX does not say which way the trend goes: a strong downtrend has a high ADX too. Read the DIs for direction.

## Usage

ADX needs three columns, so pass data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, ...):

```python
import pyta

data = {
    "high": [10.0, 12.0, 13.0, 12.0],
    "low": [8.0, 9.0, 10.0, 8.0],
    "close": [9.0, 11.0, 12.0, 9.0],
}

result = pyta.adx(data, period=2)
# result["adx"]:          [nan, nan, nan, 66.67]
# result["adx_plus_di"]:  [nan, nan, 44.44, 16.0]
# result["adx_minus_di"]: [nan, nan, 0.0, 32.0]
```

A DataFrame (or a dict, or JSON) gains one column per line:

```python
pyta.adx(df)                       # period 14: adx, adx_plus_di, adx_minus_di
pyta.adx(df, period=20)
pyta.adx(yfinance_df).columns      # ['ADX', 'ADX_Plus_DI', 'ADX_Minus_DI']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.adx(df, columns=["close", "low", "high"])
pyta.adx(df, columns=["high", "low", "adj_close"])   # the adjusted close as the close
```

Unnamed input takes its columns in the order **high, low, close**, and returns a tuple of the three lines:

```python
import numpy as np

adx, plus_di, minus_di = pyta.adx(np.column_stack([highs, lows, closes]))   # (rows, 3) or (3, rows)
adx, plus_di, minus_di = pyta.adx((highs, lows, closes))                    # tuple of arrays
```

ADX is also in the trend namespace; both names are the same function:

```python
pyta.trend.adx(df)   # same as pyta.adx
from pyta.trend import adx
```

Many datasets in one call:

```python
results = pyta.batch.adx([df1, df2, df3])              # list of results, in order
pyta.batch.trend.adx({"SPY": spy, "QQQ": qqq})         # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `period` | `int` | `14` | Wilder's smoothing period for the directional movement, the true range and ADX; at least `2` (TA-Lib's minimum) |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low and a close (or adjusted close). `None` finds them by name. Names are standard column names or aliases, such as `High`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, then `adj_close` | 3rd |

A missing column raises `ValueError` naming the required and the available columns.

## Output

- Three outputs in the order `adx`, `adx_plus_di`, `adx_minus_di`, each the same length as the input, `float64`, from 0 to 100.
- Each output keeps its own warm-up:

  | Output | First value at row | Warm-up (`NaN`) rows |
  |---|---|---|
  | `adx_plus_di`, `adx_minus_di` | `period` | `period` |
  | `adx` | `2 * period - 1` | `2 * period - 1` |

  With the default period the DIs start at row 14 and ADX at row 27. TA-Lib's `PLUS_DI`, `MINUS_DI` and `ADX` start at the same rows.
- At least `2 * period` rows are required, so every output has a value.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the three. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `ADX_PLUS_DI` for `HIGH, LOW, CLOSE`, `ADX_Plus_DI` for `High, Low, Close` (ADX and DI are abbreviations, so they stay upper case).

### Let it stabilise

Wilder's smoothing never forgets its start completely: the seed's weight shrinks by a factor `(period - 1) / period` per bar, and ADX smooths values that are smoothed already. The first values therefore depend on where the data begins. With the default period, about 150 bars (roughly ten periods) before the part you use make the values practically independent of the start; compare values across platforms, or across two downloads that start on different days, only after that. TA-Lib can be told to drop such an "unstable period" from its output (`TA_SetUnstablePeriod`); PyTA returns every value, so skip the rows yourself.

## Edge cases

| Situation | ADX |
|---|---|
| A flat stretch after some movement | +DM, -DM and the true range are all 0, so both smoothed sums shrink by the same factor each bar: the DIs **hold their last values**, and ADX keeps moving towards their DX |
| A series flat from its first bar | the smoothed true range is 0: both DIs are 0, no DX is taken, and ADX is 0 |
| +DI and -DI both 0 (or their sum below `1e-14`) | no DX is taken that bar: ADX keeps its value (the first ADX counts it as 0) |
| A bar whose high rises and low falls by the same amount | neither movement counts: +DM and -DM are both 0 |
| Close outside the bar's high and low | not rejected; the DIs can then exceed 100 |

These follow TA-Lib exactly, including its zero tests (see the implementation notes).

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in every output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `2 * period` rows | `ValueError` |
| `period` below 2 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: ADX needs three columns |

## Implementation notes

### TA-Lib's calculation

PyTA follows TA-Lib 0.8.3's `TA_ADX`, `TA_PLUS_DI` and `TA_MINUS_DI`, which follow Wilder's book, and matches their output bit for bit on the two reference series in `tests/fixtures/` (300 real SPY sessions and 120 synthetic edge-case rows, including a flat stretch and bars with high equal to low):

- **Seeding.** +DM, -DM and the true range are summed plainly over bars `1` to `period - 1`; from bar `period` on, each sum is `sum - sum / period + value` (Wilder's smoothing written as a sum, `period` times his average). TA-Lib 0.8.3 multiplies by a precomputed `1 / period` rather than dividing, and so does PyTA, which is why the values agree to the last bit. The first ADX is the plain mean of the DX values of bars `period` to `2 * period - 1`; each later ADX is `ADX - (ADX - DX) / period`. StockCharts' worked ADX example (`cs-adx.xls`, ChartSchool) seeds the same way, so its values agree with PyTA's up to its two-decimal rounding.
- **Zero guards.** TA-Lib computes the DIs only when the smoothed true range is above 0 (an exact test), else writes 0; it takes a DX only when `+DI + -DI` is outside `(-1e-14, 1e-14)` (`TA_IS_ZERO`, a fixed band, fine for values in percent); a skipped DX leaves ADX unchanged. PyTA copies both.
- **One pass.** TA-Lib computes the three lines in three separate functions; PyTA computes all three in one pass over the rows, with the same arithmetic in the same order.
- **Plain arithmetic.** No fused multiply-add is used; the TA-Lib 0.8.3 wheel's results are matched with plain multiplies and adds.

### Differences from other sources

- **Wilder's hand worksheet** rounded each step to whole numbers or a few decimals; values agree with PyTA's to that rounding.
- **Platforms that smooth with an EMA or an RMA seeded from the first value** (some TradingView scripts) give different early values; the difference fades after the stabilisation period above.
- **Periods.** TA-Lib accepts periods up to 100,000; PyTA accepts any period up to `2**31 - 1` that the data can fill.

### Calculation

The Rust kernel (`pyta-trend`) builds on the shared true-range and Wilder-sum kernels of `pyta-core` (the true range is the same as `pyta.atr`'s). The cost is proportional to the number of rows, independent of `period`.

## See also

[ATR](../volatility/atr.md) · [MACD](macd.md) · [EMA](ema.md) · [CCI](../momentum/cci.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
