# ROC: Rate of Change

**Category:** Momentum · **Function:** `pyta.roc` · **Batch:** `pyta.batch.roc` · **Default column:** close

## What it is

The Rate of Change is the percentage change of the price over the last `period` bars. PyTA follows TA-Lib's `TA_ROC`:

```
ROC = (price / price `period` bars ago − 1) × 100
```

It oscillates around zero: positive when the price is above where it was `period` bars ago, negative below. Unlike [RSI](rsi.md) or [Williams %R](willr.md) it has no upper bound, and its lower bound is −100 (a price that fell to zero).

## What it is for

- **Momentum.** The further ROC is from zero, the faster the price is moving; a ROC that keeps rising shows an accelerating trend.
- **Zero-line crossings.** ROC crossing above zero (the price is back above its level `period` bars ago) is read as a turn up, and below zero as a turn down.
- **Divergence and extremes.** A new price high with a lower ROC high suggests fading momentum. Overbought and oversold levels depend on the instrument, since ROC is unbounded.
- **Comparing instruments.** As a percentage it is comparable across prices of different size, unlike TA-Lib's `MOM` (the plain difference).

## Usage

```python
import pyta

close = [10.0, 11.0, 12.0, 9.0, 15.0]

pyta.roc(close, period=2)
# [nan, nan, 20.0, -18.18..., 25.0]
```

ROC is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.roc(close, period=2)   # same as pyta.roc
from pyta.momentum import roc
```

```python
pyta.roc(df)                               # period defaults to 10, as in TA-Lib
pyta.roc(df, period=12)                    # StockCharts' default
pyta.roc(df, period=20, column="adj close") # on the adjusted close
```

Many datasets in one call:

```python
results = pyta.batch.roc([df1, df2, df3], period=12)   # list of results, in order
pyta.batch.momentum.roc({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

TA-Lib's other rate-of-change functions are not separate PyTA indicators; derive them from `roc`:

| TA-Lib | Formula | From PyTA |
|---|---|---|
| `ROCP` | `(price − earlier) / earlier` | `pyta.roc(x, n) / 100` |
| `ROCR` | `price / earlier` | `pyta.roc(x, n) / 100 + 1` |
| `ROCR100` | `price / earlier × 100` | `pyta.roc(x, n) + 100` |
| `MOM` | `price − earlier` | `x - x.shift(n)` in pandas |

The derived values can differ from TA-Lib's own in the last bit. Where the earlier price is 0, `roc` is 0, so the derived `ROCR` and `ROCR100` read 1 and 100; check TA-Lib's own convention for those rows if they matter.

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON, CSV | required | Prices |
| `period` | `int` | `10` | Bars back to the price compared with, `1` to `2**31 - 1` (TA-Lib's default; StockCharts uses 12; TA-Lib caps it at 100,000) |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`, in percent.
- The first `period` values are `NaN` (warm-up): the first value is on row `period`.
- At least `period + 1` values are required.
- Named `roc` in a Series, DataFrame, dict, or JSON object (`ROC` when the input column is `CLOSE` or `Close`: it is an abbreviation; see [names and casing](../../API.md#11-multi-output-indicators)).

## Edge cases

| Situation | ROC |
|---|---|
| Flat prices | `0` |
| The earlier price is exactly `0` | `0`, as TA-Lib writes (not an infinity) |
| The current price is `0` (earlier non-zero) | `−100` |
| An earlier price that is zero next to the current one (`|earlier| ≤ 1e-14 × |price|`, such as `1e-300` against `5`) | `0`, so every value is finite (below `1e14` %). TA-Lib divides here and returns a huge value or `±inf` |

ROC is meant for prices, which are positive. With negative values (spreads, returns) the sign of the result follows the ratio, as in TA-Lib, and is hard to read.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period + 1` values | `ValueError` (`at least 11 values are required, got 10`) |
| Empty input | `ValueError` |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_ROC`: the same expression in the same order (`(price / earlier − 1) × 100`), the warm-up (`period`) and the default (10). It matches TA-Lib's own output bit for bit on 300 real SPY closes and on a synthetic edge series with a zero price (`tests/fixtures/roc_10_talib.csv`, `roc_10_edge_talib.csv`, generated with TA-Lib 0.8.3). The one deliberate difference is the zero test on the earlier price: TA-Lib tests for exactly `0`, PyTA for zero relative to the current price (TA-Lib's own scaled test, `|earlier| ≤ 1e-14 × |price|`), so a tiny non-zero base gives `0` instead of an overflow and every output is finite; real prices never come near it. The calculation is the shared `pyta_core::kernels::rate_of_change`, which Volume ROC uses too; it costs one division per bar whatever the period. TA-Lib rejects periods above 100,000; PyTA accepts any period the data covers.

## See also

[RSI](rsi.md) · [Williams %R](willr.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
