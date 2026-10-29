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
| By category | `pyta.trend.sma(...)`, `pyta.momentum.rsi(...)` | Available |

```python
import pyta
from pyta.momentum import rsi

pyta.trend.sma(close, period=3)          # same function as pyta.sma
rsi(close, period=3)                     # same function as pyta.rsi
pyta.batch.trend.sma([close], period=3)  # same function as pyta.batch.sma
```

Both styles are the same function object (`pyta.trend.sma is pyta.sma`), so they give identical results; use whichever reads better. `import pyta` loads every namespace, and `import pyta.trend` or `from pyta.momentum import rsi` work on their own. The categories are `trend` and `momentum`; volatility, volume and valuation get their namespaces with their first indicator, and adding a category never changes an existing import.

Each indicator lives in its own module in a category subpackage, `pyta.indicators.<category>.<name>` (for example `pyta/indicators/trend/sma.py`, holding both the single call and the batch call). `pyta.indicators.sma` is the function, not the module; to reach the module itself use `from pyta.indicators.trend.sma import ...`. `pyta._native` is internal and not part of the API.

## 3. Indicators

| Function | Category | Signature |
|---|---|---|
| `sma` | Trend | `sma(data, period, *, column=None, output=None)` |
| `ema` | Trend | `ema(data, period=30, *, column=None, output=None)` |
| `macd` | Trend | `macd(data, fast=12, slow=26, signal=9, *, column=None, output=None)` |
| `rsi` | Momentum | `rsi(data, period=14, *, column=None, output=None)` |
| `cci` | Momentum | `cci(data, period=14, *, columns=None, output=None)` |

