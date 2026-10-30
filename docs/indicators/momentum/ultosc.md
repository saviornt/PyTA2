# Ultimate Oscillator

**Category:** Momentum · **Function:** `pyta.ultosc` · **Batch:** `pyta.batch.ultosc` · **Columns:** high, low, close

## What it is

The Ultimate Oscillator measures buying pressure against the true range over three time frames at once, so that one short burst does not dominate. It was introduced by Larry Williams in 1976 (published in 1985).

1. Each bar's **buying pressure** is `BP = close − true low`, and its **true range** `TR = true high − true low`, where the true low is the lower of the low and the previous close, and the true high the higher of the high and the previous close.
2. Over the last `short`, `medium` and `long` bars (7, 14 and 28 by default), each **average** is `sum(BP) / sum(TR)`.
3. `ULTOSC = 100 × (4 × short average + 2 × medium average + long average) / 7`.

The shortest window counts four times, the middle one twice and the longest once. The result runs from **0** (every close at its true low) to **100** (every close at its true high).

## What it is for

- **Divergence entries.** Williams' buy signal: a bullish divergence (a lower price low with a higher oscillator low) whose oscillator low is below 30, then the oscillator rising above the divergence's high. The sell signal mirrors it above 70.
- **Overbought and oversold.** Readings above 70 are usually read as overbought and below 30 as oversold.
- **Fewer false signals.** Mixing three time frames damps the whipsaws a single-period oscillator gives in fast moves.

## Usage

The Ultimate Oscillator needs three columns, so pass OHLCV data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest:

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")            # date, open, high, low, close, volume
pyta.ultosc(df)                           # windows 7, 14, 28: a DataFrame with one column, "ultosc"
pyta.ultosc(df, short=5, medium=10, long=20)
```

The windows must be in increasing order. TA-Lib sorts them silently; PyTA raises, so a typo cannot change the weighting unnoticed:

```python
pyta.ultosc(df, 14, 7, 28)
# ValueError: short must be less than medium, got short=14 and medium=7
```

The same works for a dict of columns, JSON and CSV text:

```python
pyta.ultosc({"High": highs, "Low": lows, "Close": closes})
# {"ULTOSC": [...]}
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.ultosc(df, columns=["high", "low", "adj close"])   # the adjusted close instead of the close
```

Unnamed input takes its columns in the order **high, low, close**:

```python
import numpy as np

pyta.ultosc(np.column_stack([highs, lows, closes]))   # 2-D array (rows, 3) or (3, rows) -> 1-D array
pyta.ultosc((highs, lows, closes))                    # tuple of arrays -> tuple
```

The Ultimate Oscillator is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.ultosc(df)   # same as pyta.ultosc
```

Many datasets in one call:

```python
results = pyta.batch.ultosc([df1, df2, df3])                  # list of results, in order
pyta.batch.momentum.ultosc({"SPY": spy, "QQQ": qqq}, 5, 10, 20)  # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `short` | `int` | `7` | Bars in the shortest window (weight 4), at least `1` |
| `medium` | `int` | `14` | Bars in the middle window (weight 2), greater than `short` |
| `long` | `int` | `28` | Bars in the longest window (weight 1), greater than `medium`. The defaults are Williams' and TA-Lib's; TA-Lib caps each at 100,000, PyTA does not |
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

- Same length as the input, `float64`, between 0 and 100.
- The first `long` values are `NaN` (warm-up: the first bar has no previous close).
- At least `long + 1` rows are required.
- Named `ultosc` in a DataFrame, dict, JSON object or CSV (`ULTOSC` when the columns used are all upper case or all title case, as yfinance's `High`, `Low`, `Close`: it is an abbreviation). A dict keeps the container type of its high column; a 2-D array gives a 1-D array, and a tuple a tuple.

## Edge cases

| Situation | Ultimate Oscillator |
|---|---|
| A window whose true ranges sum to 0 (flat bars at the previous close) | That window's term is dropped; the divisor stays 7, as in TA-Lib |
| A fully flat stretch (all three windows flat) | `0` |
| A gap (the low above the previous close, or the high below it) | The previous close takes its place in the true low or the true high |

The sums are running totals (add the newest bar, subtract the one leaving), as TA-Lib's are; once a window's worth of bars in a row added nothing, that window's totals are reset to exactly 0, so a flat window is recognised exactly rather than as a ratio of rounding residue. Because the dropped term keeps the divisor at 7, a stretch where only the short window is flat reads lower than the bars around it; this is TA-Lib 0.8.3's convention.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Fewer than `long + 1` rows | `ValueError` (`at least 29 values are required, got 20`) |
| A window below 1 | `ValueError` naming it |
| Windows not in increasing order | `ValueError` naming the two (`short must be less than medium, got short=14 and medium=7`) |
| A list, 1-D array or Series (one series) | `TypeError`: the Ultimate Oscillator needs several columns |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_ULTOSC`: the true low and true range from the previous close, the running sums with their add-then-subtract order, the resets after a window without range, the dropped term for a zero range with the divisor kept at 7, the weighting written `100 × ((4 × a + 2 × b + c) / 7)`, the warm-up (`long`) and the defaults (7, 14, 28). Every value of the TA-Lib fixtures matches bit for bit. The one deliberate difference: TA-Lib sorts the three periods before using them, PyTA requires `short < medium < long` and raises otherwise (the Rust kernel checks the same, with the same message, for direct callers). Williams' original definition is the same calculation.

The Rust kernel (`pyta-momentum`) uses the shared true range from `pyta-core` and, like TA-Lib, keeps the last `long` bars' terms in a ring buffer to subtract the bars leaving each window; its cost does not depend on the windows.

## See also

[Williams %R](willr.md) · [Stochastic Oscillator](stoch.md) · [ATR](../volatility/atr.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators)
