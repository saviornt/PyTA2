# EMA: Exponential Moving Average

**Category:** Trend · **Function:** `pyta.ema` · **Batch:** `pyta.batch.ema` · **Default column:** close

## What it is

The EMA is a moving average that weights recent prices more than older ones, so it follows the price more closely than an [SMA](sma.md) of the same period. PyTA follows TA-Lib's `TA_EMA`:

1. The first value, at row `period - 1`, is the plain mean of the first `period` prices (the seed).
2. Each later value moves toward the current price by a fixed fraction of the gap: `EMA = previous + k × (price − previous)`, with `k = 2 / (period + 1)`.

Every past price keeps some weight, shrinking by the factor `1 − k` per bar.

## What it is for

- **Trend direction.** Price above a rising EMA suggests an uptrend; below a falling one, a downtrend.
- **Crossovers.** A short EMA crossing a long one (12 and 26 days, say) is a common trend-change signal; [MACD](macd.md) is built on exactly that difference.
- **Smoothing other indicators.** `pyta.ema(pyta.rsi(close), 9)` works because leading `NaN` is skipped.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.ema(close, period=5)
# [nan, nan, nan, nan, 44.1, 44.35, 44.6, 44.87]
```

EMA is also in the trend namespace; both names are the same function:

```python
pyta.trend.ema(close, period=5)      # same as pyta.ema
from pyta.trend import ema
```

```python
pyta.ema(df)                                # period defaults to 30, as in TA-Lib
pyta.ema(df, period=10, column="adj close") # a shorter period, on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.ema([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.trend.ema([df1, df2, df3])                  # same as pyta.batch.ema
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `30` | Smoothing period, at least `1` (TA-Lib's default). Shorter follows the price more closely; `1` returns the input unchanged |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`.
- The first `period - 1` values are `NaN` (warm-up).
- At least `period` values are required.
- Named `ema` in a Series, DataFrame, dict, or JSON object (`EMA` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | EMA |
|---|---|
| Flat prices | The price itself |
| `period=1` | The input, unchanged |
| `period` equal to the length | One value: the mean of all prices |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period` values | `ValueError` |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) makes one pass over the series, with constant work per bar; MACD runs the same arithmetic fused into its own single pass. Libraries seed the EMA differently: some start from the first price instead of the mean of the first `period` prices, so their early values differ from TA-Lib's and PyTA's, converging over time. PyTA matches TA-Lib's own output to `1e-9` on 300 real SPY closes, for periods 10 and 30 (`tests/fixtures/ema_10_talib.csv`, `ema_30_talib.csv`, generated with TA-Lib 0.8.3).

## See also

[SMA](sma.md) · [MACD](macd.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
