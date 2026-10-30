# Volume-Weighted Average Price (VWAP)

**Category:** Volume · **Function:** `pyta.vwap` · **Batch:** `pyta.batch.vwap` · **Columns:** high, low, close, volume

## What it is

VWAP is the average price paid, weighting each bar's price by the volume traded in it. It is the benchmark that institutional traders measure their fills against: buying below VWAP is buying cheaper than the average trader did.

1. Each bar's **typical price** is `(high + low + close) / 3`.
2. Multiply it by the bar's volume.
3. `VWAP = sum(typical price × volume) / sum(volume)`, over **every bar so far** (cumulative from the first row).

Rows before the first bar with volume have no average, so they are `NaN`.

## What it is for

- **Execution benchmark.** Fills below VWAP (when buying) or above it (when selling) beat the day's average trader.
- **Intraday trend.** Price above VWAP is read as buyers in control, below it as sellers in control.
- **Support and resistance.** Intraday traders watch for price to bounce off or break through VWAP.

## Sessions: VWAP restarts each day on charts

Charting platforms (StockCharts, TradingView) **reset VWAP at the start of every session**, so each day's line starts fresh at that day's first bar. `pyta.vwap` has no notion of dates: it is cumulative from the first row you pass. To get the per-session line, pass one session at a time, for example with a pandas `groupby` by date:

```python
import pandas as pd
import pyta

bars = pd.read_csv("minute_bars.csv", index_col="timestamp", parse_dates=True)

# One VWAP per day, each cumulative from that day's first bar.
vwap = bars.groupby(bars.index.date, group_keys=False).apply(pyta.vwap)   # column "vwap", original index
```

Or run every session in one call with the batch function:

```python
sessions = {day: frame for day, frame in bars.groupby(bars.index.date)}
results = pyta.batch.vwap(sessions)   # dict: day -> that session's VWAP
```

Anchoring VWAP at a chosen bar (an "anchored VWAP") is the same: slice the data from the anchor on. A built-in session or anchor option needs a date column and is in the parking lot.

## Usage

VWAP needs four columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low, close and volume columns by name and ignores the rest:

```python
df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.vwap(df)                    # a DataFrame with one column, "vwap"
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.vwap({"High": highs, "Low": lows, "Close": closes, "Volume": volumes})
# {"VWAP": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.vwap(df, columns=["high", "low", "adj close", "volume"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close, volume**:

```python
import numpy as np

pyta.vwap(np.column_stack([highs, lows, closes, volumes]))   # 2-D array (rows, 4) or (4, rows) -> 1-D array
pyta.vwap((highs, lows, closes, volumes))                    # tuple of arrays -> tuple
```

VWAP is also in the volume namespace; both names are the same function:

```python
pyta.volume.vwap(df)   # same as pyta.vwap
```

Many datasets in one call:

```python
results = pyta.batch.vwap([df1, df2, df3])          # list of results, in order
pyta.batch.volume.vwap({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low, close and volume; other columns are ignored |
| `columns` | list of `str` or `None` | `None` | The four columns to use, in any order: a high, a low, a close or adjusted close, and a volume. `None` finds them by name. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

VWAP has no parameters. `column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, or else `adj_close` | 3rd |
| volume | `volume` | 4th |

## Output

- Same length as the input, `float64`, between the lowest low and the highest high seen so far.
- `NaN` until the first row with volume; a value on every row after it. One row is enough.
- Named `vwap` in a DataFrame, dict, JSON object or CSV (`VWAP` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`, `Volume`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | VWAP |
|---|---|
| Leading rows with zero volume | `NaN` until the first row with volume |
| No volume at all | `NaN` throughout |
| Zero volume on a later row | Unchanged from the row before |
| A one-price bar (high equal to low) | Its price is the typical price, as usual |
| Constant prices | That price |

Both sums are compensated (Neumaier), so VWAP over millions of rows is as accurate as a fresh sum, even when one huge volume is followed by many small ones. Price × volume is a product of two inputs: if it would overflow (prices and volumes both near the `1e290` input limit), PyTA scales the volume by a power of two, which changes no ratio, so the result stays finite.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output; the sums then start at the first complete row |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Negative volume on any row | `ValueError` naming the column and the row (zero is valid) |
| A list, 1-D array or Series (one series) | `TypeError`: VWAP needs several columns |

## Implementation notes

TA-Lib has no VWAP. PyTA uses the typical price, as StockCharts and TradingView do (some platforms use the close, or the average of open, high, low and close), and accumulates from the first row with no session reset (see [Sessions](#sessions-vwap-restarts-each-day-on-charts)). The values are checked against a hand-computed table (`tests/fixtures/vwap_hand.csv`, with leading rows without volume and a one-price bar) and against a plain cumulative sum on real SPY data to `1e-12`.

The Rust kernel (`pyta-volume`) uses the shared typical price and compensated sum from `pyta-core`, in one pass; its overflow guard reruns the pass with scaled volumes only when a sum has overflowed, as MFI's does.

## See also

[Chaikin Money Flow](cmf.md) · [Accumulation/Distribution](ad.md) · [OBV](obv.md) · [Volume indicators](README.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
