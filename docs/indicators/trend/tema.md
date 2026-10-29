# TEMA: Triple Exponential Moving Average

**Category:** Trend · **Function:** `pyta.tema` · **Batch:** `pyta.batch.tema` · **Default column:** close

## What it is

The TEMA is the second of Patrick Mulloy's faster moving averages ("Smoothing Data with Faster Moving Averages", *Technical Analysis of Stocks & Commodities*, February 1994), after the [DEMA](dema.md). It combines three cascaded [EMAs](ema.md) so that their lag cancels out. PyTA follows TA-Lib's `TA_TEMA`:

```
EMA1 = EMA(price, period)
EMA2 = EMA(EMA1, period)
EMA3 = EMA(EMA2, period)
TEMA = EMA3 + 3 × (EMA1 − EMA2)   (= 3 × EMA1 − 3 × EMA2 + EMA3)
```

Despite the name, the TEMA is **not** "an EMA of an EMA of an EMA": that would be `EMA3` alone, the slowest of the three. Each further EMA lags the one before by about the same amount, and the weights 3, −3 and 1 cancel that lag on a steady trend.

All three EMAs use `k = 2 / (period + 1)` and TA-Lib's seed: each starts with the plain mean of the first `period` values of its input, `EMA1` at row `period − 1`, `EMA2` at `2 × (period − 1)` and `EMA3` at `3 × (period − 1)`. The TEMA's first value is at that last row, so its warm-up is `3 × (period − 1)` rows (87 for the default period of 30), three times an EMA's.

## What it is for

- **Trend following with the least lag.** On a steady trend the TEMA follows the price with no delay, and it responds to a turn faster than a DEMA.
- **Crossovers.** Price crossing its TEMA, or a short TEMA crossing a long one.
- **Smoothing other indicators.** `pyta.tema(pyta.rsi(close), 9)` works because leading `NaN` is skipped. (TRIX, a momentum indicator, is the rate of change of `EMA3` alone.)

The price of less lag is overshoot: after a sudden move the TEMA runs further past the new level than a DEMA does before settling.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.tema(close, period=2)
# [nan, nan, nan, 43.67, 44.3, 44.84, 45.12, 45.43]
```

TEMA is also in the trend namespace; both names are the same function:

```python
pyta.trend.tema(close, period=2)     # same as pyta.tema
from pyta.trend import tema
```

```python
pyta.tema(df)                                 # period defaults to 30, as in TA-Lib
pyta.tema(df, period=10, column="adj close")  # a shorter period, on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.tema([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.trend.tema([df1, df2, df3])                  # same as pyta.batch.tema
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `30` | Period of all three EMAs, `1` to `2**31 - 1` (TA-Lib's default; TA-Lib caps it at 100,000). `1` returns the input unchanged |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`.
- The first `3 × (period − 1)` values are `NaN` (warm-up).
- At least `3 × period − 2` values are required.
- Named `tema` in a Series, DataFrame, dict, or JSON object (`TEMA` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | TEMA |
|---|---|
| Flat prices | The price itself |
| `period=1` | The input, unchanged |
| Exactly `3 × period − 2` values | One value, at the last row |
| A steady ramp | The price itself (no lag) |
| A step | Overshoots the new level, then settles back to it |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `3 × period − 2` values | `ValueError` (`at least … values are required`) |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) runs the three EMAs in one pass, with constant work per bar, using the same update and seeds as the shared EMA kernel (`pyta_core::kernels::ema`); a property test checks that it is bit for bit the result of three separate EMA passes, and the fused pass is about 3.1 times faster. The final sum is TA-Lib's, `EMA3 + (3 × EMA1 − 3 × EMA2)`, in that order. Mulloy's article does not fix how the EMAs start; PyTA follows TA-Lib, seeding each EMA with the plain mean of its first `period` inputs, which is why the warm-up is long. Libraries that seed from the first price give different early values that converge over time. TA-Lib 0.8.3 writes its EMA update as a fused multiply-add of `(period − 1) / (period + 1)` times the previous value plus `k` times the new one; PyTA keeps its EMA's form, `previous + k × (value − previous)`, so the two can differ in the last bits. PyTA matches TA-Lib's own output to `1e-9` on 300 real SPY closes and on a synthetic edge series with flat stretches, for period 30 (`tests/fixtures/tema_30_talib.csv`, `tema_30_edge_talib.csv`, generated with TA-Lib 0.8.3). TA-Lib rejects periods above 100,000; PyTA accepts any period the data covers.

## See also

[DEMA](dema.md) · [EMA](ema.md) · [KAMA](kama.md) · [SMA](sma.md) · [WMA](wma.md) · [MACD](macd.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
