# ATR: Average True Range

**Category:** Volatility · **Function:** `pyta.atr` · **Batch:** `pyta.batch.atr` · **Columns:** high, low, close

## What it is

The ATR measures how much the price typically moves in one bar, gaps included. J. Welles Wilder Jr. introduced it in *New Concepts in Technical Trading Systems* (1978), for commodities, and it is used on any market.

1. For each bar, the **true range** is the largest of:
   - `high − low` (the bar's own range),
   - `|high − previous close|` (a gap up),
   - `|low − previous close|` (a gap down).
2. The first ATR is the **mean** of the first `period` true ranges.
3. Every later ATR is **Wilder's smoothing** of the previous ATR and the new true range: `ATR = (previous ATR × (period − 1) + true range) / period`.

The first bar has no previous close, so it has no true range: the first ATR comes at bar `period` (counting from 0).

## What it is for

- **Position sizing and stops.** Stops placed a multiple of ATR away from the price (for example 2 × ATR, the "chandelier" exit) adapt to how much the market moves.
- **Comparing volatility over time.** A rising ATR means wider bars and bigger gaps; a falling ATR a quieter market. ATR says nothing about direction.
- **Building block.** Keltner Channels, the Average Directional Index and SuperTrend are built on true range or ATR.

ATR is in price units, so values for different instruments (or the same one at very different prices) are not directly comparable.

## Usage

ATR needs three columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, symbols, ...):

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.atr(df, period=14)          # a DataFrame with one column, "atr"
pyta.atr(df)                     # period defaults to 14
```

The same works for a dict of columns and JSON (an array of records or an object of arrays):

```python
pyta.atr({"High": highs, "Low": lows, "Close": closes, "Volume": volumes})
# {"ATR": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.atr(df, columns=["high", "low", "adj close"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close**:

```python
import numpy as np

pyta.atr(np.column_stack([highs, lows, closes]))   # 2-D array (rows, 3) or (3, rows) -> 1-D array
pyta.atr((highs, lows, closes))                     # tuple of arrays -> tuple
pyta.atr([df["High"], df["Low"], df["Close"]])     # list of Series -> Series, matched by name
```

ATR is also in the volatility namespace; both names are the same function:

```python
pyta.volatility.atr(df)   # same as pyta.atr
from pyta.volatility import atr
```

Many datasets in one call:

```python
results = pyta.batch.atr([df1, df2, df3])              # list of results, in order
pyta.batch.volatility.atr({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `period` | `int` | `14` | Number of true ranges in the first average, and Wilder's smoothing period; at least `1` (TA-Lib's and Wilder's default is 14) |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low, and a close or adjusted close. `None` finds them by name. Names are standard column names or aliases, such as `High` or `adj close`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |

With no `columns=`, the close input takes the close column if there is one, and the adjusted close otherwise. A missing column raises `ValueError` naming the required and the available columns.

## Output

- Same length as the input, `float64`, never negative, in the input's price units.
- The first `period` values are `NaN` (warm-up); the first value is at row `period`.
- At least `period + 1` rows are required.
- Named `atr` in a DataFrame, dict, or JSON object (`ATR` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`; see [names and casing](../../API.md#11-multi-output-indicators)). A dict keeps the container type of its high column (list, array or Series); a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | ATR |
|---|---|
| Flat series (every high, low and close equal) | `0` |
| High equal to low and the close unchanged | true range `0` for that bar |
| High equal to low, close moving | the gaps only: true range `|close − previous close|` |
| `period = 1` | the true range itself, from row 1 |
| Movement stops | ATR decays towards `0` by a factor `(period − 1) / period` per bar, without reaching it |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `period + 1` rows | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: ATR needs several columns |

## Implementation notes

PyTA follows TA-Lib's `TA_ATR` (0.8.3): the same true range, warm-up (`period`), seed (the mean of the true ranges of rows 1 to `period`), smoothing and default period (14). TA-Lib's smoothing is written `(previous × (period − 1) + true range) / period`; PyTA computes the same recurrence as `previous × (period − 1) / period + true range / period` (the form RSI uses, shared through `pyta-core`), which can differ in the last bit and agrees with TA-Lib's own output to `1e-9` relative on the reference data. With `period = 1` both return the true range.

Wilder's 1978 definition is the same calculation. Some worked examples, StockCharts ChartSchool's among them, start one row earlier: they take the first bar's true range as `high − low` (it has no previous close) and average rows 0 to `period − 1`, so their first ATR is at row `period − 1` and their values differ slightly from TA-Lib's and PyTA's for the first few dozen bars, converging after that.

The Rust kernel (`pyta-volatility`) makes one pass for the true ranges and one for the smoothing, so the cost is proportional to the number of rows and independent of `period`. Reference values are TA-Lib 0.8.3's own output on 300 SPY sessions and on a synthetic edge-case series (flat stretches, high equal to low), stored in `tests/fixtures/atr_14_talib.csv` and `atr_14_edge_talib.csv`.

## See also

[CCI](../momentum/cci.md) · [RSI](../momentum/rsi.md) (the same Wilder smoothing) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
