# PyTA

High-performance technical analysis indicators for Python, powered by Rust.

> [!WARNING]
> **PyTA is in active development and is not ready for use.** APIs, behavior, and project structure will change without notice, and the package has not been published to PyPI. Do not use it in production or depend on it in your projects yet.

## Overview

PyTA is a drop-in replacement for [TA-Lib](https://ta-lib.org/) in spirit: a complete technical-analysis toolkit that is easy to install and easy to use. TA-Lib depends on a C library that must be compiled, and that build often fails. PyTA aims to remove that friction, so installing it is a single `pip install` and no compiler is required.

- **Rust core.** Every indicator calculation is implemented in Rust for speed and numerical consistency.
- **Concurrency under the hood.** Calculations run on a Rust execution engine that schedules work concurrently. You don't need `asyncio` or threading in your own code.
- **Works with your data.** Pass a list, tuple, NumPy array, pandas Series or DataFrame, dictionary, or JSON, and get the same kind of container back.
- **Consistent conventions.** Every indicator returns full-length output with `NaN` warm-up values, and indicators can be chained.

## Requirements

- Python 3.15 or later
- [NumPy](https://numpy.org/) and [Pydantic](https://docs.pydantic.dev/) (installed automatically)
- [pandas](https://pandas.pydata.org/) is optional (`pyta[pandas]`)

## Installation

PyTA will be published to PyPI once the major indicators are complete and stable. Until then it can only be built from source, which requires Rust 1.99.1 or later and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/saviornt/PyTA2
cd PyTA2
uv run maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml
```

## Usage

```python
import numpy as np
import pyta

close = np.array([10.0, 11.0, 12.0, 13.0, 12.0, 14.0])

sma = pyta.sma(close, period=3)
rsi = pyta.rsi(close, period=3)
rsi = pyta.momentum.rsi(close, period=3)  # by category: the same function as pyta.rsi
```

Outputs have the same length as the input, with `NaN` for the warm-up period. Indicators accept the same container types as inputs and can be chained:

```python
smoothed_rsi = pyta.sma(pyta.rsi(close, period=14), period=5)
```

With a pandas DataFrame, an indicator uses its default column (`close` for SMA, EMA, MACD and RSI). Names ignore case, whitespace and `. _ -`, and common aliases match (`Adj Close`, `adjusted_close`, `Vol`, `o`/`h`/`l`/`c`). Use `column=` to pick another. Output names are the indicator's name, cased like your columns (`sma` for `close`, `SMA` for yfinance's `Close`):

```python
result = pyta.sma(df, period=20)                  # DataFrame with an "sma" column
result = pyta.sma(df, period=20, column="open")
result = pyta.sma(df, period=20, column="adj close")
```

Indicators that need several columns find them by name, so a full OHLCV DataFrame (dates and all) works as it is; `columns=[...]` picks them yourself, in any order:

```python
result = pyta.cci(df, period=20)                                    # high, low and close found by name
result = pyta.cci(df, period=20, columns=["adj close", "low", "high"])
```

Indicators with several outputs return one column per output, or a tuple for a single series:

```python
result = pyta.macd(df)                         # columns macd, macd_signal, macd_hist
macd, signal, hist = pyta.macd(close, fast=12, slow=26, signal=9)
```

Results come back in the input's container unless you ask for another with `output=` (`"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"`, `"csv_bytes"`); a DataFrame's index goes along to the named targets, with dates as ISO 8601 in JSON and CSV (see [Output conversion](docs/API.md#output-conversion-output)):

```python
text = pyta.sma(df, period=20, output="json")  # '{"Date":["2024-01-02",...],"SMA":[null,...]}'
```

PyTA logs through Python's standard `logging` (Rust messages included) under the `pyta` logger and is silent unless you configure logging. For example, `logging.getLogger("pyta").setLevel(logging.DEBUG)` shows how batches are scheduled; see [Logging](docs/API.md#14-logging).

## Indicators

### Available

| Category | Indicator |
|---|---|
| Trend | [Simple Moving Average](docs/indicators/trend/sma.md) (`sma`) |
| Trend | [Exponential Moving Average](docs/indicators/trend/ema.md) (`ema`, TA-Lib seeding) |
| Trend | [Weighted Moving Average](docs/indicators/trend/wma.md) (`wma`, linear weights 1 to `period`) |
| Trend | [Double Exponential Moving Average](docs/indicators/trend/dema.md) (`dema`, Mulloy: `2 × EMA − EMA of EMA`) |
| Trend | [Triple Exponential Moving Average](docs/indicators/trend/tema.md) (`tema`, Mulloy: `3 × EMA1 − 3 × EMA2 + EMA3`) |
| Trend | [Kaufman Adaptive Moving Average](docs/indicators/trend/kama.md) (`kama`, an EMA whose weight follows the efficiency ratio) |
| Trend | [Moving Average Convergence/Divergence](docs/indicators/trend/macd.md) (`macd`, three outputs) |
| Trend | [Average Directional Index](docs/indicators/trend/adx.md) (`adx`, high, low and close; Wilder's ADX with +DI and -DI; three outputs) |
| Trend | [Parabolic SAR](docs/indicators/trend/sar.md) (`sar`, high and low; Wilder's stop and reverse, TA-Lib's first direction) |
| Trend | [Aroon](docs/indicators/trend/aroon.md) (`aroon`, high and low; Chande's Aroon Up, Aroon Down and Aroon Oscillator; three outputs) |
| Trend | [Ichimoku Cloud](docs/indicators/trend/ichimoku.md) (`ichimoku`, high, low and close; Hosoda's five lines, unshifted by default or displaced for charting with `shift=True`; five outputs) |
| Momentum | [Relative Strength Index](docs/indicators/momentum/rsi.md) (`rsi`, Wilder's smoothing) |
| Momentum | [Commodity Channel Index](docs/indicators/momentum/cci.md) (`cci`, high, low and close) |
| Momentum | [Stochastic Oscillator](docs/indicators/momentum/stoch.md) (`stoch`, high, low and close; Lane's full stochastic, %K and %D; two outputs) |
| Momentum | [Williams %R](docs/indicators/momentum/willr.md) (`willr`, high, low and close; from -100 to 0) |
| Momentum | [Rate of Change](docs/indicators/momentum/roc.md) (`roc`, percentage change over `period` rows) |
| Momentum | [Money Flow Index](docs/indicators/momentum/mfi.md) (`mfi`, high, low, close and volume; volume-weighted, from 0 to 100) |
| Momentum | [TRIX](docs/indicators/momentum/trix.md) (`trix`, one-bar rate of change of a triple EMA) |
| Momentum | [Ultimate Oscillator](docs/indicators/momentum/ultosc.md) (`ultosc`, high, low and close; buying pressure over true range in three windows) |
| Volatility | [Average True Range](docs/indicators/volatility/atr.md) (`atr`, high, low and close; Wilder's smoothing) |
| Volatility | [Standard Deviation](docs/indicators/volatility/stddev.md) (`stddev`, population, times `k`) |
| Volatility | [Bollinger Bands](docs/indicators/volatility/bbands.md) (`bbands`, SMA ± `k` population standard deviations; three outputs) |
| Volatility | [Donchian Channels](docs/indicators/volatility/donchian.md) (`donchian`, high and low; highest high and lowest low, current row included; three outputs) |
| Volatility | [Keltner Channels](docs/indicators/volatility/keltner.md) (`keltner`, high, low and close; EMA ± `k` Wilder ATRs; three outputs) |
| Volume | [On-Balance Volume](docs/indicators/volume/obv.md) (`obv`, close and volume; Granville's running total of signed volume) |
| Volume | [Accumulation/Distribution](docs/indicators/volume/ad.md) (`ad`, high, low, close and volume; Chaikin's running total of volume weighted by the close's place in the bar) |
| Volume | [Chaikin Money Flow](docs/indicators/volume/cmf.md) (`cmf`, high, low, close and volume; A/D's money-flow volume over volume in a window, from -1 to 1) |
| Volume | [Volume-Weighted Average Price](docs/indicators/volume/vwap.md) (`vwap`, high, low, close and volume; typical price weighted by volume, cumulative from the first row) |
| Volume | [Volume Rate of Change](docs/indicators/volume/vroc.md) (`vroc`, the volume column; percentage change over `period` rows) |

### Planned

The catalog below is the planned scope and is subject to change.

**Valuation Indicators**
Mayer Multiple, Z-Score, P/E(TTM), Earnings Yield, P/B, P/S, Dividend Yield, EV/EBITDA, PEG
*Future*: DCF, DDM, Residual Income, Justified P/E, Comparables, CAPE


## Performance against TA-Lib

Measured 2026-10-30 with `PyTA-Integration/benchmarks/compare_talib.py` (PyTA 0.2.0 release wheel, TA-Lib 0.8.3 from PyPI, Python 3.15, Intel i9-9900K, Linux, CPU governor `performance`). Each library is called as its documentation shows and the whole call is timed with `timeit` (best of 5, the libraries alternating) on a seeded random walk. Cells are **TA-Lib time / PyTA time**: above 1.00x PyTA is faster, below it TA-Lib is. Outputs agree to within 8.7e-12 relative everywhere. Full timings in µs: [`docs/benchmarks/talib_comparison_2026-10-30.md`](docs/benchmarks/talib_comparison_2026-10-30.md).

**Today TA-Lib is faster in most cases.** PyTA's per-call Python layer (validation, container handling) costs a few µs on NumPy and ~100 µs or more on a DataFrame, which dominates small inputs and many-small-dataset batches; at 1,000,000 rows most PyTA kernels plus the copy into Rust are still slower than TA-Lib's. PyTA wins on large batches of NumPy data (`pyta.batch` runs datasets in parallel: faster in 14 of 23 indicators at 100 x 10,000) and on three kernels (ADX, Aroon and CCI at 10,000 rows and more). Closing this gap is the next performance work.

Indicators with no TA-Lib function (`ichimoku`, `keltner`, `donchian`, `cmf`, `vwap`, `vroc`) are not compared.

### Single indicator (one dataset per call, rows)

| Indicator | 100 (NumPy) | 10,000 (NumPy) | 1,000,000 (NumPy) | 100 (DataFrame) | 10,000 (DataFrame) | 1,000,000 (DataFrame) |
|---|---:|---:|---:|---:|---:|---:|
| `sma` | 0.45x | 0.72x | 0.62x | 0.15x | 0.28x | 1.01x |
| `ema` | 0.43x | 0.31x | 0.25x | 0.15x | 0.21x | 0.70x |
| `wma` | 0.46x | 0.71x | 0.60x | 0.15x | 0.29x | 0.88x |
| `dema` | 0.44x | 0.35x | 0.30x | 0.15x | 0.22x | 0.67x |
| `tema` | 0.47x | 0.39x | 0.34x | 0.15x | 0.24x | 0.72x |
| `kama` | 0.45x | 0.66x | 0.58x | 0.15x | 0.31x | 0.80x |
| `macd` | 0.50x | 0.31x | 0.33x | 0.26x | 0.32x | 0.68x |
| `sar` | 0.17x | 0.53x | 0.55x | 0.12x | 0.30x | 0.72x |
| `adx` | 0.44x | 1.40x | 1.20x | 0.31x | 0.80x | 1.56x |
| `aroon` | 0.34x | 1.76x | 1.57x | 0.29x | 0.97x | 1.63x |
| `rsi` | 0.48x | 0.98x | 0.86x | 0.15x | 0.35x | 1.07x |
| `cci` | 0.28x | 1.96x | 1.61x | 0.13x | 0.88x | 1.68x |
| `stoch` | 0.22x | 0.70x | 0.68x | 0.18x | 0.45x | 0.79x |
| `willr` | 0.16x | 0.31x | 0.29x | 0.12x | 0.23x | 0.47x |
| `roc` | 0.43x | 0.72x | 0.54x | 0.15x | 0.25x | 1.07x |
| `mfi` | 0.15x | 0.34x | 0.31x | 0.11x | 0.25x | 0.48x |
| `trix` | 0.47x | 0.46x | 0.40x | 0.15x | 0.26x | 0.64x |
| `ultosc` | 0.18x | 0.52x | 0.49x | 0.12x | 0.33x | 0.64x |
| `atr` | 0.16x | 0.21x | 0.20x | 0.12x | 0.19x | 0.51x |
| `bbands` | 0.50x | 0.36x | 0.33x | 0.27x | 0.34x | 0.48x |
| `stddev` | 0.44x | 0.45x | 0.37x | 0.15x | 0.28x | 0.47x |
| `obv` | 0.13x | 0.49x | 0.53x | 0.12x | 0.28x | 0.77x |
| `ad` | 0.11x | 0.27x | 0.29x | 0.11x | 0.21x | 0.71x |

### Batch (TA-Lib: a loop of calls; PyTA: one `pyta.batch` call; datasets x rows)

| Indicator | 10 x 1,000 (NumPy) | 100 x 100 (NumPy) | 100 x 10,000 (NumPy) | 1,000 x 1,000 (NumPy) | 10 x 1,000 (DataFrame) | 100 x 100 (DataFrame) | 100 x 10,000 (DataFrame) | 1,000 x 1,000 (DataFrame) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `sma` | 0.65x | 0.62x | 1.25x | 0.83x | 0.20x | 0.20x | 0.41x | 0.24x |
| `ema` | 0.34x | 0.48x | 0.70x | 0.65x | 0.17x | 0.19x | 0.33x | 0.23x |
| `wma` | 0.45x | 0.61x | 1.35x | 0.87x | 0.18x | 0.20x | 0.42x | 0.24x |
| `dema` | 0.37x | 0.47x | 0.87x | 0.73x | 0.17x | 0.19x | 0.35x | 0.23x |
| `tema` | 0.41x | 0.51x | 1.06x | 0.77x | 0.17x | 0.19x | 0.38x | 0.24x |
| `kama` | 0.51x | 0.48x | 1.52x | 1.02x | 0.18x | 0.20x | 0.47x | 0.25x |
| `macd` | 0.44x | 0.58x | 0.68x | 0.73x | 0.31x | 0.35x | 0.46x | 0.40x |
| `sar` | 0.30x | 0.23x | 1.13x | 0.54x | 0.18x | 0.17x | 0.54x | 0.23x |
| `adx` | 0.79x | 0.55x | 1.87x | 1.10x | 0.45x | 0.40x | 1.05x | 0.53x |
| `aroon` | 1.07x | 0.51x | 3.37x | 1.65x | 0.46x | 0.38x | 1.47x | 0.59x |
| `rsi` | 0.59x | 0.50x | 1.82x | 1.10x | 0.19x | 0.19x | 0.52x | 0.26x |
| `cci` | 0.95x | 0.32x | 3.19x | 1.40x | 0.28x | 0.16x | 1.30x | 0.33x |
| `stoch` | 0.51x | 0.30x | 1.61x | 0.83x | 0.26x | 0.23x | 0.78x | 0.34x |
| `willr` | 0.22x | 0.19x | 0.64x | 0.38x | 0.16x | 0.15x | 0.40x | 0.21x |
| `roc` | 0.61x | 0.59x | 0.74x | 0.66x | 0.19x | 0.20x | 0.32x | 0.22x |
| `mfi` | 0.23x | 0.17x | 0.67x | 0.37x | 0.16x | 0.14x | 0.44x | 0.20x |
| `trix` | 0.44x | 0.49x | 1.12x | 0.84x | 0.18x | 0.19x | 0.40x | 0.24x |
| `ultosc` | 0.34x | 0.23x | 1.09x | 0.55x | 0.18x | 0.16x | 0.55x | 0.24x |
| `atr` | 0.14x | 0.18x | 0.31x | 0.25x | 0.15x | 0.15x | 0.26x | 0.19x |
| `bbands` | 0.57x | 0.61x | 1.13x | 1.02x | 0.33x | 0.36x | 0.61x | 0.43x |
| `stddev` | 0.53x | 0.50x | 1.51x | 1.09x | 0.19x | 0.20x | 0.50x | 0.26x |
| `obv` | 0.23x | 0.18x | 0.87x | 0.40x | 0.16x | 0.16x | 0.44x | 0.21x |
| `ad` | 0.17x | 0.14x | 0.28x | 0.20x | 0.14x | 0.14x | 0.26x | 0.17x |

## Data Providers

On release, PyTA will initally support the data formats returned by both **yFinance** (`pandas`, `dict`, `tuple`) and **AlphaVantage** (`json`, `csv`).

## Development

Run the full check suite (Rust formatting, which it fixes first, Clippy, Rust tests, extension build, smoke test, pytest, and Ruff):

```bash
./scripts/test-suite.sh
```

Run benchmarks (`--single`, `--batch`, or `--all`; add `--rust`, `--python`, `--indicator NAME`, or `--quick` to narrow it):

```bash
./scripts/benchmark.sh --all
```

Each script prints its progress and writes a timestamped report, with a summary at the top and the full output below, to `tests/results/` or `benches/results/`. Compare reports over time to see what changed. See [`scripts/README.md`](scripts/README.md) for all options.

[`PyTA-Integration/`](PyTA-Integration/README.md) uses PyTA as an outside project does: it installs the release wheel into its own environment and runs examples, integration tests and the TA-Lib comparison (`PyTA-Integration/scripts/setup.sh`).

Project design and plans live in [`docs/`](docs/).

## License

PyTA is released under the [MIT License](LICENSE).
