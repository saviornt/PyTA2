# Donchian Channels

**Category:** Volatility · **Function:** `pyta.donchian` · **Batch:** `pyta.batch.donchian` · **Columns:** high, low

## What it is

Donchian Channels draw the highest high and the lowest low of the last `period` bars around the price. Richard Donchian, a pioneer of trend-following funds, used them from the 1950s on; the rule "buy a new 4-week high, sell a new 4-week low" is his, and the Turtle traders of the 1980s built their system on 20- and 55-bar channels.

For each bar, over the last `period` bars **including the current one**:

1. The **upper channel** is the highest high.
2. The **lower channel** is the lowest low.
3. The **middle channel** is their midpoint, `(upper + lower) / 2`.

The channels are in price units. A 20-bar window, about four weeks of daily bars, is the common setting and PyTA's default.

## What it is for

- **Breakouts.** A close above the previous bar's upper channel is a new `period`-bar high, Donchian's buy signal; below the previous lower channel, a sell signal. Compare with the *previous* bar's channel (see [the current-row choice](#the-current-row-choice)).
- **Trailing stops.** The lower channel of a shorter window (10 bars for a 20-bar entry, in the Turtle rules) trails a long position; the upper one a short.
- **Volatility and range.** The width `upper - lower` is the price range of the window: wide channels mean large swings, narrow ones a quiet market. The middle channel is a simple reference level for trend direction.

## Usage

Donchian Channels need two columns, so pass data in a container that has column names. PyTA finds the high and low columns by name and ignores the rest (dates, open, close, volume, ...):

```python
import pyta

data = {
    "high": [11.0, 12.0, 11.0, 14.0, 13.0, 10.0, 12.0],
    "low": [9.0, 9.0, 10.0, 12.0, 11.0, 8.0, 10.0],
}

result = pyta.donchian(data, period=3)
# result["donchian_upper"]:  [nan, nan, 12.0, 14.0, 14.0, 14.0, 13.0]
# result["donchian_middle"]: [nan, nan, 10.5, 11.5, 12.0, 11.0, 10.5]
# result["donchian_lower"]:  [nan, nan, 9.0, 9.0, 10.0, 8.0, 8.0]
```

A DataFrame (or a dict, or JSON) gains one column per channel:

```python
pyta.donchian(df)                        # period 20: columns donchian_upper, donchian_middle, donchian_lower
pyta.donchian(df, period=55)
pyta.donchian(yfinance_df).columns       # ['Donchian_Upper', 'Donchian_Middle', 'Donchian_Lower']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.donchian(df, columns=["low", "high"])
```

Unnamed input takes its columns in the order **high, low**, and returns a tuple of the three channels:

```python
import numpy as np

upper, middle, lower = pyta.donchian(np.column_stack([highs, lows]))   # (rows, 2) or (2, rows)
upper, middle, lower = pyta.donchian((highs, lows))                    # tuple of arrays
```

Donchian Channels are also in the volatility namespace; both names are the same function:

```python
pyta.volatility.donchian(df)   # same as pyta.donchian
from pyta.volatility import donchian
```

Many datasets in one call:

```python
results = pyta.batch.donchian([df1, df2, df3])              # list of results, in order
pyta.batch.volatility.donchian({"SPY": spy, "QQQ": qqq})    # dict of results, same keys
```

### Breakout signals (StockCharts' Price Channels)

The channels include the current bar, so the current high can never be above the upper channel. For a breakout test, compare with the previous bar's channels by shifting them one row:

```python
channels = pyta.donchian(df, period=20)
breakout_up = df["close"] > channels["donchian_upper"].shift(1)
breakout_down = df["close"] < channels["donchian_lower"].shift(1)
```

`channels.shift(1)` is StockCharts' "Price Channels" exactly.

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High and low prices; other columns are ignored |
| `period` | `int` | `20` | Number of bars in each window, the current bar included; at least `1` |
| `columns` | list of `str` or `None` | `None` | The two columns to use, in any order: a high and a low. `None` finds them by name. Names are standard column names or aliases, such as `High`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |

A missing column raises `ValueError` naming the required and the available columns.

## Output

- Three outputs in the order `donchian_upper`, `donchian_middle`, `donchian_lower`, each the same length as the input, `float64`, in the input's price units. Upper is never below middle, and middle never below lower.
- All three share one warm-up: the first `period - 1` values are `NaN`.
- At least `period` rows are required.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the three. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `DONCHIAN_UPPER` for `HIGH, LOW`, `Donchian_Upper` for `High, Low` (no part of the name is an abbreviation).

## Edge cases

| Situation | Donchian Channels |
|---|---|
| `period = 1` | upper is the high, lower the low, middle their midpoint |
| High equal to low throughout a window (a flat stretch) | three equal channels, the repeated value |
| `period` equal to the input length | one value per channel, from the whole series |
| A new high on the current bar | it is the upper channel on that same bar |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in either column | Rows up to the last leading `NaN` of either column are skipped, then re-padded with `NaN` in every output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `period` rows | `ValueError` |
| `period` below 1 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: Donchian Channels need two columns |

## Implementation notes

### The current-row choice

Donchian Channels are not a TA-Lib function. PyTA defines them as TA-Lib's `MAX(high, period)` and `MIN(low, period)`, whose windows include the current bar, with the middle `(upper + lower) / 2`; the upper and lower channels match TA-Lib 0.8.3's `MAX` and `MIN` bit for bit on 300 real SPY sessions and on an edge-case series (flat stretches, high equal to low), and the middle to `1e-9` (in practice exactly). This is also how most charting platforms draw the indicator.

StockCharts ChartSchool's "Price Channels" use the `period` bars **before** the current one, so a breakout shows as the price crossing the channel. Their values are PyTA's shifted by one row: the same channel, one bar later. Shift by one for breakout signals (see [Usage](#breakout-signals-stockcharts-price-channels)).

### Calculation

The Rust kernel (`pyta-volatility`) uses the shared rolling-extreme kernels of `pyta-core` (the van Herk/Gil-Werman algorithm), which take about three comparisons per row whatever the period and the data, so the cost is proportional to the number of rows and independent of `period`. Upper and lower are input values copied as they are, never computed. Reference values are stored in `tests/fixtures/donchian_20_talib.csv` and `donchian_20_edge_talib.csv`.

## See also

[BBANDS](bbands.md) · [ATR](atr.md) · [Keltner Channels](keltner.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
