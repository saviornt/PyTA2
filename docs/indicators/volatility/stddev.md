# STDDEV: Standard Deviation

**Category:** Volatility · **Function:** `pyta.stddev` · **Batch:** `pyta.batch.stddev` · **Default column:** close

## What it is

The rolling standard deviation measures how widely prices are spread around their own recent average. A quiet market gives a small value; a market swinging back and forth gives a large one. It is measured in the same units as the prices.

For each bar, over the last `period` values:

1. The **mean** is the plain average of the window.
2. The **variance** is the average squared distance from that mean, dividing by `period` (the *population* variance).
3. **STDDEV** is the square root of the variance, multiplied by `k`.

## What it is for

- **Volatility.** Rising STDDEV means prices are moving further from their average; falling STDDEV means the market is calming down. Low readings often come before large moves.
- **Bands.** Bollinger Bands are the moving average plus and minus `k` standard deviations; `pyta.stddev(close, 20, k=2)` is exactly that band width on each side.
- **Position sizing and stops.** A stop or position size scaled by recent standard deviation adapts to how much the instrument usually moves.
- **Chaining.** `pyta.sma(pyta.stddev(close, 20), 10)` smooths the volatility itself, because leading `NaN` is skipped.

## Usage

```python
import pyta

close = [10.0, 11.0, 12.0, 11.0, 10.0, 10.0, 10.0, 10.0, 10.0]

pyta.stddev(close, period=5)
# [nan, nan, nan, nan, 0.748, 0.748, 0.8, 0.4, 0.0]  (rounded)
```

STDDEV is also in the volatility namespace; both names are the same function:

```python
pyta.volatility.stddev(close, period=5)  # same as pyta.stddev
from pyta.volatility import stddev
```

```python
pyta.stddev(df)                       # period 5, k 1.0 (TA-Lib's defaults)
pyta.stddev(df, period=20, k=2.0)     # the half-width of 20-bar, 2-sigma Bollinger Bands
pyta.stddev(df, period=20, column="adj close")
```

Many datasets in one call:

```python
results = pyta.batch.stddev([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.volatility.stddev([df1, df2, df3])             # same as pyta.batch.stddev
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON, CSV | required | Prices |
| `period` | `int` | `5` | Number of values in each window, at least `2` (TA-Lib's minimum; one value has no spread) |
| `k` | `float` | `1.0` | Multiplier (TA-Lib's `nbdev`), any finite number above `0`; an `int` is accepted. `2.0` gives a two-sigma width |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`, never negative.
- The first `period - 1` values are `NaN` (warm-up).
- At least `period` values are required.
- Named `stddev` in a Series, DataFrame, dict, or JSON object (`STDDEV` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | STDDEV |
|---|---|
| A flat window (every value the same) | exactly `0` |
| `period` equal to the input length | one value, the deviation of the whole series |
| A large price with a tiny spread (`100000 + 0.001 × noise`) | full precision (see Implementation notes) |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period` values | `ValueError` |
| `period` below 2, or `k` zero, negative or not finite | `ValueError` naming the parameter |
| Empty input | `ValueError` |

## Implementation notes

- **TA-Lib convention.** PyTA follows TA-Lib's `TA_STDDEV` (0.8.3): the population standard deviation, dividing by `period`, times `nbdev` (here `k`), with the same default period (5) and minimum (2). Results match TA-Lib to within `1e-9` relative on real SPY closes and on an edge-case series.
- **Population, not sample.** Statistics packages often divide by `period - 1` (the *sample* deviation: pandas' `rolling().std()` by default, NumPy's `std(ddof=1)`). TA-Lib, Bollinger and PyTA divide by `period`, so PyTA's value is `sqrt((period - 1) / period)` times pandas' default; use `rolling(period).std(ddof=0)` to compare.
- **Stable calculation.** Each window is centred on its own mean and its squared distances are summed afresh (a two-pass calculation per window, from the shared `pyta-core` kernel). Older TA-Lib releases used a running sum of squares, `mean(x²) − mean(x)²`, which loses most of its digits when prices are large and the spread small (a price near 100,000 moving by 0.001); PyTA keeps full precision there. The cost is `O(rows × period)`, not `O(rows)`.
- **Flat windows.** The window's mean can miss a repeated value by one unit in the last place, which would leave a deviation of about `1e-16` of the price. A deviation within `1e-14` of the window's mean (TA-Lib's own zero tolerance, `TA_IS_ZERO_SCALED`) is reported as exactly `0`, as TA-Lib gives on a flat window. A real spread is far larger: a one-tick move of `1e-8` on a price of 100 is `1e-10` of it.

## See also

[ATR](atr.md) · [SMA](../trend/sma.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
