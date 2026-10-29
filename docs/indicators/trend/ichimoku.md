# Ichimoku Cloud

**Category:** Trend · **Function:** `pyta.ichimoku` · **Batch:** `pyta.batch.ichimoku` · **Columns:** high, low, close

## What it is

The Ichimoku Cloud (Ichimoku Kinko Hyo, "equilibrium chart at a glance") is a complete trend system in five lines, developed by the Japanese journalist Goichi Hosoda from the 1930s and published in 1969. Four of the lines are midpoints of a price range, `(highest high + lowest low) / 2`, over windows that **include the current bar**; the fifth is the close.

| Line | PyTA output | Calculation (defaults) |
|---|---|---|
| Tenkan-sen (conversion line) | `ichimoku_tenkan` | midpoint of the last `tenkan` bars (9) |
| Kijun-sen (base line) | `ichimoku_kijun` | midpoint of the last `kijun` bars (26) |
| Senkou span A (leading span A) | `ichimoku_senkou_a` | `(tenkan-sen + kijun-sen) / 2` |
| Senkou span B (leading span B) | `ichimoku_senkou_b` | midpoint of the last `senkou` bars (52) |
| Chikou span (lagging span) | `ichimoku_chikou` | the close |

Each midpoint is the middle line of [Donchian Channels](../volatility/donchian.md) over the same window.

**The cloud** (kumo) is the area between the two senkou spans. On a chart both spans are drawn `kijun` bars (26) **ahead** of the bar they were calculated on, so the cloud runs into the future, and the chikou span is drawn `kijun` bars **back**. PyTA does not shift anything: every line is on the bar it is calculated from (see [Plotting the cloud](#plotting-the-cloud)).

**The defaults 9, 26 and 52** come from the Japanese trading calendar of Hosoda's time, with six trading days a week: 9 is a week and a half, 26 a month and 52 two months. They are kept almost everywhere today, including on five-day markets; some traders scale them (for example 7, 22 and 44, or doubled windows on markets that trade every day).

## What it is for

- **Trend direction.** Price above the cloud is an uptrend, below it a downtrend, inside it no clear trend. A cloud with span A above span B (often drawn green) is bullish, span B above span A bearish.
- **Support and resistance.** The cloud's edges, and the kijun-sen, act as support in an uptrend and resistance in a downtrend; a thick cloud is stronger than a thin one.
- **Signals.** The tenkan-sen crossing above the kijun-sen (a "TK cross") is a buy signal, stronger above the cloud; crossing below is a sell signal. The two spans crossing (a "kumo twist") warns of a trend change.
- **Confirmation.** The chikou span, today's close drawn 26 bars back, confirms a trend when it is above (or below) the price of 26 bars ago.

## Usage

The Ichimoku Cloud needs three columns, so pass data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, ...):

```python
import pyta

data = {
    "high": [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0, 13.0],
    "low": [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0, 10.0],
    "close": [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0, 11.0],
}

result = pyta.ichimoku(data, tenkan=2, kijun=3, senkou=5)
# result["ichimoku_tenkan"]:   [nan, 10.5, 11.5, 11.5, 12.0, 13.0, 13.5, 12.0]
# result["ichimoku_kijun"]:    [nan, nan, 11.0, 11.5, 12.0, 12.5, 13.0, 12.5]
# result["ichimoku_senkou_a"]: [nan, nan, 11.25, 11.5, 12.0, 12.75, 13.25, 12.25]
# result["ichimoku_senkou_b"]: [nan, nan, nan, nan, 11.5, 12.5, 12.5, 12.5]
# result["ichimoku_chikou"]:   [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0, 11.0]
```

A DataFrame (or a dict, or JSON) gains one column per output:

```python
pyta.ichimoku(df)                                   # 9, 26, 52: five ichimoku_* columns
pyta.ichimoku(df, tenkan=7, kijun=22, senkou=44)    # scaled windows
pyta.ichimoku(yfinance_df).columns                  # ['Ichimoku_Tenkan', ..., 'Ichimoku_Senkou_A', ...]
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.ichimoku(df, columns=["adj_close", "low", "high"])
```

Unnamed input takes its columns in the order **high, low, close**, and returns a tuple of the five outputs:

```python
import numpy as np

tenkan, kijun, span_a, span_b, chikou = pyta.ichimoku(np.column_stack([highs, lows, closes]))
tenkan, kijun, span_a, span_b, chikou = pyta.ichimoku((highs, lows, closes))
```

The Ichimoku Cloud is also in the trend namespace; both names are the same function:

```python
pyta.trend.ichimoku(df)   # same as pyta.ichimoku
from pyta.trend import ichimoku
```

Many datasets in one call:

```python
results = pyta.batch.ichimoku([df1, df2, df3])              # list of results, in order
pyta.batch.trend.ichimoku({"SPY": spy, "QQQ": qqq})         # dict of results, same keys
```

### Plotting the cloud

PyTA returns every line on the bar it is calculated from, so the output is as long as the input and nothing is lost. To draw the classic chart, shift the spans `kijun` bars forward and the chikou span `kijun` bars back. With pandas:

```python
kijun = 26
cloud = pyta.ichimoku(df, kijun=kijun)

# Extend the index by `kijun` future bars, so the last 26 span values stay visible.
future = pd.bdate_range(df.index[-1], periods=kijun + 1)[1:]
chart = cloud.reindex(df.index.append(future))

chart["ichimoku_senkou_a"] = chart["ichimoku_senkou_a"].shift(kijun)   # 26 bars ahead
chart["ichimoku_senkou_b"] = chart["ichimoku_senkou_b"].shift(kijun)
chart["ichimoku_chikou"] = chart["ichimoku_chikou"].shift(-kijun)      # 26 bars back
```

Without the extra index, `shift(kijun)` drops the last 26 values of each span, which are the part of the cloud that lies ahead of today. With NumPy, pad instead: `np.concatenate([np.full(kijun, np.nan), span_a])`.

The unshifted lines are also what a strategy needs: on bar `t`, the cloud a chart shows above that bar is `senkou_a[t - kijun]` and `senkou_b[t - kijun]`.

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `tenkan` | `int` | `9` | Bars in the tenkan-sen's (conversion line's) window; at least `1` |
| `kijun` | `int` | `26` | Bars in the kijun-sen's (base line's) window; at least `1`. Also the usual plotting shift |
| `senkou` | `int` | `52` | Bars in senkou span B's window; at least `1` |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low and a close (or adjusted close). `None` finds them by name. Names are standard column names or aliases, such as `High`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

