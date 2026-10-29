# Williams %R

**Category:** Momentum · **Function:** `pyta.willr` · **Batch:** `pyta.batch.willr` · **Columns:** high, low, close

## What it is

Williams %R shows where the latest close lies within the high-low range of the last `period` bars. It was introduced by Larry Williams in 1973.

1. Over the last `period` bars, the current bar included, take the **highest high** and the **lowest low**.
2. `%R = (highest high − close) / (highest high − lowest low) × −100`.

The result runs from **0** (the close is at the highest high) to **−100** (the close is at the lowest low). It is the fast Stochastic %K turned upside down and shifted: `%R = %K − 100` over the same window.

## What it is for

- **Overbought and oversold.** Readings above −20 are usually read as overbought and below −80 as oversold. In a strong trend %R can stay near either end for a long time.
- **Momentum failures.** %R failing to return above −20 on a new price rally (or below −80 on a new low) is often read as fading momentum.
- **Confirmation.** A move from below −80 to above −50 is sometimes used to confirm a turn.

## Usage

Williams %R needs three columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.willr(df, period=14)        # a DataFrame with one column, "willr"
pyta.willr(df)                   # period defaults to 14
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.willr({"High": highs, "Low": lows, "Close": closes})
# {"WILLR": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.willr(df, columns=["high", "low", "adj close"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close**:

```python
import numpy as np

pyta.willr(np.column_stack([highs, lows, closes]))   # 2-D array (rows, 3) or (3, rows) -> 1-D array
pyta.willr((highs, lows, closes))                    # tuple of arrays -> tuple
```

Williams %R is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.willr(df)   # same as pyta.willr
```

Many datasets in one call:

```python
results = pyta.batch.willr([df1, df2, df3], period=14)   # list of results, in order
pyta.batch.momentum.willr({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `period` | `int` | `14` | Bars in the highest-high and lowest-low window, the current bar included, at least `2` (TA-Lib's minimum and default; Williams also used 10) |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low, and a close or adjusted close. `None` finds them by name. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |

## Output

- Same length as the input, `float64`, between −100 and 0.
- The first `period − 1` values are `NaN` (warm-up).
- At least `period` rows are required.
- Named `willr` in a DataFrame, dict, JSON object or CSV (`WILLR` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | %R |
|---|---|
| Close at the highest high | `0` (written `-0.0`, as TA-Lib does) |
| Close at the lowest low | `−100` |
| Flat window (highest high equal to lowest low) | `0` |
| Close above the window's high or below its low | Clamped to `0` or `−100` |

"Flat" allows a range of `1e-14` of `|highest| + |lowest|`, as TA-Lib 0.8.3 does, so rounding noise reads as a flat window rather than a random value. A close outside its own bar's high and low is not checked (TA-Lib does not either); the clamp keeps the result in range.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Fewer than `period` rows | `ValueError` (`period (14) exceeds the series length (10)`) |
| `period` below 2 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: Williams %R needs several columns |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_WILLR`: the same formula and order of operations (divide by the range, then multiply by −100), the scaled flat-window test, the clamp, the warm-up (`period − 1`), default (14) and minimum period (2). Every value of the TA-Lib fixtures matches bit for bit. TA-Lib caps `period` at 100,000; PyTA does not. Williams' original definition is the same calculation; some charting platforms plot it from 0 to 100 without the minus sign.

The Rust kernel (`pyta-momentum`) takes the rolling highest high and lowest low from the shared van Herk/Gil-Werman extremes in `pyta-core`, so its cost does not depend on `period`.

## See also

[Stochastic Oscillator](stoch.md) · [CCI](cci.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
