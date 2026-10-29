# CCI: Commodity Channel Index

**Category:** Momentum · **Function:** `pyta.cci` · **Batch:** `pyta.batch.cci` · **Columns:** high, low, close

## What it is

The CCI measures how far the price has moved away from its recent average, in units of its usual deviation from that average. It was introduced by Donald Lambert in 1980 for commodities, and is used on any market.

1. For each bar, the **typical price** is `(high + low + close) / 3`.
2. Over the last `period` bars, take the **mean** of the typical price and its **mean deviation**: the average distance of each typical price from that mean.
3. `CCI = (typical price − mean) / (0.015 × mean deviation)`.

Lambert's constant 0.015 puts most values (roughly 70–80%) between −100 and +100.

## What it is for

- **Overbought and oversold.** Readings above +100 suggest the price is unusually high relative to its average, and below −100 unusually low. As with any oscillator, strong trends can stay beyond these levels for a long time.
- **Emerging trends.** A move from inside the ±100 band to above +100 (or below −100) is often read as the start of a new trend.
- **Divergence.** Price making a new high while CCI does not is often read as weakening momentum.

## Usage

CCI needs three columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, symbols, ...):

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.cci(df, period=20)          # a DataFrame with one column, "cci"
pyta.cci(df)                     # period defaults to 14
```

The same works for a dict of columns and JSON (an array of records or an object of arrays):

```python
pyta.cci({"High": highs, "Low": lows, "Close": closes, "Volume": volumes})
# {"cci": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.cci(df, columns=["high", "low", "adj close"])   # the adjusted close instead of the close
pyta.cci(df, columns=["adj close", "low", "high"])   # same result
```

Unnamed input takes its columns in the order **high, low, close**:

```python
import numpy as np

pyta.cci(np.column_stack([highs, lows, closes]), period=20)   # 2-D array (rows, 3) -> 1-D array
pyta.cci((highs, lows, closes), period=20)                     # tuple of arrays -> tuple
```

CCI is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.cci(df)   # same as pyta.cci
from pyta.momentum import cci
```

Many datasets in one call:

```python
results = pyta.batch.cci([df1, df2, df3], period=20)   # list of results, in order
pyta.batch.momentum.cci({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, 2-D array, tuple of arrays | required | High, low and close prices; other columns are ignored |
| `period` | `int` | `14` | Number of bars in each window, at least `1`. TA-Lib's default is 14; Lambert and StockCharts use 20 |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low, and a close or adjusted close. `None` finds them by name. Names are standard column names or aliases, such as `High` or `adj close`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |

With no `columns=`, the close input takes the close column if there is one, and the adjusted close otherwise. A missing column raises `ValueError` naming the required and the available columns.

## Output

- Same length as the input, `float64`. Unbounded, but most values lie between −100 and +100; it can never exceed `period / 0.03` in size.
- The first `period − 1` values are `NaN` (warm-up).
- At least `period` rows are required.
- Named `cci` in a DataFrame, dict, or JSON object (`CCI` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`; see [names and casing](../../API.md#11-multi-output-indicators)). A dict keeps the container type of its high column (list, array or Series); a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | CCI |
|---|---|
| Flat window (every typical price equal) | `0` |
| Latest typical price equal to the window's mean | `0` |
| `period = 1` | `0` throughout (each window is flat) |

"Equal" allows a relative difference of `1e-14` of the mean, as TA-Lib does, so rounding noise in a flat market reads as `0` rather than a huge value.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `period` rows | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: CCI needs several columns |

## Implementation notes

PyTA follows TA-Lib's `TA_CCI`: the same formula, warm-up (`period − 1`), default period (14) and zero rule. It differs from TA-Lib in one place: TA-Lib rejects `period < 2`, while PyTA accepts `1` and returns `0`. Lambert's original definition is the same calculation.

The Rust kernel (`pyta-momentum`) works in two passes. The first keeps each window's sum as a running total with exact error compensation, so it never drifts: a flat stretch right after a large price leaves the window still reads exactly `0`, which a plain running sum gets wrong. The second takes each window's mean deviation, which needs a pass over the window because the mean moves every row; the windows are independent there, so the CPU works on several at once. The cost is proportional to `rows × period`, at about a third of a nanosecond per row and period on the development machine. Results agree with summing every window afresh to within the rounding of the mean itself. Reference values are checked against StockCharts ChartSchool's 20-day example.

## See also

[RSI](rsi.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