Each indicator has its own parameters, with TA-Lib's defaults where TA-Lib has one: `period` is required for `sma`; `macd` takes `fast`, `slow` and `signal` instead of `period`. Every parameter is an integer (NumPy integers too); out-of-range values raise `ValueError` and other types `TypeError`, naming the parameter. `column` selects a column for inputs that have columns (see [Column selection](#column-selection)); `None` means the indicator's default column, which is `close` for every single-column indicator so far. `cci` needs several columns, found by name, and takes `columns=` instead (see [Multi-column indicators](#10-multi-column-indicators)). `macd` returns three outputs (see [Multi-output indicators](#11-multi-output-indicators)). Every indicator takes `output=` to return another container than the input's (see [Output conversion](#output-conversion-output)). Each indicator has a page in the [indicator wiki](indicators/): [SMA](indicators/trend/sma.md), [EMA](indicators/trend/ema.md), [MACD](indicators/trend/macd.md), [RSI](indicators/momentum/rsi.md), [CCI](indicators/momentum/cci.md).

### SMA (Simple Moving Average)

Each value is the arithmetic mean of the current price and the preceding `period - 1` prices.

- The first `period - 1` results are `NaN` (warm-up).
- `period` must not exceed the series length.

### EMA (Exponential Moving Average)

Follows TA-Lib. The first value is the simple mean of the first `period` prices; after that `EMA = prev + k * (price - prev)` with `k = 2 / (period + 1)`.

- Needs at least `period` values. The first `period - 1` results are `NaN` (warm-up).
- `period=1` returns the input unchanged. The default `period` is 30, as in TA-Lib.

### MACD (Moving Average Convergence/Divergence)

Follows TA-Lib. `macd` is the `fast` EMA minus the `slow` EMA; both start at row `slow - 1`, the fast EMA seeded with the mean of the `fast` prices ending there. `macd_signal` is the `signal` EMA of `macd`, and `macd_hist = macd - macd_signal`.

- Needs at least `slow + signal - 1` values, so every output has at least one value.
- Each output has its own warm-up: `macd` has values from row `slow - 1`, `macd_signal` and `macd_hist` from row `slow + signal - 2`. (TA-Lib blanks all three until the signal exists; where TA-Lib has a value, PyTA's is the same.)
- `fast` and `slow` are at least 2 and `signal` at least 1, as in TA-Lib. If `slow` is less than `fast`, the two are swapped, as TA-Lib does, so the result is the one you meant; `fast == slow` gives `0` throughout.

### RSI (Relative Strength Index)

Uses Wilder's smoothing. The first average gain and loss are the simple means of the first `period` price changes; later values use `avg = (prev_avg * (period - 1) + current) / period`. `RSI = 100 * avg_gain / (avg_gain + avg_loss)`.

- Needs at least `period + 1` values. The first `period` results are `NaN` (warm-up).
- Flat prices give `0`; a series with no losses gives `100`; a series with no gains gives `0`.

### CCI (Commodity Channel Index)

Follows TA-Lib. The typical price is `TP = (high + low + close) / 3`; over each window of `period` rows, `CCI = (TP - mean(TP)) / (0.015 * mean_deviation(TP))`, where the mean deviation is the mean absolute distance from the window's mean.

- Needs at least `period` rows. The first `period - 1` results are `NaN` (warm-up).
- A flat window, or a latest typical price equal to the mean (within `1e-14` of the mean, as TA-Lib), gives `0`; `period=1` gives `0` throughout (TA-Lib rejects it).
- Inputs: high, low, and close (or else the adjusted close). Unnamed input is in that order.

## 4. Input containers

Every supported container is converted to one-dimensional `float64` series (one per input column the indicator needs), and the result is returned in the same kind of container. To get another container instead (DataFrame in, JSON out), pass `output=` ([Output conversion](#output-conversion-output)); the matrix below is the default, `output=None`.

### Container matrix

Columns are the indicator shapes: one input column and one output (SMA, EMA, RSI), one column and several outputs (MACD), several columns and one output (CCI), and several of both (none yet; Stochastic in Sprint 11.5, tested now with a stand-in). "Same" means the same container as the input; "tuple of outputs" means one item per output, in documented order, each in the single-output form. Values always equal the plain NumPy-array call exactly.

| Input | One column, one output | One column, several outputs | Several columns, one output | Several columns, several outputs |
|---|---|---|---|---|
| `list` of numbers | `list` | tuple of lists | `TypeError` (one series) | `TypeError` (one series) |
| `list` of rows or of column lists (or arrays) | `ValueError` (expects a flat list) | `ValueError` (expects a flat list) | `list`; layout as for a 2-D array | tuple of lists |
| `tuple` of numbers | `tuple` | tuple of tuples | `TypeError` (one series) | `TypeError` (one series) |
| NumPy 1-D array (any real numeric dtype, masked) | `float64` array | tuple of arrays | `TypeError` (one series) | `TypeError` (one series) |
| NumPy 2-D array `(rows, columns)` or `(columns, rows)` | `ValueError` (expects 1-D) | `ValueError` (expects 1-D) | 1-D array; columns in documented order, the axis of the column count is the columns (both: `(rows, columns)`) | tuple of 1-D arrays |
| `tuple` of arrays or lists (one per column) | `ValueError` (expects 1-D) | `ValueError` (expects 1-D) | `tuple` | tuple of tuples |
| pandas Series | Series named by the output, same index | tuple of Series, same index | `TypeError` (one series) | `TypeError` (one series) |
| `list` or `tuple` of pandas Series (one shared index) | `ValueError` (expects a flat list) | `ValueError` (expects a flat list) | Series named by the output, same index; matched by name when every Series is named by a role, else documented order | tuple of Series, same index |
| pandas DataFrame | DataFrame, one column, same index | DataFrame, one column per output | DataFrame, one column | DataFrame, one column per output |
| `dict` of columns (list, tuple, array or Series values) | `dict`, one key | `dict`, one key per output | `dict`, one key | `dict`, one key per output |
| JSON array of numbers (`str`, `bytes`, `bytearray`) | JSON array | JSON object keyed by output | `TypeError` (one series) | `TypeError` (one series) |
| JSON array of arrays (rows or columns) | `ValueError` (expects numbers) | `ValueError` (expects numbers) | JSON array; layout as for a 2-D array | JSON object keyed by output |
| JSON array of records | records, one key per output | records, one key per output | records | records |
| JSON object of arrays | object, one key per output | object, one key per output | object | object |
| CSV with a header row (`str`, `bytes`, `bytearray`) | CSV, one column | CSV, one column per output | CSV, one column | CSV, one column per output |
| anything else (sets, scalars, generators, ...) | `TypeError` | `TypeError` | `TypeError` | `TypeError` |

Text (`str`, `bytes`, `bytearray`) is JSON when its first non-whitespace character is `[` or `{`, and CSV otherwise. JSON and CSV results have the input's type: `str` stays `str`, and `bytes` or `bytearray` become `bytes`. A pandas index (default, date, datetime, time-zone aware, non-unique, MultiIndex rows) is kept with its name and order. A dict's values take the container type of the column used (for a multi-column indicator, its first input column), so a Series value keeps its index only when that column is a Series.

**Limitations** (each raises, never guesses):

- A `(rows, 1)` array or a one-item tuple is not taken as one series; pass the column itself.
- A 2-D table (array, list of lists, JSON array of arrays) with as many rows as columns is read as `(rows, columns)`; neither axis matching the column count raises `ValueError`. A tuple is always a tuple of columns, never of rows.
- DataFrames with MultiIndex columns are not supported; select a single column level first.
- Only leading gaps are skipped: a gap (`None`, `null`, `NaN`, `pd.NA`) after the first value raises `ValueError` ([§6](#6-missing-and-non-finite-values)).
- In a Python list or JSON array, `True` and `False` among numbers are read as 1 and 0 (NumPy's conversion; rejecting them would mean scanning every list); a list, array or Series of only booleans, or a boolean among strings, raises `TypeError`.
- CSV needs a header row, uses `,` as its only delimiter, and must be UTF-8 when given as bytes. A first line of only numbers (or blanks) is taken as a missing header and raises `ValueError`, so name the columns even in a one-column file.
- Provider-specific layouts are not unpacked: AlphaVantage's nested JSON time series is not supported; use its CSV, or flatten the JSON first ([§12](#12-data-sources)).

Details:

- **Output names** are the indicator's name without its parameters (`sma`, `rsi`, `ema`, `cci`), with casing that follows the input's columns: `sma` for `close`, `SMA` for `CLOSE` or `Close` (see [§11](#11-multi-output-indicators) for the rule). To keep two runs of one indicator side by side (SMA 20 and SMA 50), rename one of them.
- **Dict values** may be lists, tuples, NumPy arrays, or pandas Series.
- **JSON** may be an array of numbers, an array of records (`[{"close": 1.0}, ...]`), or an object of arrays (`{"close": [1.0, ...]}`). Results use the same shape. `NaN` is written as `null`.
- **CSV** needs a header row naming the columns (`timestamp,open,high,low,close,volume`); columns are picked as for a dict, and only the columns used are read, so a date or text column is never parsed. Quoted fields, `\r\n` line endings and a UTF-8 byte-order mark are accepted; a row with more or fewer fields than the header raises `ValueError`. The result is CSV with a header of the output names and one row per input row (the input's other columns are not repeated, as for JSON records): `NaN` is an empty field, numbers are written as Python's shortest round-trip form (`repr`), and lines end with `\n`. A one-column result can be passed straight to the next indicator.
- **Numbers as strings** (`"187.15"`, `" 1e3 "`) are read as numbers in every container: CSV fields, lists, tuples, dict values, JSON, NumPy string arrays, and pandas `object` or string columns (so a DataFrame built from text works). Surrounding whitespace is ignored, and an empty string or `NaN` text is a gap. Any other text, or a boolean among strings, raises `TypeError` naming the column (when the input has names) and the index: `column 'close' value 'abc' at index 3 is not a number`.
- **pandas** is optional. PyTA only recognizes pandas objects when pandas has been imported by your program. DataFrames with MultiIndex columns are not supported; select a single column first.
- **Masked arrays** are accepted; masked values become `NaN`.
- **Input is never modified.**

### Column selection

For DataFrame, dict, JSON-object or record, and CSV input, PyTA picks the column to use:

1. If you pass `column=`, that column is used. The name must be a standard column name (see the table below), so code reads the same on every data source; any other name raises `ValueError`, and so does a standard name the input does not have.
2. Otherwise, if there is only one column, it is used.
3. Otherwise PyTA looks for the indicator's **default column**. `sma` and `rsi` default to `close`; an indicator that works on something else (for example a volume average) declares its own default.

Names ignore case, whitespace, and the separators `.`, `_` and `-`, so `" Close "`, `"Adj_Close"` and `"adj.close"` all match as written. A leading number and dot before a letter is ignored too (AlphaVantage numbers its fields), so `"1. open"` matches `open` and `"5. adjusted close"` matches `adj_close`, in every container and in `column=` and `columns=`; output casing still reads the name as written (`"4. Close"` gives `SMA`). A name also matches the aliases of its column role:

| Role | Names that match |
|---|---|
| `open` | `open`, `opening`, `open_price`, `opening_price`, `o` |
| `high` | `high`, `highest`, `high_price`, `highest_price`, `h` |
| `low` | `low`, `lowest`, `low_price`, `lowest_price`, `l` |
| `close` | `close`, `closing`, `close_price`, `closing_price`, `c` |
| `adj_close` | `adj_close`, `adjusted_close`, `adj_close_price`, `adjusted_close_price`, `adj_closing`, `adjusted_closing` (any spelling of the separators, such as `Adj Close`) |
| `volume` | `volume`, `volumes`, `vol`, `v` |

A role matches only its own aliases: asking for `close` never falls back to the adjusted close, and a column named exactly as you wrote it wins over an alias. Two names that are identical after this normalization (for example `"Adj_Close"` and `"adj close"`, or `"1. open"` and `"open"`) are rejected as ambiguous. The input's own columns may be named anything; only the name you ask for is restricted. If your columns use other names, rename them first (`df.rename(columns={"px": "close"})`). An input with a single column needs no `column=` at all, which is what lets one indicator's output feed the next. Passing `column=` with input that has no columns (list, tuple, array, Series, JSON array of numbers) raises `ValueError`.

```python
pyta.sma(df, period=20)                          # the "close" column
pyta.sma(df, period=20, column="open")           # the "open" column
pyta.sma(df, period=20, column="adjusted close") # the "Adj Close" column
```

## 5. Output conventions

- Results are `float64` and the same length as the input.
- Warm-up positions are `NaN` (`null` in JSON).
- A pandas result keeps the input's index; positions are never reordered.
- Outputs are named after the indicator, without parameters (`sma`, not `sma_20`); a multi-output indicator names each output `<indicator>_<part>` after the main one (`macd`, `macd_signal`, `macd_hist`). The casing follows the input's columns ([§11](#11-multi-output-indicators)).

### Output conversion (`output=`)

By default (`output=None`) the result comes back in the input's own container ([§4](#4-input-containers)). `output=` converts it to another one, from any supported input, for every indicator, single and batch:

```python
pyta.sma(df, period=20, output="json")      # DataFrame in, JSON text out
pyta.macd(csv_text, output="pandas")        # CSV in, a DataFrame of three columns out
pyta.cci(ohlcv_dict, period=20, output="numpy")
```

The valid names are the type `pyta.Output` (a `Literal`), for annotating your own code: `fmt: pyta.Output = "csv"`.

Each target has one fixed shape, whatever the input was, so asking for the input's own kind still gives the target's shape (`output="dict"` always holds NumPy arrays, even for a dict of lists; `output="json"` is always an object of arrays, even for JSON records):

| `output=` | One output | Several outputs | Input's pandas index |
|---|---|---|---|
| `None` (default) | the input's container ([§4](#4-input-containers)) | as in [§4](#4-input-containers) | kept by pandas results |
| `"list"` | `list` of floats | tuple of lists | dropped |
| `"tuple"` | `tuple` of floats | tuple of tuples | dropped |
| `"numpy"` | `float64` array | tuple of arrays | dropped |
| `"pandas"` | Series named by the output | DataFrame, one column per output | the index (a default `RangeIndex` without one) |
| `"dict"` | `{name: array}` | one key per output, NumPy array values | a key placed first, NumPy array of its values |
| `"json"`, `"json_bytes"` | object of arrays, `str` or `bytes` | one key per output | a field placed first |
| `"csv"`, `"csv_bytes"` | header row, then one row per input row, `str` or `bytes` | one column per output | the first column |

- **Names and casing** are those of the default output (`SMA` for a yfinance `Close` column, `MACD_Signal`, ...).
- **Values** equal the default call's exactly. JSON writes `NaN` as `null`; CSV writes it as an empty field, numbers in Python's shortest round-trip form (`repr`), and ends lines with `\n`, as for CSV input ([§4](#4-input-containers)).
- **The index** comes from a pandas input: a Series or DataFrame, a list or tuple of Series, or a dict whose column used (a multi-column indicator's first input column) is a Series. JSON, CSV, lists and arrays have no index, so their results have none. The index field is named after the index, or `index` when it has no name; a MultiIndex gives one field per level, named after the level or `level_0`, `level_1`, ... (as pandas' `reset_index` names them), and is kept whole by `"pandas"`. An index name equal to an output name raises `ValueError`; rename the index (`rename_axis`).
- **Dates in JSON and CSV** become ISO 8601 strings: an index whose values are all tz-naive midnights is written as dates (`2024-01-02`), any other as timestamps (`2024-01-02T09:30:00`, with the offset when tz-aware: `2024-01-02T09:30:00-05:00`). Python `date` and `datetime` values are written the same way; `NaT` and missing values are `null` or an empty field. Other index values must be numbers or strings (CSV quotes a string holding `,`, `"` or a line break); anything else (`Period`, `Timedelta`, tuples, infinite floats) raises `TypeError` naming the value and position. `"pandas"` and `"dict"` keep any index as it is.
- **pandas is imported only for `output="pandas"`**, when the call is made (`import pyta` never imports it). Without pandas installed it raises `ModuleNotFoundError` saying to install the `pandas` extra (`pip install 'pyta[pandas]'`).
- **An invalid name** (anything but `None` or the names above, including `"JSON"`) raises `ValueError` listing the valid ones, before any data is read.
- **Batch:** one `output=` applies to every dataset ([§9](#9-batch-calculation)).

## 6. Missing and non-finite values

| Input value | Behavior |
|---|---|
| `None` (list) or `null` (JSON) | Treated as a gap (`NaN`) |
| Empty CSV field, empty string, or `NaN` / `nan` text (CSV, or a string in any container) | Treated as a gap (`NaN`) |
| Leading `NaN` | Skipped, then re-padded as `NaN` in the output |
| `NaN` after the first valid value | `ValueError`, naming the index |
| `inf` / `-inf` | `ValueError`, naming the index |
| Finite value larger in magnitude than `1e290` | `ValueError`, naming the index |
| Empty input, or only `NaN` | `ValueError` |

The `1e290` limit keeps every intermediate sum finite: near `float64`'s maximum (about `1.8e308`), a window sum or a price change could overflow and turn a valid result into `inf` or `NaN`. With the limit, `NaN` in a result only ever marks a warm-up position. Market data is many orders of magnitude below it.

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

>>> pyta.cci(df, period=20)   # df has date, open, high, close, volume
ValueError: cci needs the columns high, low and close (close or adj_close); missing: low. Available columns: 'date', 'open', 'high', 'close', 'volume'. Rename the input's columns, or pass columns=[...] to choose them

>>> pyta.sma([1.0, 2.0, 3.0], period=0)
ValueError: period must be between 1 and 2147483647, got 0

>>> pyta.sma([1.0, 2.0, 3.0], period="14")
TypeError: period must be an integer, got str

>>> pyta.macd(close, fast=1)
ValueError: fast must be between 2 and 2147483647, got 1
```

The examples show the current wording, which may change between releases, so catch the exception type rather than matching message text.

| Exception | Raised for |
|---|---|
| `TypeError` | Unsupported container or dtype (booleans, complex numbers, dates), text that is not a number (naming the column and index), DataFrames with MultiIndex columns, non-integer `period`, `fast`, `slow` or `signal` (including `bool`), non-string `column`, `columns` that is not a list of strings, JSON of the wrong shape (including arrays that mix records and numbers), one series (list, 1-D array, Series) given to a multi-column indicator, an index value that JSON or CSV cannot hold (`output=`) |
| `ValueError` | An unknown `output=` name, an index named like an output (`output=` with an index), `period` or `signal` outside `1` to `2**31 - 1`, `fast` or `slow` outside `2` to `2**31 - 1`, period larger than the series (`sma`) or fewer than `period` values (`ema`), `period + 1` values (`rsi`), `period` rows (`cci`) or `slow + signal - 1` values (`macd`), empty input or input with no valid values, a non-finite value after the first valid value, a value larger in magnitude than `1e290`, multidimensional or ragged input, invalid JSON, CSV without a header row or with a row of the wrong field count (or bytes that are not UTF-8), a missing or ambiguous column, `column=` on input without columns; for multi-column indicators: an invalid `columns=` (see [§10](#10-multi-column-indicators)), columns of different lengths, a high below its low on any row, the wrong number of unnamed columns (or a 2-D table with neither axis of that length), Series that do not share one index, and `column=` on a multi-column indicator or `columns=` on a single-column one |
| `ModuleNotFoundError` | `output="pandas"` without pandas installed |
| `RuntimeError` | An internal calculation failure |

NumPy integers are accepted for every integer parameter.

## 8. Calling from async code

PyTA's functions are ordinary synchronous calls. The native boundary releases the GIL while Rust calculates, so other Python threads keep running. A Python-level async API is not planned for now.

---

## 9. Batch calculation

Apply one indicator to many datasets in a single call. The engine decides internally whether to run them sequentially or concurrently.

```python
results = pyta.batch.sma(datasets, period=14)
```

- `pyta.batch` mirrors the top-level indicator functions (`pyta.batch.sma`, `pyta.batch.ema`, `pyta.batch.macd`, `pyta.batch.rsi`, `pyta.batch.cci`), with the same names and parameters, and the category namespaces too (`pyta.batch.trend.sma is pyta.batch.sma`). One call applies one indicator.
- `datasets` can be a **list** or a **mapping** (for example, ticker to data); anything else raises `TypeError`. Each dataset can be any supported container, and the result has the same shape and order as the input, with each result in its own input's container type (for MACD, the three outputs in the form a single call returns them). Output names are cased per dataset, from that dataset's own columns. An empty list or mapping returns an empty one.
- The indicator's parameters (`period`; `fast`, `slow`, `signal`), `column` and `output` are shared by every dataset. An invalid one raises, because it affects the whole call.
- With `output=` ([Output conversion](#output-conversion-output)), every dataset's result is in that target's shape (`pyta.batch.sma(frames, period=20, output="json")` gives a list of JSON strings). A dataset whose result cannot be converted (an index JSON cannot hold) gets its exception in place, like any other failure.
- **A failure never cancels the others.** Each dataset gets a result. A dataset that fails is represented by the exception that explains why, in the same position or under the same key, so you can see which dataset failed and the reason. This covers malformed datasets (unsupported type, missing column, a `NaN` after the first valid value) as well as calculation errors (such as a period longer than the series). Fix the dataset and call again.

```python
results = pyta.batch.sma({"AAPL": aapl, "MSFT": msft}, period=14)

for ticker, result in results.items():
    if isinstance(result, Exception):
        print(f"{ticker} failed: {result}")
```

## 10. Multi-column indicators

Some indicators need more than one column (for example CCI needs high, low, and close). Pass your OHLCV data in any named container (DataFrame, dict of columns, JSON array of records or object of arrays); PyTA finds the columns the indicator needs and returns the same kind of container.

```python
cci = pyta.cci(df, period=20)   # a DataFrame with one column, "cci" ("CCI" for yfinance's "High", "Low", "Close")
```

- **Automatic selection.** PyTA matches column names to the roles an indicator needs, with the same rules as `column=` (case, whitespace, and `. _ -` ignored; aliases such as `h` or `adjusted close`). If you pass more columns than needed (for example all of date, open, high, low, close, and volume), the extras are ignored, whatever they hold.
- **Explicit override.** `columns=[...]` names the columns to use, and the order you list them in does not matter: PyTA assigns each name to the indicator's input slot for its role.

  ```python
  pyta.cci(df, period=20, columns=["high", "low", "adj close"])
  pyta.cci(df, period=20, columns=["adj close", "low", "high"])   # same result
  ```

  Each indicator defines its own slots and the roles each slot accepts (CCI's `close` slot takes `close`, or else `adj_close`). The call raises `ValueError`, naming what the indicator needs, when a name is not a recognized role, when its role is not one of the indicator's inputs, when two names fill the same slot, when a slot is left empty, or when a name is not in the input. If your columns have custom names, rename them first.
- **Unnamed inputs.** These have no column names, so their columns are taken in the order documented for the indicator (high, low, close for CCI), and `columns=` raises `ValueError`:
  - a 2-D NumPy array, a list of rows (`[[h, l, c], ...]`) or of column lists (`[highs, lows, closes]`), or a JSON array of arrays (rows or columns). The axis whose length equals the indicator's column count holds the columns; when both do (as many rows as columns), `(rows, columns)` is assumed. When neither does, `ValueError` names the shape expected: `(rows, 3)` or `(3, rows)` for CCI;
  - a tuple of arrays or lists, one per column; the count must match.

  A 2-D array returns a 1-D array, a list a `list`, a tuple a `tuple`, and a JSON array a JSON array (several outputs: a tuple of them, or a JSON object keyed by output name). A single series (a flat list, a 1-D array, a pandas Series) raises `TypeError`.
- **Lists and tuples of pandas Series.** When every Series is named by a role (`High`, `low`, `adj close`), they are matched by name like a dict, and `columns=` works; otherwise they are taken in the documented order and the count must match. All must share one index (`Index.equals`), else `ValueError` naming the first that differs; align them first, for example with `pandas.concat(..., axis=1)`. The result is a Series named by the output with that index (several outputs: a tuple of Series).
- `column=` is for single-column indicators and `columns=` for multi-column ones; passing the wrong one raises `ValueError`.
- **Missing data.** If a required column can't be found, a `ValueError` names what the indicator requires and which columns were available, so you don't have to know in advance what an indicator needs:

  ```text
  ValueError: cci needs the columns high, low and close (close or adj_close); missing: low. Available columns: 'date', 'open', 'high', 'close', 'volume'. ...
  ```

- **Leading NaN.** Rows up to the last leading `NaN` of any needed column are skipped and re-padded with `NaN`, so outputs of other indicators (each with its own warm-up) can be combined. `NaN` or `inf` after that raises `ValueError` naming the column and the row.
- **Row checks.** A high below its low on any row raises `ValueError` naming both columns and the row (equal is fine).
- **Results.** A DataFrame result keeps the input's index; a dict result keeps the container type of the indicator's first input column. Output names are cased from the columns used ([§11](#11-multi-output-indicators)); unnamed input gives lower case.
- **Batch.** `pyta.batch.cci(datasets, period, columns=None)` works as in [§9](#9-batch-calculation); `columns=` applies to every dataset, and a dataset with a missing column is returned as its `ValueError` in place.
- Each indicator's documentation lists its required inputs and their order for unnamed input.

## 11. Multi-output indicators

Indicators that produce several series return them all, in a documented order, in the input's container type.

| Indicator | Outputs, in order | Parameters |
|---|---|---|
| MACD | `macd`, `macd_signal`, `macd_hist` | `fast=12`, `slow=26`, `signal=9` |

```python
out = pyta.macd(df)                      # DataFrame with columns macd, macd_signal, macd_hist
macd, signal, hist = pyta.macd(close)    # one series in: a tuple of three, in order
```

| Input | Result |
|---|---|
| pandas DataFrame | DataFrame with one column per output, same index |
| `dict` of columns | `dict` with one key per output; each value keeps the input column's container type |
| JSON array of records | each record holds every output name |
| JSON object of arrays | one key per output |
| `list`, `tuple`, NumPy array, pandas Series | a `tuple` of outputs in documented order, each in the input's own single-output form (a Series is named by its output and keeps the index) |
| JSON array of numbers | a JSON object keyed by output name |
| 2-D array, list of rows or columns, tuple of arrays, list or tuple of Series (multi-column indicators) | a `tuple` of outputs, each a 1-D array, a list, a tuple or a Series |
| JSON array of arrays (multi-column indicators) | a JSON object keyed by output name |

`NaN` is written as `null` in JSON. Each output has its own warm-up, and a leading `NaN` run in the input shifts every output alike. A single-output indicator returns exactly what the [§4](#4-input-containers) table says. To chain from a multi-output result, pass the output itself (`pyta.sma(out["macd_signal"], period=5)`); `column=` takes only the standard role names.

**Names and casing.** Output names never include parameters: the main output is the indicator's name and the others are `<indicator>_<part>`. Their casing follows the input column names the call used (the picked column of a DataFrame, dict or JSON; the name of a Series; every column a multi-column indicator matched):

| Input columns | Casing | Example names |
|---|---|---|
| no upper-case letters (`close`) | lower | `sma`, `macd_signal` |
| no lower-case letters (`CLOSE`) | upper | `SMA`, `MACD_SIGNAL` |
| some lower-case letters, and each word either a capital then no other capitals or all capitals (`Close`, `Adj Close` as yfinance; `SPY Close`; PyTA's own `MACD_Signal`) | title | `SMA`, `MACD_Signal`, `MACD_Hist` |
| mixed (`cLose`, `ClosePrice`), columns that disagree, or no names (lists, arrays, unnamed Series, JSON arrays of numbers or arrays, unnamed 2-D input, Series not all named by role) | lower | `sma`, `macd_signal` |

In title case, abbreviations (`SMA`, `EMA`, `RSI`, `CCI`, `MACD`) are upper case and words (`Signal`, `Hist`) title case. The separator is always `_`. Because a word in capitals counts as title case, title-case outputs chain as title case: `pyta.sma(pyta.macd(yf_frame)["MACD_Signal"], 5)` is named `SMA`. A name that is not a string is cased by its `str()`.

## 12. Data sources

PyTA does not depend on any data provider. It accepts the data types that providers return:

| Provider | Returns | Support |
|---|---|---|
| yFinance | pandas DataFrame or Series, tuple, dict | Available (single-level columns) |
| AlphaVantage | JSON, CSV | CSV available (`datatype=csv`); its nested JSON time series is not supported |

AlphaVantage's CSV (`timestamp,open,high,low,close,volume`) works as it comes, for single- and multi-column indicators. AlphaVantage sends the newest row first, and PyTA never reorders rows, so reverse the rows first for the usual oldest-first calculation:

```python
header, *rows = text.splitlines()
pyta.sma("\n".join([header, *reversed(rows)]), period=20)
```

Its JSON nests each day's values under the date (`{"Time Series (Daily)": {"2024-01-02": {"1. open": "187.15", ...}}}`), which PyTA does not unpack: flatten it into records or a DataFrame first. Its numbered, string-valued fields then work as they are ([§4](#4-input-containers)).

## 13. Indicator catalog

Available: SMA, EMA and MACD (trend); RSI and CCI (momentum). See the [README](../README.md#indicators) for implemented and planned indicators, and [`docs/indicators/`](indicators/) for one page per implemented indicator. Every indicator will follow the conventions in this document.

## 14. Logging

PyTA logs through Python's standard `logging`, including the messages from its Rust engine, so one configuration controls both. The library is silent until you configure logging: it adds only a `NullHandler` to the `pyta` logger and never sets levels or handlers.

```python
import logging, pyta
logging.basicConfig(level=logging.WARNING)
logging.getLogger("pyta").setLevel(logging.DEBUG)   # show PyTA's DEBUG records
```

| Logger | Language | Records |
|---|---|---|
| `pyta.api` | Python | DEBUG: each failed dataset in a batch, with its key or index and the reason. WARNING: one summary per batch with failures ("2 of 3 datasets failed") |
| `pyta.validation` | Python | DEBUG: which column was chosen for a role (`using column 'Adj Close' for 'adjusted close'`) |
| `pyta.planner` | Rust | DEBUG: each batch's scheduling choice, with request count, workers, and estimated sequential and parallel times |
| `pyta.bridge` | Rust | DEBUG: the worker pool starting, and being rebuilt in a forked child |
| `pyta.engine` | Rust | ERROR: a calculation that panicked (a bug; the call fails with `RuntimeError`) |

There is no INFO output in normal operation. Single calls log nothing from Rust. Rust records carry their Rust file and line (`record.filename == "planner.rs"`). Level changes take effect on the next batch call.
