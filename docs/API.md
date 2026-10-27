# PyTA API

> **Status:** Active development. Sections marked *(planned)* describe the intended API and are not implemented yet. Everything else reflects the current code and is covered by tests.

PyTA calculates technical-analysis indicators in Rust and exposes them through a simple Python API. Pass data in whatever container you have, and get results back in the same kind of container. Concurrency is handled internally; you don't need `asyncio` or threads.

## 1. Quick start

```python
import numpy as np
import pyta

close = np.array([10.0, 11.0, 12.0, 13.0, 12.0, 14.0])

sma = pyta.sma(close, period=3)
rsi = pyta.rsi(close, period=3)
```

## 2. Import styles

| Style | Example | Status |
|---|---|---|
| Short-hand | `pyta.sma(...)` | Available |
| By category | `pyta.trend.sma(...)`, `pyta.momentum.rsi(...)` | *Planned* |

Both styles call the same implementation. The category modules currently live at `pyta.indicators.trend` and `pyta.indicators.momentum`; exposing them as `pyta.trend` and `pyta.momentum` is planned. `pyta._native` is internal and not part of the API.

## 3. Indicators

| Function | Category | Signature |
|---|---|---|
| `sma` | Trend | `sma(data, period, *, column=None)` |
| `rsi` | Momentum | `rsi(data, period=14, *, column=None)` |

