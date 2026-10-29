# BBANDS: Bollinger Bands

**Category:** Volatility · **Function:** `pyta.bbands` · **Batch:** `pyta.batch.bbands` · **Default column:** close

## What it is

Bollinger Bands, introduced by John Bollinger in the 1980s, draw an envelope around a moving average whose width follows volatility: the bands widen when prices swing and narrow when the market is quiet. They are measured in the same units as the prices.

For each bar, over the last `period` values:

1. The **middle band** is the simple moving average of the window.
2. The window's **standard deviation** is the square root of the average squared distance from that mean, dividing by `period` (the *population* deviation, as Bollinger defines it).
3. The **upper band** is the middle band plus `k` standard deviations; the **lower band** is the middle band minus `k` standard deviations.

Bollinger's standard settings are a 20-bar window and `k = 2`, PyTA's defaults.

## What it is for

- **Relative highs and lows.** Bollinger's own reading: a price at the upper band is high *relative to its recent range*, at the lower band low. That is context, not a signal by itself; in a strong trend prices "walk the band".
- **The squeeze.** When the bands narrow to their tightest in months, volatility is low, and low volatility tends to be followed by a large move. The width `(upper - lower) / middle` (Bandwidth) measures it.
- **%b.** `(close - lower) / (upper - lower)` places the close inside the bands: 1 at the upper band, 0 at the lower one.
- **Parameters.** Bollinger suggests widening `k` slightly for longer windows and narrowing it for shorter ones (about 2.1 at 50 bars, 1.9 at 10).
- **Chaining.** `pyta.bbands(pyta.ema(close, 10))` puts bands around another series, because leading `NaN` is skipped.

## Usage

```python
import pyta

close = [10.0, 11.0, 12.0, 11.0, 10.0, 10.0, 10.0, 10.0, 10.0]

upper, middle, lower = pyta.bbands(close, period=5)
# upper:  [nan, nan, nan, nan, 12.297, 12.297, 12.2, 11.0, 10.0]  (rounded)
# middle: [nan, nan, nan, nan, 10.8, 10.8, 10.6, 10.2, 10.0]
# lower:  [nan, nan, nan, nan, 9.303, 9.303, 9.0, 9.4, 10.0]
```

BBANDS is also in the volatility namespace; both names are the same function:

```python
pyta.volatility.bbands(close, period=5)  # same as pyta.bbands
from pyta.volatility import bbands
```

A DataFrame (or a dict, or a JSON object) gains one column per band:

```python
pyta.bbands(df)                        # period 20, k 2.0: columns bbands_upper, bbands_middle, bbands_lower
pyta.bbands(df, period=50, k=2.1)
pyta.bbands(df, column="adj close")
pyta.bbands(yfinance_df).columns       # ['BBANDS_Upper', 'BBANDS_Middle', 'BBANDS_Lower']
```

Many datasets in one call:

```python
results = pyta.batch.bbands([df1, df2, df3])     # list of results, in order
pyta.batch.volatility.bbands([df1, df2, df3])    # same as pyta.batch.bbands
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON, CSV | required | Prices |
| `period` | `int` | `20` | Number of values in each window, at least `2` (TA-Lib's minimum; one value has no spread) |
| `k` | `float` | `2.0` | Width of each band in standard deviations, any finite number above `0`; an `int` is accepted. One value for both bands |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |
| `output` | `str` or `None` | `None` | Container to return instead of the input's own: `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"` or `"csv_bytes"`, each in one fixed shape, with a pandas index carried to the named targets. See [output conversion](../../API.md#output-conversion-output) |

## Output

- Three outputs in the order `bbands_upper`, `bbands_middle`, `bbands_lower`, each the same length as the input, `float64`. Upper is never below middle, and middle never below lower.
- All three share one warm-up: the first `period - 1` values are `NaN`.
- At least `period` values are required.
- One-series input (list, tuple, array, Series) returns a tuple of the three, each in the input's own form: `upper, middle, lower = pyta.bbands(close)`. A DataFrame, dict or JSON object gets one column or key per output; a JSON array of numbers returns a JSON object keyed by output name. See [multi-output indicators](../../API.md#11-multi-output-indicators).
- Names follow the input column's casing: `BBANDS_UPPER` for `CLOSE`, `BBANDS_Upper` for `Close` (`BBANDS` is an abbreviation, the parts are words).

## Edge cases

| Situation | BBANDS |
|---|---|
| A flat window (every value the same) | three equal bands, exactly the repeated value |
| `period` equal to the input length | one value per band, from the whole series |
| A large price with a tiny spread (`100000 + 0.001 × noise`) | full precision (see Implementation notes) |

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped, then re-padded in every output |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| Fewer than `period` values | `ValueError` |
| `period` below 2, or `k` zero, negative or not finite | `ValueError` naming the parameter |
| Empty input | `ValueError` |

## Implementation notes

- **TA-Lib convention.** PyTA follows TA-Lib's `TA_BBANDS` (0.8.3) with a simple moving average (`matype=0`): middle = SMA, bands = middle ± `k` × the population standard deviation of the same window. Results match TA-Lib to within `1e-9` on real SPY closes and on an edge-case series. TA-Lib 0.8.3's default period is 20, as Bollinger's; older TA-Lib releases defaulted to 5.
- **One `k` for both bands.** TA-Lib takes separate `nbdevup` and `nbdevdn`; PyTA exposes one `k` for both, which is how Bollinger Bands are defined and used. For asymmetric bands, compute `middle ± k × pyta.stddev(close, period)` yourself.
- **SMA only.** TA-Lib's `matype` (EMA, WMA, ... as the middle band) is not offered: Bollinger's definition uses the SMA, and the deviation is always taken around the window's own mean.
- **Positive `k` only.** TA-Lib accepts any `nbdev`, including 0 and negative values (which swap the bands); PyTA requires a finite `k` above 0, so `bbands_upper` is always the upper band.
- **Population, not sample.** Statistics packages often divide by `period - 1` (pandas' `rolling().std()` by default). Bollinger, TA-Lib and PyTA divide by `period`; use `rolling(period).std(ddof=0)` to compare.
- **Stable calculation.** One pass of the shared `pyta-core` kernel gives each window's mean and deviation; the deviation is centred on the window's own mean and summed afresh (two passes per window), so it keeps full precision when prices are large and the spread small, where a running sum of squares loses most of its digits. The cost is `O(rows × period)`.
- **Flat windows.** A deviation within `1e-14` of the window's mean (TA-Lib's zero tolerance, `TA_IS_ZERO_SCALED`) is rounding, not spread, and is reported as exactly `0`, so a flat window gives three identical bands, as TA-Lib does. STDDEV uses the same rule.

## See also

[STDDEV](stddev.md) · [ATR](atr.md) · [SMA](../trend/sma.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
