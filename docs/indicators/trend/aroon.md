# Aroon

**Category:** Trend · **Function:** `pyta.aroon` · **Batch:** `pyta.batch.aroon` · **Columns:** high, low

## What it is

Aroon measures how long ago the price made its highest high and its lowest low. Tushar Chande introduced it in 1995 (the name is Sanskrit for "dawn's early light"): a market in an uptrend keeps making new highs, so the last high is recent; a market in a downtrend keeps making new lows.

For each bar, over a window of `period + 1` bars (**the current bar and the `period` bars before it**):

1. **Aroon Up** is `100 × (period − bars since the highest high) / period`: 100 when the highest high is on the current bar, 0 when it is the oldest bar in the window.
2. **Aroon Down** is the same with the lowest low.
3. **Aroon Oscillator** is `Aroon Up − Aroon Down`, from −100 to 100.

When two bars share the highest high (or lowest low), the more recent one counts. Up and down move in steps of `100 / period`. The default period is 14, TA-Lib's; Chande used 25.

## What it is for

- **Trend strength and direction.** Aroon Up above 70 with Aroon Down below 30 is the classic sign of an uptrend; the reverse a downtrend. Both low together means no new highs or lows: a consolidation.
- **Trend changes.** Aroon Up crossing above Aroon Down (the oscillator crossing above 0) is an early sign of a new uptrend, and the reverse of a new downtrend.
- **New extremes.** A value of 100 means the current bar set a new `period`-bar high (Up) or low (Down).

## Usage

Aroon needs two columns, so pass data in a container that has column names. PyTA finds the high and low columns by name and ignores the rest (dates, open, close, volume, ...):

```python
import pyta

data = {
    "high": [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0],
    "low": [7.0, 9.0, 9.5, 8.0, 10.0, 9.0, 11.0],
}

result = pyta.aroon(data, period=2)
# result["aroon_up"]:   [nan, nan, 50.0, 100.0, 50.0, 100.0, 50.0]
# result["aroon_down"]: [nan, nan, 0.0, 100.0, 50.0, 0.0, 50.0]
# result["aroon_osc"]:  [nan, nan, 50.0, 0.0, 0.0, 100.0, 0.0]
```

A DataFrame (or a dict, or JSON) gains one column per output:

```python
pyta.aroon(df)                       # period 14: columns aroon_up, aroon_down, aroon_osc
pyta.aroon(df, period=25)            # Chande's original setting
pyta.aroon(yfinance_df).columns      # ['Aroon_Up', 'Aroon_Down', 'Aroon_Osc']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.aroon(df, columns=["low", "high"])
```

Unnamed input takes its columns in the order **high, low**, and returns a tuple of the three outputs:

```python
import numpy as np

up, down, osc = pyta.aroon(np.column_stack([highs, lows]))   # (rows, 2) or (2, rows)
up, down, osc = pyta.aroon((highs, lows))                    # tuple of arrays
```

Aroon is also in the trend namespace; both names are the same function:

```python
pyta.trend.aroon(df)   # same as pyta.aroon
from pyta.trend import aroon
```

Many datasets in one call:

```python
results = pyta.batch.aroon([df1, df2, df3])              # list of results, in order
pyta.batch.trend.aroon({"SPY": spy, "QQQ": qqq})         # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High and low prices; other columns are ignored |
| `period` | `int` | `14` | Number of bars looked back from the current bar (a window of `period + 1` bars); at least `2` |
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

- Three outputs in the order `aroon_up`, `aroon_down`, `aroon_osc`, each the same length as the input, `float64`. Up and down lie from 0 to 100, the oscillator from −100 to 100.
- All three share one warm-up: the first `period` values are `NaN`.
- At least `period + 1` rows are required.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the three. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `AROON_UP` for `HIGH, LOW`, `Aroon_Up` for `High, Low` (no part of the name is an abbreviation).

## Edge cases

| Situation | Aroon |
|---|---|
| A flat window (every high and every low equal) | the current bar is both the highest high and the lowest low: up 100, down 100, oscillator 0 |
| Two bars share the highest high or the lowest low | the more recent bar counts |
| A steady rise | up 100, down 0, oscillator 100 |
| A steady fall | up 0, down 100, oscillator −100 |
| `period` such as 11, 22 or 39 | `100 / period × period` rounds to `100.00000000000001`, which TA-Lib returns; PyTA clamps up and down to `[0, 100]` and the oscillator to `[-100, 100]`, so a new extreme reads exactly 100. For a few periods (97, 161, ...) it rounds one unit in the last place below 100, which is kept (within `1e-9` of 100) |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in either column | Rows up to the last leading `NaN` of either column are skipped, then re-padded with `NaN` in every output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `period + 1` rows | `ValueError` |
| `period` below 2 | `ValueError` |
| A list, 1-D array or Series (one series) | `TypeError`: Aroon needs two columns |

## Implementation notes

PyTA follows TA-Lib's `AROON` and `AROONOSC` (Chande's definition), and matches TA-Lib 0.8.3 bit for bit (the clamp does not bind at period 14) on 300 real SPY sessions and on an edge-case series with flat stretches (where TA-Lib also gives 100, 100 and 0), stored in `tests/fixtures/aroon_14_talib.csv` and `aroon_14_edge_talib.csv`.

- **The window has `period + 1` bars.** "Bars since the highest high" counts from 0 (today) to `period`, so the window spans the current bar and the `period` before it, as in TA-Lib and Chande's definition. A window of only `period` bars would never reach 0.
- **Ties go to the newest bar**, as TA-Lib's `>=` and `<=` comparisons do.
- **Output order differs from TA-Lib's.** TA-Lib's `AROON` returns `(aroondown, aroonup)`; PyTA returns `aroon_up`, `aroon_down`, `aroon_osc`, in reading order, and computes the oscillator in the same call (TA-Lib's separate `AROONOSC`).
- **The oscillator** is written as TA-Lib writes it, `100 / period × (bar of the highest high − bar of the lowest low)`, which equals `aroon_up − aroon_down`.
- **Clamped to the range**, as RSI is: `aroon_up` and `aroon_down` to `[0, 100]`, `aroon_osc` to `[-100, 100]`. Where TA-Lib returns `100.00000000000001` (periods 11, 22, 39, ...), PyTA returns 100.
- **Period.** TA-Lib's default 14 is kept (Chande used 25), with TA-Lib's minimum of 2; TA-Lib caps `period` at 100,000, PyTA does not.

The Rust kernel (`pyta-trend`) uses the shared rolling-extreme kernels of `pyta-core` (the van Herk/Gil-Werman algorithm, which reports the row of each extreme, ties to the newest), about three comparisons per row whatever the period and the data. TA-Lib rescans the window only when its extreme leaves it, which is fast on rising highs but takes `period` steps per bar on a steadily falling high.

## See also

[ADX](adx.md) · [Parabolic SAR](sar.md) · [Donchian Channels](../volatility/donchian.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
