# Chaikin Money Flow (CMF)

**Category:** Volume · **Function:** `pyta.cmf` · **Batch:** `pyta.batch.cmf` · **Columns:** high, low, close, volume

## What it is

Chaikin Money Flow measures buying and selling pressure over a fixed window: the share of the window's volume that came with closes near the high (positive) or near the low (negative). Marc Chaikin built it from the same money-flow volume as his [Accumulation/Distribution line](ad.md).

1. Each bar's **money-flow multiplier** is `((close − low) − (high − close)) / (high − low)`: `1` at the high, `−1` at the low, `0` halfway (and `0` for a one-price bar).
2. Its **money-flow volume** is the multiplier × the bar's volume.
3. Over the last `period` bars, the current one included: `CMF = sum(money-flow volume) / sum(volume)`.

The result runs from **−1** (every bar closed at its low) to **1** (every bar closed at its high).

## What it is for

- **Buying or selling pressure.** Above 0 is read as accumulation, below 0 as distribution; readings beyond ±0.1 or ±0.25 are often used as thresholds to filter noise.
- **Confirmation and divergences.** CMF staying positive through a rally confirms it; CMF turning down while prices rise is read as a warning.
- **Unlike A/D**, which is a running total that never forgets, CMF looks only at its window, so it returns towards 0 when pressure fades.

## Usage

CMF needs four columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low, close and volume columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.cmf(df, period=20)          # a DataFrame with one column, "cmf"
pyta.cmf(df)                     # period defaults to 20
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.cmf({"High": highs, "Low": lows, "Close": closes, "Volume": volumes}, 21)
# {"CMF": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.cmf(df, columns=["high", "low", "adj close", "volume"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close, volume**:

```python
import numpy as np

pyta.cmf(np.column_stack([highs, lows, closes, volumes]))   # 2-D array (rows, 4) or (4, rows) -> 1-D array
pyta.cmf((highs, lows, closes, volumes))                    # tuple of arrays -> tuple
```

CMF is also in the volume namespace; both names are the same function:

```python
pyta.volume.cmf(df)   # same as pyta.cmf
```

Many datasets in one call:

```python
results = pyta.batch.cmf([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.volume.cmf({"SPY": spy, "QQQ": qqq})        # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low, close and volume; other columns are ignored |
| `period` | `int` | `20` | Bars in each sum, the current one included, at least `1` (StockCharts' default; TradingView uses 20 or 21; TA-Lib has no CMF) |
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

- Same length as the input, `float64`, between −1 and 1 (when every close lies inside its bar).
- The first `period − 1` values are `NaN` (warm-up).
- At least `period` rows are required.
- Named `cmf` in a DataFrame, dict, JSON object or CSV (`CMF` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`, `Volume`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | CMF |
|---|---|
| Every close at its high in the window | `1` |
| Every close at its low in the window | `−1` |
| A one-price bar (high equal to low) | Its multiplier is `0`: its volume counts in the total, its money flow does not (as A/D adds nothing for it) |
| No volume at all in the window | `NaN` (the ratio is undefined); the next window with volume has a value again |
| Zero volume on some bars | Valid; those bars add nothing to either sum |
| `period=1` | The bar's own multiplier (`NaN` on a bar without volume) |

The two window sums are running sums with compensation (each new bar added and the leaving bar subtracted exactly), so they stay as accurate as fresh window sums over any length of data, even after a window of huge volumes is followed by small ones. Whether a window has volume is decided by counting its non-zero volumes, never by a rounded sum.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Negative volume on any row | `ValueError` naming the column and the row (zero is valid) |
| Fewer than `period` rows | `ValueError` (`period (20) exceeds the series length (10)`) |
| `period` below 1 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: CMF needs several columns |

## Implementation notes

TA-Lib has no CMF, so PyTA follows Chaikin's definition as StockCharts and TradingView give it: a window of `period` bars including the current one, the money-flow multiplier of [A/D](ad.md) (TA-Lib's `AD` order of operations, and `0` for a one-price bar, as A/D adds nothing for it), and the default of 20. A window whose volume is all zero gives `NaN` rather than `0`, since no money flowed at all. The values are checked against a hand-computed table (`tests/fixtures/cmf_hand.csv`, with a one-price bar and a window without volume) and against fresh window sums on real SPY data to `1e-12`.

The Rust kernel (`pyta-volume`) keeps the window's money-flow volumes in a ring and two compensated running sums (Knuth's two-sum with Neumaier compensation, from `pyta-core`), so its cost does not depend on `period`; the multiplier is the helper A/D uses.

## See also

[Accumulation/Distribution](ad.md) · [MFI](../momentum/mfi.md) · [OBV](obv.md) · [VWAP](vwap.md) · [Volume indicators](README.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