`period` is required for `sma`. `column` selects a column for inputs that have columns (see [Input containers](#4-input-containers)).

### SMA (Simple Moving Average)

Each value is the arithmetic mean of the current price and the preceding `period - 1` prices.

- The first `period - 1` results are `NaN` (warm-up).
- `period` must not exceed the series length.

### RSI (Relative Strength Index)

Uses Wilder's smoothing. The first average gain and loss are the simple means of the first `period` price changes; later values use `avg = (prev_avg * (period - 1) + current) / period`. `RSI = 100 * avg_gain / (avg_gain + avg_loss)`.

- Needs at least `period + 1` values. The first `period` results are `NaN` (warm-up).
- Flat prices give `0`; a series with no losses gives `100`; a series with no gains gives `0`.

## 4. Input containers

Every supported container is converted to a one-dimensional `float64` series, and the result is returned in the same kind of container.

| Input | Output |
|---|---|
| `list` | `list` |
| `tuple` | `tuple` |
| NumPy array (any real numeric dtype) | `float64` array |
| pandas Series | Series with the same index, named `<indicator>_<period>` |
| pandas DataFrame | DataFrame with the same index and one `<indicator>_<period>` column |
| `dict` of columns | `dict` with one `<indicator>_<period>` key; the value keeps its container type |
| JSON `str` | JSON `str`, same shape |
| JSON `bytes` or `bytearray` | JSON `bytes`, same shape |

Details:

- **Output names** are lowercase, for example `sma_20` and `rsi_14`.
- **Dict values** may be lists, tuples, NumPy arrays, or pandas Series.
- **JSON** may be an array of numbers, an array of records (`[{"close": 1.0}, ...]`), or an object of arrays (`{"close": [1.0, ...]}`). Results use the same shape. `NaN` is written as `null`.
- **pandas** is optional. PyTA only recognizes pandas objects when pandas has been imported by your program. DataFrames with MultiIndex columns are not supported; select a single column first.
- **Masked arrays** are accepted; masked values become `NaN`.
- **Input is never modified.**

### Column selection

For DataFrame, dict, and JSON-object or record input, PyTA picks the column to use:

1. If you pass `column=`, that column is used.
2. Otherwise, if there is only one column, it is used.
3. Otherwise PyTA looks for `close` (also `closing`, `close_price`, `closing_price`).

Names ignore case and surrounding whitespace, so `" Close "` matches `"close"`. Two names that are identical after this normalization are rejected as ambiguous. Passing `column=` with input that has no columns (list, tuple, array, Series, JSON array of numbers) raises `ValueError`.

```python
pyta.sma(df, period=20)                  # uses the "close" column
pyta.sma(df, period=20, column="open")   # uses the "open" column
```

## 5. Output conventions

- Results are `float64` and the same length as the input.
- Warm-up positions are `NaN` (`null` in JSON).
- A pandas result keeps the input's index; positions are never reordered.

## 6. Missing and non-finite values

| Input value | Behavior |
|---|---|
| `None` (list) or `null` (JSON) | Treated as a gap (`NaN`) |
| Leading `NaN` | Skipped, then re-padded as `NaN` in the output |
| `NaN` after the first valid value | `ValueError`, naming the index |
| `inf` / `-inf` | `ValueError`, naming the index |
| Empty input, or only `NaN` | `ValueError` |

Skipping leading `NaN` lets you chain indicators, because one indicator's warm-up period passes cleanly into the next:

```python
smoothed_rsi = pyta.sma(pyta.rsi(close, period=14), period=5)
```

## 7. Errors

PyTA uses built-in exceptions, and every exception carries a message that explains what went wrong and, where possible, how to fix it. Messages name the offending parameter, value, or position, and state what was expected.

```python
>>> pyta.sma([1.0, 2.0, 3.0], period=5)
ValueError: period (5) exceeds the series length (3); sma needs at least 5 values

>>> pyta.sma([1.0, float("nan"), 3.0, 4.0], period=2)
ValueError: non-finite value (nan) at index 1; only leading NaN values are skipped

>>> pyta.sma(df, period=20)   # df has no recognizable close column
ValueError: no "close" column found; available columns: ["px", "vol"]. Pass column= to choose one

>>> pyta.sma([1.0, 2.0, 3.0], period="14")
TypeError: period must be an integer, got str
```

The examples show the intended style; exact wording may change between releases, so catch the exception type rather than matching message text.

| Exception | Raised for |
|---|---|
| `TypeError` | Unsupported container or dtype (strings, booleans, complex numbers), non-integer `period` (including `bool`), non-string `column`, JSON of the wrong shape |
| `ValueError` | `period` outside `1` to `2**31 - 1`, period larger than the series (`sma`) or fewer than `period + 1` values (`rsi`), empty or non-finite input, multidimensional or ragged input, invalid JSON, a missing or ambiguous column, `column=` on input without columns |
| `RuntimeError` | An internal calculation failure |

NumPy integers are accepted as `period`.

## 8. Calling from async code

PyTA's functions are ordinary synchronous calls. The native boundary releases the GIL while Rust calculates, so other Python threads keep running. A Python-level async API is not planned for now.

---

## 9. Batch calculation *(planned)*

Apply one indicator to many datasets in a single call. The engine decides internally whether to run them sequentially or concurrently.

```python
results = pyta.batch.sma(datasets, period=14)
```

- `pyta.batch` mirrors the top-level indicator functions, with the same names and parameters.
- `datasets` can be a **list** or a **mapping** (for example, ticker to data). Each dataset can be any supported container, and the result has the same shape and order as the input, with each result in its own input's container type.
- **A failure never cancels the others.** Each dataset gets a result. A dataset that fails is represented by the exception that explains why, in the same position or under the same key, so you can see which dataset failed and the reason.

```python
results = pyta.batch.sma({"AAPL": aapl, "MSFT": msft}, period=14)

for ticker, result in results.items():
    if isinstance(result, Exception):
        print(f"{ticker} failed: {result}")
```

## 10. Multi-column indicators *(planned)*

Some indicators need more than one column (for example ATR needs high, low, and close). Pass your OHLCV data in any supported container; PyTA identifies it, finds the columns the indicator needs, and returns the same kind of container.

```python
atr = pyta.atr(df, period=14)
```

- **Automatic selection.** PyTA matches column names to the roles an indicator needs. If you pass more columns than needed (for example all of open, high, low, close, and volume), the extras are ignored.
- **Explicit override.** `columns=[...]` names the columns to use, in the order listed in the indicator's documentation:

  ```python
  pyta.atr(df, period=14, columns=["H", "L", "C"])
  ```

- **Missing data.** If a required column can't be found, a `ValueError` names what the indicator requires and which columns were available, so you don't have to know in advance what an indicator needs.
- Each indicator's documentation lists its required inputs.

## 11. Multi-output indicators *(planned)*

Indicators that produce several series, such as MACD, return them in the input's container type:

| Indicator | Output names |
|---|---|
| MACD | `macd`, `macd_signal`, `macd_hist` |

A DataFrame result has one column per output, and a dict or JSON object has one key per output. The casing of the output names follows the casing used by the input's columns.

## 12. Data sources *(planned)*

PyTA does not depend on any data provider. It accepts the data types that providers return:

| Provider | Returns | Support |
|---|---|---|
| yFinance | pandas DataFrame or Series, tuple, dict | Available (single-level columns) |
| AlphaVantage | JSON, CSV | JSON available; CSV planned |

## 13. Indicator catalog

See the [README](../README.md#indicators) for implemented and planned indicators. Every indicator will follow the conventions in this document.