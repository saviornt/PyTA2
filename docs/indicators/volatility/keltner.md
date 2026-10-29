# Keltner Channels

**Category:** Volatility · **Function:** `pyta.keltner` · **Batch:** `pyta.batch.keltner` · **Columns:** high, low, close

## What it is

Keltner Channels are an envelope around a moving average whose width follows volatility. PyTA computes the modern definition, popularised by Linda Bradford Raschke in the 1980s and used by StockCharts, TradingView and most charting platforms:

1. The **middle line** is the exponential moving average (EMA) of close over `period` bars.
2. The **upper band** is the middle line plus `k` times the Average True Range (ATR) over `atr_period` bars.
3. The **lower band** is the middle line minus `k` times the same ATR.

The ATR is Wilder's (the [ATR](atr.md) page has the details), so the bands widen when bars get larger or gap, and narrow in a quiet market. The defaults, a 20-bar EMA, a 10-bar ATR and `k = 2`, are StockCharts'.

The middle line is exactly `pyta.ema(close, period)`, and the bands exactly `middle ± k * pyta.atr(..., atr_period)`, bit for bit.

## What it is for

- **Trend direction.** The slope of the middle line, and whether price stays above or below it.
- **Breakouts.** A close above the upper band in a flat or rising market is a sign of strength; below the lower band, of weakness. Because the bands move with the ATR, a breakout means a move that is large for the current volatility.
- **Overbought and oversold in a trend.** In a steady uptrend, pullbacks to the middle line or the lower band are entry points; touches of the upper band are where the move is stretched.
- **Squeezes.** Bollinger Bands inside Keltner Channels mark unusually low volatility (the "TTM squeeze"); compare `pyta.bbands` with `pyta.keltner` on the same data.

## Usage

Keltner Channels need three columns, so pass data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, ...):

```python
import pyta

data = {
    "high": [11.0, 12.0, 13.0, 12.0, 14.0, 15.0],
    "low": [9.0, 10.0, 11.0, 10.0, 11.0, 12.0],
    "close": [10.0, 11.0, 12.0, 11.0, 13.0, 14.0],
}

result = pyta.keltner(data, period=3, atr_period=3, k=2.0)
# result["keltner_upper"]:  [nan, nan, nan, 15.0, 16.67, 18.11]
# result["keltner_middle"]: [nan, nan, 11.0, 11.0, 12.0, 13.0]
# result["keltner_lower"]:  [nan, nan, nan, 7.0, 7.33, 7.89]
```

A DataFrame (or a dict, or JSON) gains one column per line:

```python
pyta.keltner(df)                                  # 20, 10, 2.0: keltner_upper, keltner_middle, keltner_lower
pyta.keltner(df, period=20, atr_period=20, k=1.5)
pyta.keltner(yfinance_df).columns                 # ['Keltner_Upper', 'Keltner_Middle', 'Keltner_Lower']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.keltner(df, columns=["close", "low", "high"])
pyta.keltner(df, columns=["high", "low", "adj_close"])   # the adjusted close as the close
```

Unnamed input takes its columns in the order **high, low, close**, and returns a tuple of the three lines:

```python
import numpy as np

upper, middle, lower = pyta.keltner(np.column_stack([highs, lows, closes]))   # (rows, 3) or (3, rows)
upper, middle, lower = pyta.keltner((highs, lows, closes))                    # tuple of arrays
```

Keltner Channels are also in the volatility namespace; both names are the same function:

```python
pyta.volatility.keltner(df)   # same as pyta.keltner
from pyta.volatility import keltner
```

Many datasets in one call:

```python
results = pyta.batch.keltner([df1, df2, df3])              # list of results, in order
pyta.batch.volatility.keltner({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `period` | `int` | `20` | The EMA's period: bars in its seed average, and its weight `2 / (period + 1)`; at least `1` |
| `atr_period` | `int` | `10` | The ATR's period (Wilder's smoothing); at least `1` |
| `k` | `float` | `2.0` | Width of each band in ATRs; a finite number above 0 (an `int` is accepted) |
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

- Three outputs in the order `keltner_upper`, `keltner_middle`, `keltner_lower`, each the same length as the input, `float64`, in the input's price units. Upper is never below middle, and middle never below lower.
- Each output keeps its own warm-up:

  | Output | First value at row | Warm-up (`NaN`) rows |
  |---|---|---|
  | `keltner_middle` | `period - 1` (the EMA's) | `period - 1` |
  | `keltner_upper`, `keltner_lower` | `max(period - 1, atr_period)` (the later of the EMA and the ATR) | `max(period - 1, atr_period)` |

  With the defaults the middle line and the bands all start at row 19 (the ATR starts at row 10).
- At least `max(period, atr_period + 1)` rows are required, so every output has a value.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the three. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `KELTNER_UPPER` for `HIGH, LOW, CLOSE`, `Keltner_Upper` for `High, Low, Close` (no part of the name is an abbreviation).

## Edge cases

| Situation | Keltner Channels |
|---|---|
| A flat series (or high equal to low with an unchanged close) | ATR 0: three equal lines, the repeated value |
| `period = 1` | the middle line is the close |
| `atr_period = 1` | the ATR is each bar's true range |
| `k` so large that `k * ATR` overflows | infinite bands (not rejected) |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in every output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `max(period, atr_period + 1)` rows | `ValueError` |
| `period` or `atr_period` below 1 | `ValueError` |
| `k` zero, negative, `NaN` or infinite | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: Keltner Channels need three columns |

## Implementation notes

### The modern definition, and the original

Keltner Channels are not a TA-Lib function, and no standard defines them. PyTA follows the definition the major references share (StockCharts ChartSchool, TradingView): an EMA of close with bands a multiple of the ATR away.

Chester Keltner's original, in *How to Make Money in Commodities* (1960), was different: a 10-day **simple** moving average of the typical price `(high + low + close) / 3`, with bands one 10-day simple moving average of the range `high - low` above and below it. PyTA does not implement it. To approximate it with PyTA's functions, combine `pyta.sma` of the typical price with `pyta.sma` of `high - low`.

### Differences from charting platforms

The formula is the same everywhere; values can still differ slightly between platforms, mostly near the start of the data:

- **ATR smoothing and seeding.** PyTA's ATR is Wilder's, seeded with the mean of the first `atr_period` true ranges, as TA-Lib's `ATR`. TradingView, for example, may smooth or seed the ATR differently (and offers other band sources as options), so its bands can differ slightly from PyTA's; the difference from seeding fades as the smoothing forgets the seed.
- **EMA seeding.** The middle line follows TA-Lib's convention (seeded with the simple average of the first `period` closes), as `pyta.ema` does; a platform that seeds the EMA with the first close gives different early values.
- **Middle-line average.** Some scripts use a simple moving average for the middle line; PyTA always uses the EMA.

### Calculation

The Rust kernel (`pyta-volatility`) computes the middle line with the shared EMA kernel of `pyta-core`, the one `pyta.ema` uses, and the ATR with the same code as `pyta.atr`, so both match those functions bit for bit (tested on 300 real SPY sessions and by property tests); then one pass adds and subtracts `k * ATR`. The cost is proportional to the number of rows, independent of the periods and `k`. There is no reference library to compare with, so besides the bit-for-bit checks against PyTA's EMA and ATR (each checked against TA-Lib), a 12-row table worked by hand with exact fractions is stored in `tests/fixtures/keltner_hand.csv`, its derivation in the file's comments.

## See also

[ATR](atr.md) · [BBANDS](bbands.md) · [Donchian Channels](donchian.md) · [EMA](../trend/ema.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
