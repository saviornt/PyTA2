# WMA: Weighted Moving Average

**Category:** Trend · **Function:** `pyta.wma` · **Batch:** `pyta.batch.wma` · **Default column:** close

## What it is

The WMA is a moving average whose weights fall in a straight line from the newest price to the oldest, so it reacts faster than an [SMA](sma.md) of the same period but, unlike an [EMA](ema.md), forgets a price completely once it leaves the window. PyTA follows TA-Lib's `TA_WMA`:

```
WMA = (1 × p[t − period + 1] + 2 × p[t − period + 2] + … + period × p[t]) / (period × (period + 1) / 2)
```

The oldest price in the window weighs 1, the newest `period`; the divisor is the sum of the weights. For period 5 the weights are 1, 2, 3, 4, 5 over 15.

## What it is for

- **Trend direction with less lag.** On a steady trend a WMA lags the price by `(period − 1) / 3` bars, against `(period − 1) / 2` for an SMA.
- **Crossovers.** Price crossing its WMA, or a short WMA crossing a long one, as with other moving averages.
- **Building block.** The Hull Moving Average is made of WMAs; `pyta.wma(pyta.rsi(close), 9)` smooths another indicator, since leading `NaN` is skipped.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.wma(close, period=5)
# [nan, nan, nan, nan, 44.07, 44.31, 44.61, 44.95]
```

WMA is also in the trend namespace; both names are the same function:

```python
pyta.trend.wma(close, period=5)      # same as pyta.wma
from pyta.trend import wma
```

```python
pyta.wma(df)                                # period defaults to 30, as in TA-Lib
pyta.wma(df, period=10, column="adj close") # a shorter period, on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.wma([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.trend.wma([df1, df2, df3])                  # same as pyta.batch.wma
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `30` | Window length, `1` to `2**31 - 1` (TA-Lib's default; TA-Lib caps it at 100,000). `1` returns the input unchanged |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`.
- The first `period - 1` values are `NaN` (warm-up).
- At least `period` values are required.
- Named `wma` in a Series, DataFrame, dict, or JSON object (`WMA` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | WMA |
|---|---|
| Flat prices | The price itself |
| `period=1` | The input, unchanged |
| `period` equal to the length | One value: the weighted mean of all prices |
| A steady ramp | The price `(period − 1) / 3` bars ago |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period` values | `ValueError` (period larger than the series) |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) keeps two running sums, the window's plain sum and its weighted sum, and updates both in constant work per bar: when the window slides, every weight drops by one (`weighted − plain`) and the new price enters with weight `period`. As in TA-Lib, both sums are rebuilt from the window every `8 × period` bars, so rounding cannot build up over a long series; on 100,000-row random walks the result stays within `1e-9` of each window's directly summed WMA (property test). The weights are the original linearly weighted average's; TA-Lib and PyTA agree with it. PyTA matches TA-Lib's own output to `1e-9` on 300 real SPY closes for periods 10 and 30 and on a synthetic edge series with flat stretches (`tests/fixtures/wma_10_talib.csv`, `wma_30_talib.csv`, `wma_30_edge_talib.csv`, generated with TA-Lib 0.8.3). TA-Lib rejects periods above 100,000; PyTA accepts any period the data covers.

## See also

[SMA](sma.md) · [EMA](ema.md) · [MACD](macd.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
