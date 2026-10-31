# KAMA: Kaufman Adaptive Moving Average

**Category:** Trend · **Function:** `pyta.kama` · **Batch:** `pyta.batch.kama` · **Default column:** close

## What it is

Perry Kaufman's Adaptive Moving Average (*Smarter Trading*, 1995) is an exponential moving average whose weight changes every bar with how efficiently the price is moving. In a clean trend it follows the price closely; in sideways noise it barely moves. PyTA follows TA-Lib's `TA_KAMA`:

```
change     = |price − price period bars ago|
volatility = sum of |price − previous price| over the last period bars
ER         = change / volatility                     (efficiency ratio, 0 to 1)
SC         = (ER × (fast − slow) + slow)²            fast = 2/(2+1), slow = 2/(30+1)
KAMA       = previous KAMA + SC × (price − previous KAMA)
```

The efficiency ratio is 1 when every bar in the window moved the same way (the net change equals the total distance travelled) and near 0 when the price went back and forth and ended where it started. The smoothing constant `SC` then lies between the weight of a 2-bar EMA squared (fast, about 0.44) and that of a 30-bar EMA squared (slow, about 0.004). The fast and slow constants are fixed at 2 and 30, as in TA-Lib, which has no parameters for them.

The first KAMA is calculated at row `period` and starts from the previous price (row `period − 1`) as its previous value, TA-Lib's seed. The warm-up is therefore `period` rows (30 for the default period).

## What it is for

- **Trend following that ignores chop.** KAMA stays nearly flat while the market is noisy and moves with the price once a trend starts, so fewer false signals come from sideways stretches than with an EMA of similar speed.
- **Trend direction and filters.** A rising or falling KAMA, or price above or below it, as a trend filter.
- **Crossovers.** Price crossing its KAMA, or a short KAMA crossing a long one.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.kama(close, period=3)
# [nan, nan, nan, 43.97, 43.98, 44.05, 44.52, 44.92]
```

KAMA is also in the trend namespace; both names are the same function:

```python
pyta.trend.kama(close, period=3)     # same as pyta.kama
from pyta.trend import kama
```

```python
pyta.kama(df)                                 # period defaults to 30, as in TA-Lib
pyta.kama(df, period=10)                      # Kaufman's own efficiency-ratio period
pyta.kama(df, period=10, column="adj close")  # on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.kama([df1, df2, df3], period=10)   # list of results, in order
pyta.batch.trend.kama([df1, df2, df3])                  # same as pyta.batch.kama
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `30` | Bars in the efficiency ratio's window, `1` to `2**31 - 1` (TA-Lib's default; Kaufman and StockCharts use 10; TA-Lib caps it at 100,000). `1` returns the input unchanged |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`.
- The first `period` values are `NaN` (warm-up); with `period=1` there is none.
- At least `period + 1` values are required (one for `period=1`).
- Named `kama` in a Series, DataFrame, dict, or JSON object (`KAMA` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | KAMA |
|---|---|
| Flat prices | The price itself |
| `period=1` | The input, unchanged (TA-Lib's convention, matching its other moving averages) |
| Exactly `period + 1` values | One value, at the last row |
| A steady trend in one direction | Efficiency ratio 1: the fastest weight, about 0.44 |
| Prices that end the window where they started | Efficiency ratio 0: the slowest weight, about 0.004 |
| A window with no price change at all (`period` unchanged bars) | Efficiency ratio 1, as in TA-Lib; KAMA closes in on the flat price |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period + 1` values | `ValueError` (`at least … values are required`) |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) keeps the window's sum of one-bar changes as a running total (the change leaving the window subtracted, then the new one added, TA-Lib's order), so each bar costs the same whatever the period. It copies TA-Lib 0.8.3's guards exactly. The efficiency ratio is 1 when the sum is zero or not above the signed net change, and is otherwise clamped to at most 1, because a running sum can drift just below the net change. A run of `period` bars with a change of exactly zero marks the window as flat: the running sum is reset to exactly 0, dropping the rounding residue that add-then-subtract leaves behind, and the ratio is 1. These are exact zero tests, not a tolerance. TA-Lib's source writes the two multiply-adds as fused (`fma`); PyTA computes them plainly, as its EMA does, because a fused multiply-add is a library call on a default x86-64 build and more than doubled the kernel's time. PyTA still reproduces TA-Lib 0.8.3's output bit for bit on 300 real SPY closes and on a synthetic edge series with a 35-bar flat stretch, a gap and a zero price, for period 30 (`tests/fixtures/kama_30_talib.csv`, `kama_30_edge_talib.csv`, compared to `1e-9` relative). PyTA promises agreement with TA-Lib 0.8.3 within `1e-9`, not bit for bit, and uses plain multiplies and adds everywhere, never a fused multiply-add or code picked by CPU at run time ([API: Agreement with TA-Lib](../../API.md#agreement-with-ta-lib)).

Kaufman's own default efficiency-ratio period is 10; PyTA keeps TA-Lib's 30 so that code switching from TA-Lib gets the same numbers without arguments. StockCharts' KAMA(10, 2, 30) uses the same formula but seeds the first KAMA with a simple moving average of the first 10 prices instead of the previous price; the two start apart and converge as the seed's weight decays. TA-Lib rejects periods above 100,000; PyTA accepts any period the data covers.

## See also

[EMA](ema.md) · [DEMA](dema.md) · [TEMA](tema.md) · [SMA](sma.md) · [WMA](wma.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
