# SMA: Simple Moving Average

**Category:** Trend · **Function:** `pyta.sma` · **Batch:** `pyta.batch.sma` · **Default column:** close

## What it is

The SMA is the plain average of the last `period` prices. Each new bar drops the oldest price from the window and adds the newest, so the line follows the price but moves more slowly than it, smoothing out short-term noise.

```
SMA[t] = (price[t] + price[t-1] + ... + price[t-period+1]) / period
```

## What it is for

- **Direction of the trend.** A rising SMA means the average price over the window is climbing; a falling one means it is dropping.
- **Support and resistance.** Traders watch long averages such as 50 and 200 as levels where price often pauses.
- **Crossovers.** Price crossing the SMA, or a short SMA crossing a long one (for example 50 over 200, the "golden cross"), is a common trend-change signal.
- **A smoother input for other indicators.** Because PyTA skips leading `NaN`, you can apply `sma` to another indicator's output.

A longer `period` is smoother but reacts later; a shorter one reacts sooner but is noisier. Every price in the window has the same weight, which is why the SMA lags more than an exponential average.

## Usage

```python
import pyta

close = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42]

pyta.sma(close, period=5)
# [nan, nan, nan, nan, 44.1, 44.2, 44.4, 44.66]
```

It works on any supported container and returns the same kind:

```python
pyta.sma(df, period=20)                          # DataFrame with an "sma_20" column
pyta.sma(df, period=20, column="adj close")      # use the adjusted close instead
pyta.sma(pd_series, period=50)                   # Series named "sma_50", same index
pyta.sma(np_array, period=10)                    # NumPy array
```

Many datasets in one call, in parallel when it pays off:

```python
results = pyta.batch.sma({"AAPL": aapl_df, "MSFT": msft_df}, period=20)
results["AAPL"]            # a DataFrame, or the exception if that dataset failed
```

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `data` | list, tuple, array, Series, DataFrame, dict, JSON | required | Prices to average |
| `period` | `int` | required | Window length, `1` to `2**31 - 1`, at most the series length |
| `column` | `str` or `None` | `None` | Column to use when the input has columns. `None` means the close column, or the only column if there is just one. Must be a standard column name or alias, such as `open` or `adj close`. See [column selection](../../API.md#column-selection) |

## Output

- Same length as the input, `float64`.
- The first `period - 1` values are `NaN` (warm-up), because a full window is not available yet.
- A `period` of `1` returns the input unchanged.
- Named `sma_<period>` (for example `sma_20`) in a Series, DataFrame, dict, or JSON object.

## Missing and invalid data

| Input | Result |
|---|---|
| Leading `NaN` or `None` | Skipped; the output has the same number of leading `NaN` plus the warm-up |
| `NaN` or `inf` after the first value | `ValueError` naming the index |
| `period` larger than the series | `ValueError` |
| Empty input | `ValueError` |

## Implementation notes

The Rust kernel (`pyta-trend`) keeps a running sum, adding the new price and subtracting the one that left the window, so the cost is linear in the series length and independent of `period`. The sum is recomputed from scratch every `period` steps to stop floating-point error from accumulating on long series.

## See also

[RSI](../momentum/rsi.md) · [API reference](../../API.md) · [Batch API](../../API.md#9-batch-calculation)
