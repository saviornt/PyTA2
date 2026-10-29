# RSI: Relative Strength Index

**Category:** Momentum · **Function:** `pyta.rsi` · **Batch:** `pyta.batch.rsi` · **Default column:** close

## What it is

The RSI measures how strongly price has been moving up compared with down over recent bars, on a scale from 0 to 100. It was introduced by J. Welles Wilder, and PyTA uses his original smoothing.

1. For each bar, the change from the previous bar is a **gain** (if positive) or a **loss** (if negative, stored as a positive number).
2. The first average gain and average loss are the plain means of the first `period` changes.
3. After that, each average is smoothed: `new_average = (previous_average × (period − 1) + latest) / period`.
4. `RS = average gain / average loss`, and `RSI = 100 − 100 / (1 + RS)`.

## What it is for

- **Overbought and oversold.** By convention, an RSI above 70 suggests the price has risen fast and may be stretched; below 30 suggests it has fallen fast and may be due for a bounce. These are prompts to look closer, not signals on their own, and strong trends can stay beyond them for a long time.
- **Momentum.** RSI above 50 means gains have outweighed losses recently; below 50 the opposite.
- **Divergence.** Price making a new high while RSI does not is often read as weakening momentum.
- **Chaining.** Smoothing the RSI itself, as in `pyta.sma(pyta.rsi(close), 5)`, works because leading `NaN` is skipped.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
         45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]

pyta.rsi(close, period=14)
# [nan, ... 14 times ..., 70.46, 66.25]
```

RSI is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.rsi(close, period=14)  # same as pyta.rsi
from pyta.momentum import rsi
```

```python
pyta.rsi(df)                                # period defaults to 14
pyta.rsi(df, period=9, column="adj close")  # a shorter period, on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.rsi([df1, df2, df3], period=14)   # list of results, in order
pyta.batch.momentum.rsi([df1, df2, df3])               # same as pyta.batch.rsi
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `period` | `int` | `14` | Number of price changes in the first average, at least `1`. Wilder's choice is 14; shorter is more sensitive, longer is smoother |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |

## Output

- Same length as the input, `float64`, always between 0 and 100.
- The first `period` values are `NaN` (warm-up): `period` changes need `period + 1` prices.
- At least `period + 1` values are required.
- Named `rsi` in a Series, DataFrame, dict, or JSON object (`RSI` when the input column is `CLOSE` or `Close`; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | RSI |
|---|---|
| Only gains, no losses | `100` |
| Only losses, no gains | `0` |
| No movement at all (flat prices) | `0` |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period + 1` values | `ValueError` |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-momentum`) makes one pass over the series, with constant work per bar. The result matches Wilder's original method, not the simple-average variant some libraries use, so values can differ slightly from tools that average gains and losses with a plain window.

## See also

[SMA](../trend/sma.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
