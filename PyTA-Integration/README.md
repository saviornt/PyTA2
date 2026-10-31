# PyTA-Integration

An independent project that uses PyTA the way an outside user does: PyTA is installed from a release wheel into this project's own virtual environment and used only through its public API (`pyta.<name>`, `pyta.<category>.<name>`, `pyta.batch.<name>`). Nothing here imports PyTA's source tree or its private modules, and PyTA's own tests and tooling never import this project.

It holds runnable examples, integration tests against the installed package, and the TA-Lib comparison benchmarks.

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.15 (`uv python install 3.15` if `uv python list` does not show it).
- The Rust toolchain PyTA builds with (`rust-toolchain.toml` in the repository root), to build the wheel.

## Set up and run everything

From anywhere in the repository:

```bash
PyTA-Integration/scripts/setup.sh            # build the wheel, create .venv, run examples, tests, ruff
PyTA-Integration/scripts/setup.sh --bench    # also install TA-Lib 0.8.3 (the `bench` extra)
PyTA-Integration/scripts/setup.sh --no-build # reuse the wheel already in dist/
PyTA-Integration/scripts/setup.sh --no-run   # install only
```

The script works from a clean checkout (no `.venv/`, no `dist/`) and does this:

1. Builds PyTA's release wheel from the repository root's `pyproject.toml` (`uv run maturin build --release --out PyTA-Integration/dist`), which packages the Python sources together with the compiled extension. This uses PyTA's own development environment for maturin, so the first run also creates the root `.venv`.
2. Recreates `PyTA-Integration/.venv` with Python 3.15 (`uv venv --clear`).
3. Installs the wheel together with this project's dependencies and the `dev` group (`uv pip install dist/pyta-*.whl -r pyproject.toml --group dev`). Naming the wheel on the command line is what satisfies the `pyta` requirement, so it is never resolved from an index or from the source tree.
4. Runs every script in `examples/`, then `pytest` and `ruff`.

There is no `uv.lock` here on purpose: the `pyta` dependency is a locally built wheel whose file name and hash change with every build, so the install is done with `uv pip` instead of `uv sync`. `.venv/` and `dist/` are git-ignored.

After a change to PyTA, run `setup.sh` again: the wheel is rebuilt and the environment recreated, so the tests always run against the code as it would be released.

## Examples

Run any of them with the project's interpreter, from this directory:

```bash
.venv/bin/python examples/yfinance_dataframe.py
.venv/bin/python examples/alphavantage.py
.venv/bin/python examples/batch.py
```

| Example | Shows |
|---|---|
| `examples/yfinance_dataframe.py` | SMA, RSI, MACD and the Stochastic on a DataFrame shaped like yfinance's `history(auto_adjust=False)`: a time-zone aware `Date` index and `Open High Low Close Adj Close Volume` columns. Results come back as DataFrames on the same index with title-case names (`SMA`, `MACD_Signal`, `Stoch_K`). |
| `examples/alphavantage.py` | AlphaVantage-shaped CSV (`timestamp,open,high,low,close,volume`) and JSON (`Time Series (Daily)` keyed by date, `1. open` names, numbers as strings). Both arrive newest first and are put oldest first before the call, because PyTA never reorders rows; the JSON is flattened into records with the standard library. Shows CSV in and out, JSON records in and out, and `output="pandas"`. |
| `examples/batch.py` | `pyta.batch.rsi` over a mapping of five datasets, three of which fail (too short, a gap after the first value, no close column) and come back as their `ValueError` in place while the others complete; then `pyta.batch.bbands` over a list of NumPy arrays. |

## Data

| File | Contents |
|---|---|
| `data/spy_daily.csv` | 300 SPY sessions (2024-10-21 to 2025-12-31, unadjusted) from Yahoo Finance via yfinance, a copy of PyTA's test fixture. Yahoo's data is for personal use; check its terms before redistributing. It has no adjusted series, so the yfinance-shaped example fills `Adj Close` with `Close`. |
| `data/alphavantage_daily.csv` | The last 40 of those sessions in AlphaVantage's daily CSV layout, newest first. |
| `data/alphavantage_daily.json` | The same 40 sessions in AlphaVantage's daily JSON layout (`Meta Data`, `Time Series (Daily)`), numbers as strings with four decimals. |

## Tests

```bash
.venv/bin/python -m pytest      # from this directory
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

| File | Checks |
|---|---|
| `tests/test_examples.py` | Every example runs as a script with warnings as errors; their results have the documented columns, index, casing and warm-up, and the AlphaVantage results equal the DataFrame results for the same rows. |
| `tests/test_values.py` | SMA(20), RSI(14), MACD(12, 26, 9) and OBV on the SPY data against reference numbers computed without PyTA (kept as literals in the file) and recomputed with plain pandas/NumPy, to 1e-9; the same values from every container; chaining; `output="json"`; batch equals single calls. |
| `tests/test_errors.py` | Invalid parameters and data raise the documented `ValueError`/`TypeError` with the documented messages; batch parameter errors raise, batch data errors come back in place. |
| `tests/test_install.py` | PyTA is imported from this venv's site-packages and installed from a wheel (not editable, not the source tree on `sys.path`); `import pyta` does not import pandas; no file in this project names PyTA's private modules or its Rust crate paths. |

The error tests match messages exactly, so a deliberate wording change in PyTA means updating them here.

## Benchmarks

`benchmarks/compare_talib.py` times PyTA against TA-Lib 0.8.3 (the `bench` extra; TA-Lib is never a PyTA dependency), each called the way its documentation shows:

- **Single indicator:** one dataset per call, `talib.<NAME>(...)` against `pyta.<name>(...)`, at 100, 10,000 and 1,000,000 rows.
- **Batch:** TA-Lib has no batch call, so a list comprehension calling `talib.<NAME>` per dataset, against one `pyta.batch.<name>(...)` call over the list, at 10 x 1,000, 100 x 100, 100 x 10,000 and 1,000 x 1,000 (datasets x rows).

Both run on float64 NumPy arrays (TA-Lib one array per input, PyTA a dict of named arrays) and on yFinance-shaped DataFrames (TA-Lib the frame's columns, PyTA the whole frame), on a seeded random walk. `timeit` times the whole call, best of 5 repeats of ~0.1 s, the two libraries alternating. Each row also gives the largest relative difference between the outputs. Indicators TA-Lib lacks (Ichimoku, Keltner, Donchian, CMF, VWAP, Volume ROC) are not compared.

```bash
PyTA-Integration/scripts/setup.sh --bench --no-run          # install TA-Lib once
cd PyTA-Integration
.venv/bin/python benchmarks/compare_talib.py                # full run (about 15 minutes)
.venv/bin/python benchmarks/compare_talib.py --quick --indicator sma rsi --containers NumPy
```

The report is written to `results/compare_talib_<timestamp>.md` (git-ignored). Run on a quiet machine, ideally with the CPU governor set to `performance`; the report records the governor.