The three windows may be in any order (`tenkan` longer than `kijun` is allowed). `column=` (singular) is for single-column indicators and raises `ValueError` here.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, else `adj_close` | 3rd |

A missing column raises `ValueError` naming the required and the available columns.

## Output

- Five outputs in the order `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`, `ichimoku_chikou`, each the same length as the input, `float64`, **unshifted**.
- Each output keeps its own warm-up (`NaN`): the first `tenkan - 1` values of the tenkan-sen, `kijun - 1` of the kijun-sen, `max(tenkan, kijun) - 1` of senkou span A and `senkou - 1` of senkou span B. The chikou span has none. With the defaults: 8, 25, 25 and 51 rows.
- At least `max(tenkan, kijun, senkou)` rows are required, so every output has a value.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the five. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `ICHIMOKU_TENKAN` for `HIGH, LOW, CLOSE`, `Ichimoku_Tenkan` and `Ichimoku_Senkou_A` for `High, Low, Close` (no part of the name is an abbreviation).

## Edge cases

| Situation | Ichimoku Cloud |
|---|---|
| A window of 1 | that line is `(high + low) / 2` of each bar |
| A flat window (every high and low equal) | the line is that level |
| `tenkan` longer than `kijun` | allowed; senkou span A starts with the longer of the two |
| `adj_close` and no `close` | the chikou span is the adjusted close |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in every output (the chikou span included) |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `max(tenkan, kijun, senkou)` rows | `ValueError` |
| `tenkan`, `kijun` or `senkou` below 1 | `ValueError` naming it |
| A list, 1-D array or Series (one series) | `TypeError`: the Ichimoku Cloud needs three columns |

## Implementation notes

TA-Lib has no Ichimoku function, so PyTA follows Hosoda's definition as charting platforms (StockCharts, TradingView) calculate it, with two choices of its own:

- **Unshifted output.** Every line is on the bar it is calculated from, and the output is as long as the input. Shifting within the input's length would drop the last `kijun` values of both spans, the part of the cloud traders look at; shifting beyond it would break "output length equals input length". [Plotting the cloud](#plotting-the-cloud) shows the shift.
- **Each output keeps its own warm-up**, so the tenkan-sen has values long before senkou span B.

Differences from other libraries:

- **pandas-ta** returns the spans already shifted forward by `kijun` (and the chikou span shifted back), so its values sit on different rows than PyTA's; shift PyTA's as above to compare.
- Some implementations exclude the current bar from the windows; PyTA includes it, as Hosoda and the charting platforms do.

There is no reference library for the unshifted lines, so the tests check them two ways: on 300 real SPY sessions the tenkan-sen, kijun-sen and senkou span B equal [Donchian Channels](../volatility/donchian.md)' middle line over 9, 26 and 52 bars bit for bit (Donchian's upper and lower channels match TA-Lib's `MAX` and `MIN`), senkou span A equals their average and the chikou span equals the close; and a hand-computed table, `tests/fixtures/ichimoku_hand.csv` (windows 2, 3 and 5), matches exactly.

The Rust kernel (`pyta-trend`) builds each midpoint from the shared rolling-extreme kernels of `pyta-core` (the van Herk/Gil-Werman algorithm), O(n) whatever the windows, writing the lowest low into the highest high's buffer so each midpoint needs one allocation.

## See also

[Donchian Channels](../volatility/donchian.md) · [Aroon](aroon.md) · [ADX](adx.md) · [MACD](macd.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
