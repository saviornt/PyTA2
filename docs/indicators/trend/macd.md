# MACD: Moving Average Convergence/Divergence

**Category:** Trend · **Function:** `pyta.macd` · **Batch:** `pyta.batch.macd` · **Default column:** close · **Outputs:** `macd`, `macd_signal`, `macd_hist`

## What it is

MACD, devised by Gerald Appel, compares a fast and a slow [EMA](ema.md) of the price. PyTA follows TA-Lib's `TA_MACD`:

1. **`macd`** (the MACD line) is the `fast` EMA minus the `slow` EMA. Both EMAs start at row `slow - 1`: the slow EMA is seeded with the mean of the first `slow` prices, and the fast EMA with the mean of the `fast` prices ending at that row.
2. **`macd_signal`** (the signal line) is the `signal`-period EMA of the MACD line.
3. **`macd_hist`** (the histogram) is `macd − macd_signal`.

## What it is for

- **Trend and momentum.** `macd` above 0 means the fast average is above the slow one (upward momentum); below 0, downward.
- **Crossovers.** `macd` crossing above its signal line (`macd_hist` turning positive) is read as bullish, crossing below as bearish.
- **Divergence.** Price making a new high while `macd` does not is often read as weakening momentum.
- **The histogram** shows whether the gap between the two lines is widening or narrowing.

## Usage

```python
import pyta

out = pyta.macd(df)                  # DataFrame with columns macd, macd_signal, macd_hist
out = pyta.macd(df, 5, 35, 5)        # fast=5, slow=35, signal=5
macd, signal, hist = pyta.macd(close)   # one series in: a tuple of three, in that order
```

MACD is also in the trend namespace; both names are the same function:

```python
pyta.trend.macd(close)               # same as pyta.macd
from pyta.trend import macd
```

Each output is returned in the input's container type:

| Input | Result |
|---|---|
| DataFrame | DataFrame with the three columns, same index |
| dict of columns | dict with the three keys, each value in the input column's container type |
| JSON records / JSON object of arrays | every record / the object gets the three keys; `NaN` is `null` |
| list, tuple, NumPy array, pandas Series | a tuple of three of the same kind (each Series named by its output, same index) |
| JSON array of numbers | a JSON object keyed by output name |

Names follow the casing of the input column: `MACD`, `MACD_SIGNAL`, `MACD_HIST` for `CLOSE`, and `MACD`, `MACD_Signal`, `MACD_Hist` for yfinance's `Close` (see [names and casing](../../API.md#11-multi-output-indicators)). To use one output in another indicator, pass it directly: `pyta.sma(out["macd_signal"], period=5)`.

Many datasets in one call, with the same parameters for all:

```python
results = pyta.batch.macd({"SPY": spy, "QQQ": qqq})    # dict of results, by key
pyta.batch.trend.macd([df1, df2], fast=8, slow=17)     # same as pyta.batch.macd
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices |
| `fast` | `int` | `12` | Period of the fast EMA, at least `2` |
| `slow` | `int` | `26` | Period of the slow EMA, at least `2` |
| `signal` | `int` | `9` | Period of the signal line's EMA, at least `1` |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape (a tuple of three, a DataFrame, or one key or column per output), with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

If `slow` is less than `fast`, the two are swapped, as TA-Lib does, so `macd(close, 26, 12, 9)` equals `macd(close, 12, 26, 9)`. The ranges are TA-Lib's lower bounds; a parameter out of range raises `ValueError` naming it (`fast must be between 2 and 2147483647, got 1`).

## Output

- Three outputs in the order `macd`, `macd_signal`, `macd_hist`, each the same length as the input, `float64`.
- At least `slow + signal - 1` values are required, so every output has at least one value.
- Each output has its own warm-up (`NaN`): `macd` has values from row `slow - 1`; `macd_signal` and `macd_hist` from row `slow + signal - 2`. With the defaults: rows 25 and 33.
- A leading `NaN` run in the input shifts all three outputs by the same number of rows.

## Edge cases

| Situation | Result |
|---|---|
| Flat prices | `0` in every output |
| `fast == slow` | `0` in every output |
| `slow < fast` | Swapped: the same as with `fast` and `slow` exchanged |
| `signal=1` | `macd_signal` equals `macd`, `macd_hist` is `0` |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in every output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `slow + signal - 1` values | `ValueError` |
| Empty input | `ValueError` |

## Differences from other definitions

- **Appel's original** used the conventional 12/26/9 EMAs, but the EMA seed was not standardized; libraries that start each EMA from the first price (Tulip, `ta`) give different early values that converge over time. PyTA follows TA-Lib, the de facto standard: both EMAs start at row `slow - 1` from simple-mean seeds.
- **TA-Lib's warm-up.** TA-Lib blanks all three outputs until the signal line exists (row `slow + signal - 2`). PyTA keeps each output's own warm-up, so `macd` has `signal - 1` more values at the start. Where TA-Lib has a value, PyTA's is the same.
- **`slow < fast`.** TA-Lib and pandas-ta swap silently, as PyTA does; Tulip rejects it, and `ta` returns the negated line.

## Implementation notes

The Rust kernel (`pyta-trend`) computes all three EMAs in one pass, with the same arithmetic in the same order as three separate EMA passes (so the results are identical to the bit), and allocates only the three outputs. PyTA matches TA-Lib's own output to `1e-9` on 300 real SPY closes for 12/26/9 and 5/35/5 (`tests/fixtures/macd_12_26_9_talib.csv`, `macd_5_35_5_talib.csv`, generated with TA-Lib 0.8.3; the `macd` column before the signal exists comes from TA-Lib with `signalperiod=1`).

## See also

[EMA](ema.md) · [SMA](sma.md) · [API reference](../../API.md) · [Multi-output indicators](../../API.md#11-multi-output-indicators)
