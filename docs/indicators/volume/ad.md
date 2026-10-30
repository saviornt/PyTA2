# Accumulation/Distribution (A/D)

**Category:** Volume · **Function:** `pyta.ad` · **Batch:** `pyta.batch.ad` · **Columns:** high, low, close, volume

## What it is

The Accumulation/Distribution line is a running total of volume weighted by where each bar closes within its range. Marc Chaikin introduced it to measure buying (accumulation) and selling (distribution) pressure.

1. Each bar's **money-flow multiplier** is `((close − low) − (high − close)) / (high − low)`: `1` when the bar closes at its high, `−1` at its low, `0` halfway.
2. Its **money-flow volume** is the multiplier × the bar's volume.
3. A/D is the **running total** of the money-flow volumes, starting from 0 (so the first bar already holds its own).

Unlike OBV, which adds or subtracts the whole volume by the direction of the close, A/D adds the share of the volume that the close's position in the bar suggests.

## What it is for

- **Confirmation.** A rising A/D line with rising prices shows buying pressure behind the move.
- **Divergences.** Prices making new highs while A/D falls (or the reverse) is read as distribution (or accumulation) under the surface.
- **Building block.** The Chaikin Oscillator is `EMA(A/D, 3) − EMA(A/D, 10)`: `pyta.ema(line, 3) − pyta.ema(line, 10)` with `line = pyta.ad(df)["ad"]`.

## Usage

A/D needs four columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low, close and volume columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.ad(df)                      # a DataFrame with one column, "ad"
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.ad({"High": highs, "Low": lows, "Close": closes, "Volume": volumes})
# {"AD": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.ad(df, columns=["high", "low", "adj close", "volume"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close, volume**:

```python
import numpy as np

pyta.ad(np.column_stack([highs, lows, closes, volumes]))   # 2-D array (rows, 4) or (4, rows) -> 1-D array
pyta.ad((highs, lows, closes, volumes))                    # tuple of arrays -> tuple
```

A/D is also in the volume namespace; both names are the same function:

```python
pyta.volume.ad(df)   # same as pyta.ad
```

Many datasets in one call:

```python
results = pyta.batch.ad([df1, df2, df3])          # list of results, in order
pyta.batch.volume.ad({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low, close and volume; other columns are ignored |
| `columns` | list of `str` or `None` | `None` | The four columns to use, in any order: a high, a low, a close or adjusted close, and a volume. `None` finds them by name. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

A/D has no parameters. `column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |
| volume | `volume` | 4th |

## Output

- Same length as the input, `float64`.
- No warm-up: every row has a value, and one row is enough.
- Named `ad` in a DataFrame, dict, JSON object or CSV (`AD` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`, `Volume`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | A/D |
|---|---|
| Close at the high | Adds the whole volume |
| Close at the low | Subtracts the whole volume |
| Close halfway between high and low | Adds 0 |
| A one-price bar (high equal to low) | Adds nothing, as TA-Lib (the multiplier would be `0 / 0`) |
| Zero volume on a bar | Adds nothing (zero volume is valid) |

A close outside its bar is not checked (TA-Lib does not either): its multiplier is then beyond `±1`, and with a very narrow bar it can be large enough to overflow the total to `±inf`, as in TA-Lib. With every close inside its bar, each step is at most that bar's volume.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output; the total then starts at the first complete row |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Negative volume on any row | `ValueError` naming the column and the row (zero is valid) |
| A list, 1-D array or Series (one series) | `TypeError`: A/D needs several columns |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_AD` exactly: `((close − low) − (high − close)) / (high − low) × volume` in that order of operations, added to a running total that starts at 0, and nothing added when `high − low` is not above 0. Both TA-Lib fixtures (SPY, with totals near `1e10`, and the edge series with its one-price bar, flat stretch and zero volumes) match bit for bit. Chaikin's definition is the same; StockCharts writes the multiplier as `((close − low) − (high − close)) / (high − low)` too.

The Rust kernel (`pyta-volume`) is one pass; the multiplier is a crate-private helper that [Chaikin Money Flow](cmf.md) shares.

## See also

[Chaikin Money Flow](cmf.md) · [OBV](obv.md) · [Volume indicators](README.md) · [MFI](../momentum/mfi.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
