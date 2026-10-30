# Volume Rate of Change (Volume ROC)

**Category:** Volume · **Function:** `pyta.vroc` · **Batch:** `pyta.batch.vroc` · **Column:** volume

## What it is

Volume ROC is the percentage change in volume from `period` bars earlier: [ROC](../momentum/roc.md) applied to volume instead of price.

`VROC = (volume / volume period bars earlier − 1) × 100`

A value of 100 means volume doubled over `period` bars; −50 means it halved.

## What it is for

- **Confirming breakouts.** A price breakout on a sharp rise in volume (a large positive Volume ROC) is read as more reliable than one on flat volume.
- **Spotting exhaustion.** A trend continuing on falling volume (negative Volume ROC) is read as losing participation.
- **Comparing activity** across periods or assets on a common percentage scale.

## Usage

Volume ROC works on one column, the **volume** by default (not the close):

```python
import pandas as pd
import pyta

df = pd.read_csv("prices.csv")   # date, open, high, low, close, volume
pyta.vroc(df, period=10)         # a DataFrame with one column, "vroc", from the volume column
pyta.vroc(df)                    # period defaults to 10
pyta.vroc(volumes, 12)           # a list, array or Series of volumes
```

Any other column can be chosen with `column=` (a standard name or alias), and a container with a single column uses it whatever its name:

```python
pyta.vroc(df, column="close")            # the same as pyta.roc(df, 10)
pyta.vroc({"obv": obv_values}, 5)        # a lone column, for example another indicator's output
```

Volume ROC is also in the volume namespace; both names are the same function:

```python
pyta.volume.vroc(df)   # same as pyta.vroc
```

Many datasets in one call:

```python
results = pyta.batch.vroc([df1, df2, df3], period=10)   # list of results, in order
pyta.batch.volume.vroc({"SPY": spy, "QQQ": qqq})        # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, NumPy array, Series, DataFrame, dict, JSON, CSV | required | Volumes, or a table with a volume column |
| `period` | `int` | `10` | Rows back to the volume compared with, at least `1` (TA-Lib's ROC default; StockCharts uses 12 or 25) |
| `column` | `str` or `None` | `None` | Column to use; `None` means the volume column, or the only column if there is just one. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

`columns=` (plural) is for multi-column indicators and raises `ValueError` here.

## Output

- Same length as the input, `float64`.
- The first `period` values are `NaN` (warm-up). At least `period + 1` values are required.
- Named `vroc` in a DataFrame, dict, JSON object or CSV (`VROC` when the volume column is upper or title case, as yfinance's `Volume`: it is an abbreviation).

## Edge cases

| Situation | Volume ROC |
|---|---|
| Volume unchanged over `period` rows | `0` |
| Volume now zero | `−100` |
| Volume `period` rows earlier exactly zero | `0`, as TA-Lib writes (not an infinity) |
| Flat volume | `0` |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded with `NaN` in the output |
| `NaN` or `inf` after that | `ValueError` |
| A negative value in a column matched to the volume role (by name, such as `volume`, `Volume` or `vol`, or a Series named so) | `ValueError` naming the column and the row (zero is valid): `column 'Volume' (volume) is negative at index 2 (-300.0); volume must be zero or more on every row` |
| A negative value in unnamed input or another column | Accepted (it is not known to be volume; OBV's output, for example, is often negative) |
| Fewer than `period + 1` values | `ValueError` (`at least 11 values are required, got 10`) |
| `period` below 1 | `ValueError` |

The negative-volume check applies to every single-column indicator whose column is the volume role, so `pyta.sma(df, 20, column="volume")` rejects a negative volume too.

## Implementation notes

TA-Lib has no separate Volume ROC; PyTA applies TA-Lib 0.8.3's `ROC` to volume, through the same shared kernel as `pyta.roc` (`pyta_core::kernels::rate_of_change`), so the two give identical bits on the same column. Both TA-Lib fixtures (`talib.ROC` of the SPY and edge-series volumes, the edge series with zero-volume rows) match bit for bit. The default period is TA-Lib's ROC default, 10.

## See also

[ROC](../momentum/roc.md) · [OBV](obv.md) · [Volume indicators](README.md) · [API reference](../../API.md)
