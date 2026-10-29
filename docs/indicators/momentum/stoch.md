# Stochastic Oscillator

**Category:** Momentum · **Function:** `pyta.stoch` · **Batch:** `pyta.batch.stoch` · **Columns:** high, low, close

## What it is

The Stochastic Oscillator shows where the close sits within the recent trading range, on a 0 to 100 scale. George Lane developed it in the 1950s; his idea was that in an uptrend prices tend to close near the top of their range, and that momentum turns before price does. PyTA returns the two lines charts draw:

1. **Raw %K.** `100 * (close - lowest low) / (highest high - lowest low)`, the extremes taken over the last `k` rows, the current row included. 100 means the close is at the top of the range, 0 at the bottom.
2. **%K (`stoch_k`).** The simple moving average of raw %K over `k_smooth` rows.
3. **%D (`stoch_d`).** The simple moving average of %K over `d` rows: the signal line.

Three variants share these formulas and differ only in the smoothing:

| Variant | `k_smooth` | %K is | %D is |
|---|---|---|---|
| Fast stochastic | `1` | raw %K | an SMA of raw %K |
| Slow stochastic (Lane's usual one) | `3` | an SMA of raw %K over 3 | an SMA of that over 3 |
| Full stochastic | any | an SMA of raw %K over `k_smooth` | an SMA of %K over `d` |

`pyta.stoch` is the full stochastic, so it gives all three. The defaults, `k=14, k_smooth=3, d=3`, are the slow stochastic that StockCharts, TradingView and most charting platforms show.

**TA-Lib users:** TA-Lib's `STOCH` defaults to `fastk_period=5` (with 3 and 3). Pass `k=5` to get TA-Lib's default numbers: `pyta.stoch(df, k=5)` equals `talib.STOCH(high, low, close)` wherever both have values.

## What it is for

- **Overbought and oversold.** Readings above 80 mean the close is near the top of its recent range; below 20, near the bottom. In a strong trend the oscillator can stay there for a long time, so these levels are context, not signals on their own.
- **Crossovers.** %K crossing above %D is read as bullish, below as bearish; Lane preferred crossings that happen in the extreme zones.
- **Divergence.** A new price high without a new %D high (or a new low without a new %D low) suggests the move is losing momentum; Lane considered this the most important signal.

## Usage

The Stochastic needs three columns, so pass data in a container that has column names. PyTA finds the high, low and close columns by name and ignores the rest (dates, open, volume, ...):

```python
import pyta

data = {
    "high": [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0],
    "low": [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0],
    "close": [10.0, 11.0, 12.0, 11.5, 13.0, 14.0, 13.0],
}

result = pyta.stoch(data, k=3, k_smooth=2, d=2)
# result["stoch_k"]: [nan, nan, nan, 62.5, 62.5, 77.5, 65.0]
# result["stoch_d"]: [nan, nan, nan, nan, 62.5, 70.0, 71.25]
```

A DataFrame (or a dict, or JSON) gains one column per line:

```python
pyta.stoch(df)                        # 14/3/3: stoch_k, stoch_d
pyta.stoch(df, k=5)                   # TA-Lib's defaults (5/3/3)
pyta.stoch(df, k=14, k_smooth=1)      # fast stochastic
pyta.stoch(yfinance_df).columns       # ['Stoch_K', 'Stoch_D']
```

To choose the columns yourself, pass `columns=[...]` in any order; each name goes to the input for its role:

```python
pyta.stoch(df, columns=["close", "low", "high"])
pyta.stoch(df, columns=["high", "low", "adj_close"])   # the adjusted close as the close
```

Unnamed input takes its columns in the order **high, low, close**, and returns a tuple of the two lines:

```python
import numpy as np

stoch_k, stoch_d = pyta.stoch(np.column_stack([highs, lows, closes]))   # (rows, 3) or (3, rows)
stoch_k, stoch_d = pyta.stoch((highs, lows, closes))                    # tuple of arrays
```

The Stochastic is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.stoch(df)   # same as pyta.stoch
from pyta.momentum import stoch
```

Many datasets in one call:

```python
results = pyta.batch.stoch([df1, df2, df3])              # list of results, in order
pyta.batch.momentum.stoch({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | DataFrame, dict, JSON, CSV, 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series | required | High, low and close prices; other columns are ignored |
| `k` | `int` | `14` | Rows in the highest-high and lowest-low window (TA-Lib's `fastk_period`, default 5 there); at least `1` |
| `k_smooth` | `int` | `3` | Rows in the SMA that smooths raw %K into %K (TA-Lib's `slowk_period`); at least `1`; `1` gives the fast stochastic |
| `d` | `int` | `3` | Rows in the SMA of %K that gives %D (TA-Lib's `slowd_period`); at least `1` |
| `columns` | list of `str` or `None` | `None` | The three columns to use, in any order: a high, a low and a close (or adjusted close). `None` finds them by name. Names are standard column names or aliases, such as `High`. See [multi-column indicators](../../API.md#10-multi-column-indicators) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`column=` (singular) is for single-column indicators and raises `ValueError` here. Both averages are simple moving averages; TA-Lib's other moving-average types (`slowk_matype`, `slowd_matype`) are not offered.

## Required columns

| Input | Accepted roles | Order for unnamed input |
|---|---|---|
| high | `high` | 1st |
| low | `low` | 2nd |
| close | `close`, then `adj_close` | 3rd |

A missing column raises `ValueError` naming the required and the available columns.

## Output

- Two outputs in the order `stoch_k`, `stoch_d`, each the same length as the input, `float64`, from 0 to 100.
- Each output keeps its own warm-up:

  | Output | First value at row | Warm-up (`NaN`) rows |
  |---|---|---|
  | `stoch_k` | `k + k_smooth - 2` | `k + k_smooth - 2` |
  | `stoch_d` | `k + k_smooth + d - 3` | `k + k_smooth + d - 3` |

  With the defaults %K starts at row 15 and %D at row 17. TA-Lib's `STOCH` starts both at %D's row (it blanks %K for `d - 1` extra rows); wherever both have a value they are equal.
- At least `k + k_smooth + d - 2` rows are required, so both outputs have a value.
- A DataFrame, dict or JSON object gets one column or key per output (a dict keeps the container type of its high column); a 2-D array or a tuple of arrays gives a tuple of the two. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input's casing: `STOCH_K` for `HIGH, LOW, CLOSE`, `Stoch_K` for `High, Low, Close`.

## Edge cases

| Situation | Stochastic |
|---|---|
| A flat window (highest high equal to lowest low) | raw %K is **0** (TA-Lib's convention; the ratio is undefined) |
| A range within rounding of zero: `highest - lowest` at most `1e-14 * (|highest| + |lowest|)` | treated as flat: raw %K 0 |
| A flat stretch after some movement | %K and %D fall to 0, but %D may keep a rounding residue such as `4.5e-14` instead of exactly 0 for as long as the stretch lasts (see the implementation notes); TA-Lib gives the same residue |
| Close equal to the highest high / lowest low of the window | 100 / 0 |
| `k = 1` | raw %K measures the close within its own bar: `100 * (close - low) / (high - low)` |
| `k_smooth = 1` (or `d = 1`) | %K is raw %K (or %D is %K) |
| Close outside the bar's high and low | not rejected; values can then leave 0 to 100 |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` in any column | Rows up to the last leading `NaN` of any column are skipped, then re-padded with `NaN` in every output |
| `NaN` or `inf` after that | `ValueError` naming the column and the row |
| High below low on any row | `ValueError` naming both columns and the row |
| Columns of different lengths | `ValueError` |
| Fewer than `k + k_smooth + d - 2` rows | `ValueError` |
| `k`, `k_smooth` or `d` below 1 | `ValueError` naming the parameter |
| A list, 1-D array or Series (one series) | `TypeError`: the Stochastic needs three columns |

## Implementation notes

### TA-Lib's calculation

PyTA follows TA-Lib 0.8.3's `TA_STOCH` with simple moving averages (`matype` 0, its default) and matches its output bit for bit on the three reference series in `tests/fixtures/` (300 real SPY sessions at 14/3/3 and 5/3/3, and 120 synthetic edge-case rows with a flat stretch and bars with high equal to low):

- **Raw %K** is `(close - lowest) / (highest - lowest) * 100`, dividing by the range first and scaling after, as TA-Lib does.
- **Flat window.** TA-Lib 0.8.3 writes 0 when the range is zero relative to the size of the extremes (`TA_IS_ZERO_SCALED(highest - lowest, |highest| + |lowest|)`, tolerance `1e-14`), so a range made only of rounding error does not turn into a random value between 0 and 100. PyTA uses the same test (`pyta_core::kernels::is_zero_scaled`).
- **Moving averages.** TA-Lib's SMA keeps a running total: it adds the newest value, divides the total by the period, then subtracts the oldest. PyTA does the same, in the same order, rather than using a compensated sum. That is why %D over a flat stretch can read `4.5e-14` rather than 0: after the last non-zero %K values leave the window, the total keeps their rounding error. The residue is far below any meaningful level and matches TA-Lib exactly.
- **Plain arithmetic.** No fused multiply-add is involved.

### Differences from other sources

- **Warm-up.** TA-Lib returns %K only from the row where %D starts; PyTA gives %K its own, earlier start. The values are equal wherever both exist.
- **Defaults.** Lane, StockCharts and TradingView use 14/3/3; TA-Lib uses 5/3/3. PyTA uses 14/3/3.
- **Moving-average type.** TA-Lib's `slowk_matype` and `slowd_matype` choose other averages (EMA, WMA, ...). PyTA uses the SMA only.
- **Flat windows elsewhere.** Some platforms return the previous value, 50 or `NaN` on a flat window; PyTA follows TA-Lib's 0.
- **Periods.** TA-Lib accepts periods up to 100,000; PyTA accepts any period up to `2**31 - 1` that the data can fill.

### Calculation

The Rust kernel (`pyta-momentum`) takes the highest high and lowest low from the shared rolling-extreme kernel of `pyta-core` (the van Herk/Gil-Werman algorithm, the same as `pyta.donchian`'s), so the cost is proportional to the number of rows, independent of `k`, `k_smooth` and `d`.

## See also

[RSI](rsi.md) · [CCI](cci.md) · [Donchian Channels](../volatility/donchian.md) · [SMA](../trend/sma.md) · [API reference](../../API.md) · [Multi-column indicators](../../API.md#10-multi-column-indicators) · [Batch API](../../API.md#9-batch-calculation)
