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
uv run --with maturin maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml
```

## Usage

```python
import numpy as np
import pyta

close = np.array([10.0, 11.0, 12.0, 13.0, 12.0, 14.0])

sma = pyta.sma(close, period=3)
rsi = pyta.rsi(close, period=3)
```

Outputs have the same length as the input, with `NaN` for the warm-up period. Indicators accept the same container types as inputs and can be chained:

```python
smoothed_rsi = pyta.sma(pyta.rsi(close, period=14), period=5)
```

With a pandas DataFrame, an indicator uses its default column (`close` for SMA and RSI). Names ignore case, whitespace and `. _ -`, and common aliases match (`Adj Close`, `adjusted_close`, `Vol`, `o`/`h`/`l`/`c`). Use `column=` to pick another:

```python
result = pyta.sma(df, period=20)                  # DataFrame with an "sma_20" column
result = pyta.sma(df, period=20, column="open")
result = pyta.sma(df, period=20, column="adj close")
```

PyTA logs through Python's standard `logging` (Rust messages included) under the `pyta` logger and is silent unless you configure logging. For example, `logging.getLogger("pyta").setLevel(logging.DEBUG)` shows how batches are scheduled; see [Logging](docs/API.md#14-logging).

## Indicators

### Available

| Category | Indicator |
|---|---|
| Trend | [Simple Moving Average](docs/indicators/trend/sma.md) (`sma`) |
| Momentum | [Relative Strength Index](docs/indicators/momentum/rsi.md) (`rsi`, Wilder's smoothing) |

### Planned

The catalog below is the planned scope and is subject to change.

**Trend Indicators**
EMA, WMA, DEMA, TEMA, KAMA, MACD, ADX, Parabolic SAR, Ichimoku Cloud, Aroon

**Momentum Indicators**
CCI, Stochastic Oscillator, Williams %R, ROC, MFI, TRIX, Ultimate Oscillator

**Volatility Indicators**
ATR, Bollinger Bands, Keltner Channels, Donchian Channels, Standard Deviation

**Volume Indicators**
OBV, VWAP, Accumulation/Distribution, Chaikin Money Flow, Volume Rate of Change

**Valuation Indicators**
Mayer Multiple, Z-Score, P/E(TTM), Earnings Yield, P/B, P/S, Dividend Yield, EV/EBITDA, PEG
*Future*: DCF, DDM, Residual Income, Justified P/E, Comparables, CAPE


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

Project design and plans live in [`docs/`](docs/).

## License

PyTA is released under the [MIT License](LICENSE).