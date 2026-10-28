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

Both styles call the same implementation. Each indicator lives in its own module under `pyta.indicators` (for example `sma.py`, holding both the single call and the batch call); exposing category namespaces as `pyta.trend` and `pyta.momentum` is planned. `pyta._native` is internal and not part of the API.

## 3. Indicators

| Function | Category | Signature |
|---|---|---|
| `sma` | Trend | `sma(data, period, *, column=None)` |
| `rsi` | Momentum | `rsi(data, period=14, *, column=None)` |

`period` is required for `sma`. `column` selects a column for inputs that have columns (see [Column selection](#column-selection)); `None` means the indicator's default column, which is `close` for both. Each indicator has a page in the [indicator wiki](indicators/): [SMA](indicators/trend/sma.md), [RSI](indicators/momentum/rsi.md).

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

1. If you pass `column=`, that column is used. The name must be a standard column name (see the table below), so code reads the same on every data source; any other name raises `ValueError`, and so does a standard name the input does not have.
2. Otherwise, if there is only one column, it is used.
3. Otherwise PyTA looks for the indicator's **default column**. `sma` and `rsi` default to `close`; an indicator that works on something else (for example a volume average) declares its own default.

Names ignore case, whitespace, and the separators `.`, `_` and `-`, so `" Close "`, `"Adj_Close"` and `"adj.close"` all match as written. A name also matches the aliases of its column role:

| Role | Names that match |
|---|---|
| `open` | `open`, `opening`, `open_price`, `opening_price`, `o` |
| `high` | `high`, `highest`, `high_price`, `highest_price`, `h` |
| `low` | `low`, `lowest`, `low_price`, `lowest_price`, `l` |
| `close` | `close`, `closing`, `close_price`, `closing_price`, `c` |
| `adj_close` | `adj_close`, `adjusted_close`, `adj_close_price`, `adjusted_close_price`, `adj_closing`, `adjusted_closing` (any spelling of the separators, such as `Adj Close`) |
| `volume` | `volume`, `volumes`, `vol`, `v` |

A role matches only its own aliases: asking for `close` never falls back to the adjusted close, and a column named exactly as you wrote it wins over an alias. Two names that are identical after this normalization (for example `"Adj_Close"` and `"adj close"`) are rejected as ambiguous. The input's own columns may be named anything; only the name you ask for is restricted. If your columns use other names, rename them first (`df.rename(columns={"px": "close"})`). An input with a single column needs no `column=` at all, which is what lets one indicator's output feed the next. Passing `column=` with input that has no columns (list, tuple, array, Series, JSON array of numbers) raises `ValueError`.

```python
pyta.sma(df, period=20)                          # the "close" column
pyta.sma(df, period=20, column="open")           # the "open" column
pyta.sma(df, period=20, column="adjusted close") # the "Adj Close" column
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
ValueError: period (5) exceeds the series length (3); use a smaller period or provide more data

>>> pyta.rsi([1.0, 2.0, 3.0], period=5)
ValueError: not enough data: at least 6 values are required, got 3

>>> pyta.sma([1.0, float("nan"), 3.0, 4.0], period=2)
ValueError: non-finite value (NaN or infinity) at index 1; only leading NaN values are skipped

>>> pyta.sma(df, period=20)   # df has columns "px" and "vol"
ValueError: no 'close' column found; available columns: 'px', 'vol'. Pass column= to choose one

>>> pyta.sma([1.0, 2.0, 3.0], period=0)
ValueError: period must be between 1 and 2147483647, got 0

>>> pyta.sma([1.0, 2.0, 3.0], period="14")
TypeError: period must be an integer, got str
```

The examples show the current wording, which may change between releases, so catch the exception type rather than matching message text.

| Exception | Raised for |
|---|---|
| `TypeError` | Unsupported container or dtype (strings, booleans, complex numbers), DataFrames with MultiIndex columns, non-integer `period` (including `bool`), non-string `column`, JSON of the wrong shape (including arrays that mix records and numbers) |
| `ValueError` | `period` outside `1` to `2**31 - 1`, period larger than the series (`sma`) or fewer than `period + 1` values (`rsi`), empty input or input with no valid values, a non-finite value after the first valid value, multidimensional or ragged input, invalid JSON, a missing or ambiguous column, `column=` on input without columns |
| `RuntimeError` | An internal calculation failure |

NumPy integers are accepted as `period`.

## 8. Calling from async code

PyTA's functions are ordinary synchronous calls. The native boundary releases the GIL while Rust calculates, so other Python threads keep running. A Python-level async API is not planned for now.

---

## 9. Batch calculation

Apply one indicator to many datasets in a single call. The engine decides internally whether to run them sequentially or concurrently.

```python
results = pyta.batch.sma(datasets, period=14)
```

- `pyta.batch` mirrors the top-level indicator functions (`pyta.batch.sma`, `pyta.batch.rsi`), with the same names and parameters. One call applies one indicator.
- `datasets` can be a **list** or a **mapping** (for example, ticker to data); anything else raises `TypeError`. Each dataset can be any supported container, and the result has the same shape and order as the input, with each result in its own input's container type. An empty list or mapping returns an empty one.
- `period` and `column` are shared by every dataset. An invalid `period` or `column` raises, because it affects the whole call.
- **A failure never cancels the others.** Each dataset gets a result. A dataset that fails is represented by the exception that explains why, in the same position or under the same key, so you can see which dataset failed and the reason. This covers malformed datasets (unsupported type, missing column, a `NaN` after the first valid value) as well as calculation errors (such as a period longer than the series). Fix the dataset and call again.

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
- **Explicit override.** `columns=[...]` names the columns to use. Names follow the same matching rules as `column=` (case, separators, aliases), and the order you list them in does not matter: PyTA assigns each name to the indicator's input slot for its role.

  ```python
  pyta.atr(df, period=14, columns=["high", "low", "adj close"])
  pyta.atr(df, period=14, columns=["adj close", "low", "high"])   # same result
  ```

  Each indicator defines its own slots and the roles each slot accepts (ATR's `close` slot takes `close` or `adj_close`). The call raises `ValueError`, naming what the indicator needs, when a name is not a recognized role, when two names fill the same slot, or when a slot is left empty or the count is wrong. If your columns have custom names, rename them first or use the plain `df`.
- **Unnamed inputs.** A 2-D array or a tuple of arrays has no names, so its columns are taken in the order documented for the indicator.
- `column=` is for single-column indicators and `columns=` for multi-column ones; passing the wrong one raises `ValueError`.

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

See the [README](../README.md#indicators) for implemented and planned indicators, and [`docs/indicators/`](indicators/) for one page per implemented indicator. Every indicator will follow the conventions in this document.
