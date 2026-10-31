# TRIX

**Category:** Momentum · **Function:** `pyta.trix` · **Batch:** `pyta.batch.trix` · **Default column:** close

## What it is

TRIX is the one-bar rate of change, in percent, of a triple-smoothed exponential moving average. It was introduced by Jack Hutson in the early 1980s. PyTA follows TA-Lib's `TA_TRIX`:

1. `EMA1` = EMA of the price over `period` bars.
2. `EMA2` = EMA of `EMA1` over `period` bars.
3. `EMA3` = EMA of `EMA2` over `period` bars.
4. `TRIX = (EMA3 / previous EMA3 − 1) × 100`.

Each EMA has the weight `2 / (period + 1)` and is seeded with the simple average of its input's first `period` values, as [`pyta.ema`](../trend/ema.md) is. The triple smoothing removes cycles shorter than the period, so TRIX oscillates around zero more smoothly than [ROC](roc.md).

## What it is for

- **Trend direction.** TRIX above zero means the triple-smoothed price is rising, below zero falling.
- **Signal line crossings.** The usual signal line is a 9-bar EMA of TRIX; TRIX crossing above it is read as a buy signal and below it as a sell signal. The signal line is not part of TRIX (TA-Lib's has none either); compute it with `pyta.ema`:

  ```python
  trix = pyta.trix(close, period=15)
  signal = pyta.ema(trix, period=9)   # chaining skips TRIX's warm-up
  ```

- **Divergence.** Price making a new high while TRIX makes a lower high suggests fading momentum.

## Usage

```python
import pyta

pyta.trix(close)               # period defaults to 30, as in TA-Lib
pyta.trix(close, period=15)    # Hutson's and StockCharts' period
pyta.trix(df, period=15)       # a DataFrame with one column, "trix", from the close
```

TRIX is also in the momentum namespace; both names are the same function:

```python
pyta.momentum.trix(close, period=15)   # same as pyta.trix
from pyta.momentum import trix
```

Many datasets in one call:

```python
results = pyta.batch.trix([df1, df2, df3], period=15)   # list of results, in order
pyta.batch.momentum.trix({"SPY": spy, "QQQ": qqq})      # dict of results, same keys
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON, CSV | required | Prices |
| `period` | `int` | `30` | Period of each of the three EMAs, `1` to `2**31 - 1`. `30` is TA-Lib's default; Hutson and StockCharts use `15`, so pass `period=15` for their charts (TA-Lib caps it at 100,000) |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Same length as the input, `float64`, in percent.
- The first `3 × (period − 1) + 1` values are `NaN` (warm-up: three EMA warm-ups, then one bar for the rate of change). With the default 30 the first value is on row 88; with 15, on row 43.
- At least `3 × period − 1` values are required.
- Named `trix` in a Series, DataFrame, dict, or JSON object (`TRIX` when the input column is `CLOSE` or `Close`: it is an abbreviation).

## Edge cases

| Situation | TRIX |
|---|---|
| Flat prices | `0` |
| The previous `EMA3` is exactly `0` | `0`, as TA-Lib writes (not an infinity) |
| `period = 1` | Each EMA is a copy of its input, so TRIX is the one-bar [ROC](roc.md) of the price, as in TA-Lib |
| A previous `EMA3` that is zero next to the current one (`|previous| ≤ 1e-14 × |EMA3|`) | `0`, as for [ROC](roc.md), so every value is finite; TA-Lib divides here and can return `±inf` |

TRIX is meant for prices, which are positive; with series that cross zero the ratio is hard to read, as for ROC.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in the output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `3 × period − 1` values | `ValueError` (`at least 89 values are required, got 88`) |
| Empty input | `ValueError` |

## Implementation notes

PyTA follows TA-Lib 0.8.3's `TA_TRIX`: the same seeds, the same lockstep EMAs, the rate of change of `EMA3` (with ROC's scaled zero test on the previous `EMA3`, where TA-Lib tests for exactly `0`), the warm-up (`3 × (period − 1) + 1`) and the default (30, where Hutson used 15). TA-Lib 0.8.3 writes each EMA update as a fused multiply-add, `fma(beta, previous, k × price)`; PyTA uses the update every PyTA EMA shares, `(price − previous) × k + previous`, so the EMAs can differ from TA-Lib's in the last bits and TRIX agrees with TA-Lib's own output to about `4e-13` relative on 300 real SPY closes at periods 30 and 15 and on a synthetic edge series (`tests/fixtures/trix_30_talib.csv`, `trix_15_talib.csv`, `trix_30_edge_talib.csv`), well inside the `1e-9` tolerance. PyTA promises agreement with TA-Lib 0.8.3 within `1e-9`, not bit for bit, and uses plain multiplies and adds everywhere, never a fused multiply-add or code picked by CPU at run time ([API: Agreement with TA-Lib](../../API.md#agreement-with-ta-lib)). In exchange TRIX equals `pyta.roc(pyta.ema(pyta.ema(pyta.ema(x, n), n), n), 1)` bit for bit.

The Rust kernel (`pyta-momentum`) runs the three EMAs and the rate of change in one pass, built from the shared `pyta_core` EMA step and kept bit for bit equal to three `kernels::ema` passes and `kernels::rate_of_change` (a property test checks it); its cost does not depend on `period`.

## See also

[ROC](roc.md) · [EMA](../trend/ema.md) · [TEMA](../trend/tema.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
