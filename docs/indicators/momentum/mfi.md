# Money Flow Index (MFI)

**Category:** Momentum · **Function:** `pyta.mfi` · **Batch:** `pyta.batch.mfi` · **Columns:** high, low, close, volume

## What it is

The Money Flow Index weighs price changes by volume: it is the share of the last `period` bars' money flow that came on rising prices. It was introduced by Gene Quong and Avrum Soudack in 1989, and is often described as a volume-weighted RSI.

1. Each bar's **typical price** is `(high + low + close) / 3`, and its **money flow** is typical price × volume.
2. A bar's money flow is **positive** when its typical price is above the previous bar's, **negative** when it is below, and counts as neither when it is unchanged.
3. Over the last `period` bars, sum the positive and the negative money flow.
4. `MFI = 100 × positive / (positive + negative)`.

The result runs from **0** (all the money flow on falling prices) to **100** (all of it on rising prices).

## What it is for

- **Overbought and oversold.** Readings above 80 are usually read as overbought and below 20 as oversold (some use 90 and 10).
- **Divergences.** Price making a new high while MFI makes a lower high (or the reverse at lows) is read as a move losing support from volume.
- **Volume confirmation.** Next to RSI, MFI shows whether a price move came on heavy or light volume.

## Usage

MFI needs four columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low, close and volume columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.mfi(df, period=14)          # a DataFrame with one column, "mfi"
pyta.mfi(df)                     # period defaults to 14
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.mfi({"High": highs, "Low": lows, "Close": closes, "Volume": volumes})
# {"MFI": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.mfi(df, columns=["high", "low", "adj close", "volume"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close, volume**:

```python
import numpy as np

pyta.mfi(np.column_stack([highs, lows, closes, volumes]))   # 2-D array (rows, 4) or (4, rows) -> 1-D array
pyta.mfi((highs, lows, closes, volumes))                    # tuple of arrays -> tuple
```

MFI is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.mfi(df)   # same as pyta.mfi
```

Many datasets in one call:

```python
results = pyta.batch.mfi([df1, df2, df3], period=14)   # list of results, in order
pyta.batch.momentum.mfi({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low, close and volume; other columns are ignored |
| `period` | `int` | `14` | Bars of money flow in each sum, at least `2` (TA-Lib's minimum and default; Quong and Soudack also use 14) |
| `columns` | list of `str` or `None` | `None` | The four columns to use, in any order: a high, a low, a close or adjusted close, and a volume. `None` finds them by name. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |
| volume | `volume` | 4th |

## Output

- Same length as the input, `float64`, between 0 and 100.
- The first `period` values are `NaN` (warm-up: the first bar has no previous typical price to compare with).
- At least `period + 1` rows are required.
- Named `mfi` in a DataFrame, dict, JSON object or CSV (`MFI` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`, `Volume`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | MFI |
|---|---|
| Only rising typical prices in the window | `100` |
| Only falling typical prices in the window | `0` |
| No money flow at all in the window (typical price unchanged on every bar, or zero volume) | `0` |
| Typical price unchanged on a bar | That bar's money flow counts as neither positive nor negative |
| Zero volume on a bar | That bar adds no money flow (zero volume is valid) |

"Unchanged" allows a change of `1e-14` of the two typical prices' `|a| + |b|`, as TA-Lib 0.8.3 does, so rounding noise in the typical price is not read as a move. The sums are running totals (add the newest bar, subtract the one leaving), as TA-Lib's are; after `period` bars in a row with no money flow both are reset to exactly 0, so an empty window gives exactly 0 rather than a ratio of rounding residue. Price × volume is a product of two inputs: if it would overflow (prices and volumes both near the `1e290` input limit), PyTA scales the volume by a power of two, which changes no ratio, so the result stays finite.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Negative volume on any row | `ValueError` naming the column and the row (zero is valid) |
| Fewer than `period + 1` rows | `ValueError` (`at least 15 values are required, got 10`) |
| `period` below 2 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: MFI needs several columns |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_MFI`: the typical price added left to right, the scaled "unchanged" test, the running sums with their subtract-then-add order, the reset after a window without money flow, the positive sum clamped into `[0, total]`, and `0` for an empty window. Every value of the TA-Lib fixtures matches bit for bit. The warm-up (`period`), the default (14) and the minimum period (2) are TA-Lib's; TA-Lib caps `period` at 100,000, PyTA does not. Quong and Soudack's definition is the same calculation, written `100 − 100 / (1 + money ratio)`; TA-Lib's form `100 × positive / (positive + negative)` is algebraically equal and is the one used. Older TA-Lib releases treated an unchanged typical price and an empty window differently (fixed thresholds), so they can differ from PyTA on flat data.

The Rust kernel (`pyta-momentum`) uses the shared typical price from `pyta-core` and, like TA-Lib, keeps the last `period` flows in a ring buffer to subtract the bar leaving the window; its cost does not depend on `period`.

## See also

[RSI](rsi.md) · [Stochastic Oscillator](stoch.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
