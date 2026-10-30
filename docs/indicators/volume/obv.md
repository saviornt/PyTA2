# On-Balance Volume (OBV)

**Category:** Volume · **Function:** `pyta.obv` · **Batch:** `pyta.batch.obv` · **Columns:** close, volume

## What it is

On-Balance Volume is a running total of volume that goes up on up days and down on down days. Joseph Granville introduced it in 1963 to show whether volume is flowing into or out of an asset.

1. OBV starts at the first bar's volume.
2. When a bar closes **above** the previous close, its volume is **added**.
3. When it closes **below**, its volume is **subtracted**.
4. When the close is **unchanged**, OBV stays where it was.

The level itself means little (it depends on where the data starts); its direction and slope are what is read.

## What it is for

- **Confirmation.** A rising price with rising OBV is a move backed by volume; a rising price with flat or falling OBV is not.
- **Divergences.** OBV making a new high while price does not (or the reverse) is read as volume leading price.
- **Breakouts.** A breakout in OBV ahead of price is sometimes taken as an early signal.

## Usage

OBV needs two columns, so pass data in a container that has column names. PyTA finds the close and volume columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.obv(df)                     # a DataFrame with one column, "obv"
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.obv({"Close": closes, "Volume": volumes})
# {"OBV": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.obv(df, columns=["adj close", "volume"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **close, volume**:

```python
import numpy as np

pyta.obv(np.column_stack([closes, volumes]))   # 2-D array (rows, 2) or (2, rows) -> 1-D array
pyta.obv((closes, volumes))                    # tuple of arrays -> tuple
```

OBV is also in the volume namespace; both names are the same function:

```python
pyta.volume.obv(df)   # same as pyta.obv
```

A signal line is not part of OBV; smooth it with another indicator, for example `pyta.ema(pyta.obv(df)["obv"], 20)`.

Many datasets in one call:

```python
results = pyta.batch.obv([df1, df2, df3])          # list of results, in order
pyta.batch.volume.obv({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | Close and volume; other columns are ignored |
| `columns` | list of `str` or `None` | `None` | The two columns to use, in any order: a close or adjusted close, and a volume. `None` finds them by name. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

OBV has no parameters. `column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| close | `close`, or else `adj_close` | 1st |
| volume | `volume` | 2nd |

## Output

- Same length as the input, `float64`.
- No warm-up: every row has a value, and one row is enough.
- Named `obv` in a DataFrame, dict, JSON object or CSV (`OBV` when the columns used are all upper case or all title case, as yfinance's `Close`, `Volume`: it is an abbreviation). A dict keeps the container type of its close column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | OBV |
|---|---|
| First row | Its volume |
| Close equal to the previous close | Unchanged |
| Zero volume on a bar | Unchanged on that bar (zero volume is valid) |
| Flat prices throughout | The first bar's volume on every row |

With whole-number volumes, every value is exact (the sums stay far below `2^53` for real volumes), so results match TA-Lib's to the bit.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in either column | Rows up to the last leading `NaN` of either column are skipped, then re-padded with `NaN` in the output; OBV then starts at the first complete row's volume |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| Negative volume on any row | `ValueError` naming the column and the row (zero is valid) |
| A list, 1-D array or Series (one series) | `TypeError`: OBV needs two columns |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_OBV` exactly: the first value is the first volume, then the volume is added on a higher close, subtracted on a lower one, and nothing is done on an equal close (an exact comparison). Both TA-Lib fixtures match bit for bit. Granville's definition is the same; some platforms start OBV at 0 instead of the first volume, which shifts every value by that volume and changes nothing else.

The Rust kernel (`pyta-volume`) is one pass with one comparison and one addition per row.

## See also

[Accumulation/Distribution](ad.md) · [Chaikin Money Flow](cmf.md) · [Volume ROC](vroc.md) · [Volume indicators](README.md) · [MFI](../momentum/mfi.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
