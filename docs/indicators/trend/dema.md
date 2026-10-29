# DEMA: Double Exponential Moving Average

**Category:** Trend · **Function:** `pyta.dema` · **Batch:** `pyta.batch.dema` · **Default column:** close

## What it is

The DEMA is Patrick Mulloy's answer to the lag of moving averages ("Smoothing Data with Faster Moving Averages", *Technical Analysis of Stocks & Commodities*, February 1994). It combines an [EMA](ema.md) with an EMA of that EMA so that most of the lag cancels out. PyTA follows TA-Lib's `TA_DEMA`:

```
EMA1 = EMA(price, period)
EMA2 = EMA(EMA1, period)
DEMA = 2 × EMA1 − EMA2
```

Despite the name, the DEMA is **not** "an EMA of an EMA": that would be `EMA2` alone, which lags even more than one EMA. `EMA1 − EMA2` estimates how far `EMA1` trails the price, and the DEMA adds that estimate back to `EMA1`.

Both EMAs use `k = 2 / (period + 1)` and TA-Lib's seed: `EMA1` starts at row `period − 1` with the plain mean of the first `period` prices, and `EMA2` starts at row `2 × (period − 1)` with the plain mean of the first `period` values of `EMA1`. The DEMA's first value is at that row, so its warm-up is `2 × (period − 1)` rows (58 for the default period of 30), twice an EMA's.

## What it is for

- **Trend following with less lag.** On a steady trend a DEMA follows the price with almost no delay, where an EMA lags by `(period − 1) / 2` bars.
- **Crossovers.** Price crossing its DEMA, or a short DEMA crossing a long one, signal earlier than the same EMAs would.
- **Smoothing other indicators.** `pyta.dema(pyta.rsi(close), 9)` works because leading `NaN` is skipped.

The price of less lag is overshoot: after a sudden move the DEMA runs past the new level for a while before settling, which an EMA never does.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.dema(close, period=3)
# [nan, nan, nan, nan, 44.16, 44.67, 45.04, 45.39]
```

DEMA is also in the trend namespace; both names are the same function:

```python
pyta.trend.dema(close, period=3)     # same as pyta.dema
from pyta.trend import dema
```

```python
pyta.dema(df)                                 # period defaults to 30, as in TA-Lib
pyta.dema(df, period=10, column="adj close")  # a shorter period, on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.dema([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.trend.dema([df1, df2, df3])                  # same as pyta.batch.dema
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `30` | Period of both EMAs, `1` to `2**31 - 1` (TA-Lib's default; TA-Lib caps it at 100,000). `1` returns the input unchanged |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`.
- The first `2 × (period − 1)` values are `NaN` (warm-up).
- At least `2 × period − 1` values are required.
- Named `dema` in a Series, DataFrame, dict, or JSON object (`DEMA` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | DEMA |
|---|---|
| Flat prices | The price itself |
| `period=1` | The input, unchanged |
| Exactly `2 × period − 1` values | One value, at the last row |
| A steady ramp | The price itself (no lag) |
| A step | Overshoots the new level, then settles back to it |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `2 × period − 1` values | `ValueError` (`at least … values are required`) |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) runs both EMAs in one pass, with constant work per bar, using the same update and seeds as the shared EMA kernel (`pyta_core::kernels::ema`); a property test checks that it is bit for bit the result of two separate EMA passes, and the fused pass is about 2.3 times faster. Mulloy's article does not fix how the EMAs start; PyTA follows TA-Lib, seeding each EMA with the plain mean of its first `period` inputs, which is why the warm-up is long. Libraries that seed from the first price give different early values that converge over time. TA-Lib 0.8.3 writes its EMA update as a fused multiply-add of `(period − 1) / (period + 1)` times the previous value plus `k` times the new one; PyTA keeps its EMA's form, `previous + k × (value − previous)`, so the two can differ in the last bits. PyTA matches TA-Lib's own output to `1e-9` on 300 real SPY closes and on a synthetic edge series with flat stretches, for period 30 (`tests/fixtures/dema_30_talib.csv`, `dema_30_edge_talib.csv`, generated with TA-Lib 0.8.3). TA-Lib rejects periods above 100,000; PyTA accepts any period the data covers.

## See also

[EMA](ema.md) · [TEMA](tema.md) · [SMA](sma.md) · [WMA](wma.md) · [MACD](macd.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
