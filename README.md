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

With a pandas DataFrame, the `close` column is used by default (names ignore case and surrounding whitespace). Use `column=` to pick another:

```python
result = pyta.sma(df, period=20)                  # DataFrame with an "sma_20" column
result = pyta.sma(df, period=20, column="open")
```

## Indicators

### Available

| Category | Indicator |
|---|---|
| Trend | Simple Moving Average (`sma`) |
| Momentum | Relative Strength Index (`rsi`, Wilder's smoothing) |

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
To be determined

## Data Providers

On release, PyTA will initally support the data formats returned by both **yFinance** (`pandas`, `dict`, `tuple`) and **AlphaVantage** (`json`, `csv`).

## Development

Run the full check suite (Rust formatting, Clippy, Rust tests, extension build, pytest, and Ruff):

```bash
./scripts/test-suite.sh
```

Quick build and smoke test:

```bash
./scripts/rebuild-and-run.sh
```

Project design and plans live in [`docs/`](docs/).

## License

PyTA is released under the [MIT License](LICENSE).