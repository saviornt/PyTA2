# PyTA Architecture

**Status:** Active development. Sections marked *(planned)* describe intended design that is not implemented yet. Everything else reflects the current code.

PyTA is a technical-analysis library: a Python API that cleans and validates user data, and a Rust backend that does the calculating. This document explains how the pieces fit together and where new code belongs. If a change departs from this design, update this document in the same change.

---

## 1. Goals

- **Drop-in replacement for TA-Lib, without the build pain.** Installation is a single `pip install`; users never compile anything.
- **Rust owns the calculations.** Formulas, numerical work, and concurrency live in Rust.
- **Python owns the user experience.** Python accepts whatever container the user has, cleans and validates it, calls Rust, and returns results in the same kind of container. Users never have to convert to a container type they didn't choose.
- **Concurrency is invisible.** Users do not need `asyncio` or threads. The engine decides internally whether concurrency is worth its overhead.
- **One implementation per indicator.** Single calls, batches, and every container type share the same Rust kernels.

### Core rule

> Indicator formulas belong in their category crate. Shared contracts belong in `pyta-core`. Execution policy belongs in `pyta-engine`. Python/Rust conversion belongs in `pyta-python`. Data cleaning, validation, and container handling belong in the Python package.

---

## 2. Repository layout

```text
PyTA/
├── .github/workflows/          # CI and release automation
├── benches/
│   └── python/bench_boundary.py    # Python-boundary benchmark
├── docs/
│   ├── ARCHITECTURE.md             # This document
│   ├── API.md                      # Public API reference
│   └── DEVELOPMENT.md              # Contributor workflow
├── python/
│   └── pyta/
│       ├── __init__.py             # Public exports
│       ├── _api.py                 # Shared execution boundary
│       ├── _async.py               # Placeholder; deferred
│       ├── _native.pyi             # Type stubs for the extension
│       ├── _types.py               # Internal types
│       ├── _validation.py          # Normalization and validation
│       ├── py.typed
│       └── indicators/
│           ├── __init__.py
│           ├── trend.py
│           └── momentum.py
├── rust/crates/
│   ├── pyta-core/                  # Shared types, validation, errors
│   ├── pyta-engine/                # Requests, dispatch, planning, execution
│   ├── pyta-trend/                 # Trend indicators
│   ├── pyta-momentum/              # Momentum indicators
│   └── pyta-python/                # PyO3 bridge (pyta._native)
├── scripts/                        # Build, test, and benchmark scripts
├── tests/
│   ├── python/                     # Public-API tests
│   ├── reference/                  # Comparisons with trusted references
│   └── smoke/                      # Quick build-and-run check
├── Cargo.toml                      # Rust workspace root
├── pyproject.toml                  # Python packaging (Maturin)
└── rust-toolchain.toml
```

### Layout notes

- The Rust workspace manifest is the root `Cargo.toml`; crates live under `rust/crates/`.
- `python/pyta/` is the import package. Maturin builds the extension from `rust/crates/pyta-python/Cargo.toml` and installs it as `pyta._native` (`module-name` in `pyproject.toml`, `[lib] name = "_native"`, and the `#[pymodule]` function name must stay consistent).
- `pyta._native` is internal. Users only import from `pyta`.

---

## 3. Data flow

```text
User data (list, tuple, ndarray, pandas, dict, JSON, ...)
    |
    v
Python layer         clean, validate, normalize -> float64 array(s)
    |
    v
pyta-python          GIL released; Rust types in, Rust types out
    |
    v
pyta-engine          dispatch (direct) or plan + execute (batch)
    |
    v
Category crate       formula kernel (pyta-trend, pyta-momentum, ...)
    |
    v
Python layer         restore the user's container type, with labeled outputs
    |
    v
User receives results in the container type they supplied
```

### Dependency rules

1. `pyta-core` depends on no other PyTA crate.
2. Category crates depend only on `pyta-core`.
3. `pyta-engine` depends on `pyta-core` and the category crates it dispatches to.
4. `pyta-python` is the only crate that depends on PyO3 and NumPy.
5. The Python package must not reimplement indicator formulas.
6. Production code never depends on test-only code. Avoid circular dependencies; move shared contracts to the lowest layer that needs them.

---

## 4. Rust crates

### `pyta-core`: shared contracts

Owns the types and rules every indicator shares.

| File | Responsibility |
|---|---|
| `input.rs` | `Series` (non-empty, all values finite) and `Ohlcv` (five aligned series) |
| `output.rs` | `IndicatorOutput`: values with `NaN` marking positions with no valid result |
| `error.rs` | `PytaError` and `PytaResult` |

Does not own formulas, scheduling, or Python concerns.

**Numerical conventions**

- Rust is strict: empty input and any non-finite value (`NaN` or infinity) are rejected.
- Output length always equals input length. Warm-up positions are `NaN`.
- Rust errors are structured (for example `InvalidPeriod`, `PeriodExceedsLength`, `InsufficientData`, `NonFiniteValue { index }`, `LengthMismatch`, `ExecutionFailed`).

### Category crates: formulas

Each crate owns the formulas for one technical-analysis category. One indicator per file where practical (`sma.rs`, `rsi.rs`), with unit and integration tests alongside.

| Crate | Indicators |
|---|---|
| `pyta-trend` | SMA |
| `pyta-momentum` | RSI (Wilder's smoothing) |

New categories (volatility, volume, valuation) are added as new `pyta-<category>` crates when there is a concrete indicator to implement.

### `pyta-engine`: requests, dispatch, execution

| File | Responsibility |
|---|---|
| `requests.rs` | `IndicatorKind`, `IndicatorRequest`, `IndicatorResult`, `IndicatorStatus` |
| `dispatch.rs` | Routes a request to its kernel; holds each indicator's estimated cost |
| `execution.rs` | `execute_direct` and the Rayon-backed `execute` |
| `batch.rs` | `execute_sequential` and `execute_batch` |
| `planner.rs` | `should_parallelize`: predicts whether concurrency beats sequential execution |

The engine has two execution paths. Both use the same `dispatch`, so results are identical.

**Direct path (`execute_direct`).** For a single dataset. Runs the kernel on the calling thread with no Tokio, Rayon, or channel overhead. A panic inside a kernel is caught and returned as `ExecutionFailed`.

**Batch path (`execute_batch`).** For multiple datasets. Each request is spawned on a Tokio `JoinSet`, bounded by a semaphore (`min(available workers, 32, batch length)`), and its CPU work is handed to Rayon. Results come back in input order, and a failed request never cancels the others.

**Planner.** Concurrency has a fixed cost, so it only helps when there is enough work. `should_parallelize` estimates each request's cost (from `estimated_cost_ns`, measured by the Criterion benchmarks), adds the scheduling overhead, and chooses concurrent execution only when it predicts a win. Single requests, tiny requests, and small batches run sequentially via `execute_sequential`.

Adding an `IndicatorKind` fails to compile until it has a dispatch arm and a cost estimate. When adding an indicator, benchmark it and include any dependence on `period` in its estimate.

### `pyta-python`: native bridge

- Registers `pyta._native` and its functions (`sma`, `rsi`).
- Accepts a read-only 1-D `float64` NumPy array, copies it once, releases the GIL, runs the engine, and returns a NumPy array.
- Maps `PytaError::ExecutionFailed` to `RuntimeError` and every other error to `ValueError`.
- Today the bridge calls `execute_direct`. Binding `execute_batch` for `pyta.batch` is *(planned)*.

---

## 5. Python package

The Python layer is responsible for everything about the user's data. Rust only sees clean arrays.

### Public surface

- `pyta/__init__.py` exports the public API (`sma`, `rsi`, `indicators`).
- `pyta/indicators/` groups user-facing functions by category with full docstrings. Each function delegates to `_api.run`.

### Private modules

| File | Responsibility |
|---|---|
| `_api.py` | `run()`: validate the period, normalize data, call native, restore the container. Also skips and re-pads a leading `NaN` run |
| `_validation.py` | `validate_period` and `normalize` for every supported container; column selection |
| `_types.py` | `Prepared`: a normalized series plus a function that rebuilds the caller's container |
| `_native.pyi` | Type stubs for the native module |
| `_async.py` | Placeholder; a Python async API is deferred |

### Input and output contract

Every supported container is reduced to one 1-D, C-contiguous `float64` array, with a function to rebuild the caller's container from a result.

| Input | Output |
|---|---|
| `list`, `tuple` | Same type |
| NumPy array (any real numeric dtype) | `float64` array |
| pandas Series | Series with the same index, named `<indicator>_<period>` |
| pandas DataFrame | DataFrame with one `<indicator>_<period>` column and the same index |
| `dict` of columns | `dict` with one `<indicator>_<period>` key |
| JSON (`str` or `bytes`): array, records, or object of arrays | JSON of the same shape and type; `NaN` is written as `null` |

Column selection (for DataFrame, dict, and JSON objects) ignores case and surrounding whitespace, defaults to `close` (or the only column), and can be set with `column=`. Names that collide after normalization are rejected.

**Responsibility split**

| Layer | Handles |
|---|---|
| Python | Container detection, column selection, dtype conversion, `None` and `null` gaps, parameter types and ranges, leading-`NaN` skipping so indicators can be chained, restoring the user's container |
| Rust | Emptiness, finiteness, period against length, and the calculation itself |

Python raises `TypeError` for unsupported types and `ValueError` for invalid values. Native errors surface as `ValueError`, or `RuntimeError` for internal execution failures.

Pydantic is a hard dependency and is used only for structure and parameter validation, never per element. pandas is optional and is only inspected if the caller has already imported it, so `import pyta` never loads it.

### Smart results *(planned for OHLCV)*

Multi-column indicators will follow the same rule: the user passes OHLCV in whatever container they have, PyTA identifies the container, pulls the columns the indicator needs, and returns the same container type.

- `IndicatorRequest` will grow from a single `Series` to named multi-column input (building on `Ohlcv`).
- Multi-output indicators (such as MACD and Bollinger Bands) return their outputs in the input's container type: extra columns for a DataFrame, extra keys for a dict or JSON object.
- CSV input will be added alongside the existing types, so data returned by AlphaVantage works directly.

---

## 6. Batch calculation *(planned)*

Batch calls apply one indicator to many datasets through the engine's concurrent path.

```python
results = pyta.batch.sma(datasets, period=14)
```

- `pyta.batch` mirrors the top-level indicator functions, with the same names and parameters. A new indicator gets a batch variant by following the same pattern.
- `datasets` is a list (or mapping) of any supported containers. Results are returned in the same shape and order, each in its own input's container type.
- The call is synchronous from the user's perspective; the engine decides internally whether to run sequentially or concurrently.
- The error policy for a failed dataset is not yet decided. The engine already reports per-request errors without cancelling the rest; the Python layer must choose how to surface them.

---

## 7. Concurrency model

- Rust owns concurrency. Python's `asyncio` is not part of PyTA's execution model, and no runtime details are exposed to users.
- Tokio coordinates batch work; Rayon runs the CPU-bound kernels. Batch concurrency (the semaphore) and Rayon's thread pool are separate controls.
- Concurrency adds overhead, so the planner chooses between sequential and concurrent execution. Do not assume that concurrency makes one calculation faster.
- The native boundary releases the GIL while the engine runs, so other Python threads are not blocked.
- A Python-level async API is deferred. If one is added later, it must wrap the same engine and must not create a separate calculation path.

---

## 8. Tests and quality checks

| Location | Purpose |
|---|---|
| Rust `#[cfg(test)]` modules and crate `tests/` | Formulas, boundary cases, warm-up, validation, engine ordering and error isolation |
| `tests/python/` | Public API behavior: containers, NaN policy, parameters, errors |
| `tests/reference/` | Comparisons against independent reference implementations, with matching conventions |
| `tests/smoke/` | Quick build-and-run check |

Run everything with `scripts/test-suite.sh`, which covers Rust formatting, Clippy, Rust tests, the extension build, pytest, and Ruff. Benchmarks must not be timing-sensitive assertions in regular tests.

## 9. Benchmarks

- `cargo bench -p pyta-engine` (via `scripts/benchmark_rust_engine.sh`) compares the kernel, direct, sequential, batch, and planner (`auto`) paths and prints a summary.
- `benches/python/bench_boundary.py` separates Python-layer cost from native-boundary cost.
- Benchmark results are the basis for the planner's cost constants. Re-measure when adding indicators.

---

## 10. Where should a change go?

| If you are changing... | Start here |
|---|---|
| A shared input, output, or error contract | `pyta-core` |
| A technical-analysis formula | Its category crate |
| How requests are routed | `pyta-engine/src/dispatch.rs` |
| Sequential vs concurrent decisions | `pyta-engine/src/planner.rs` |
| Batch ordering or batch errors | `pyta-engine/src/batch.rs` |
| Panic handling or per-request execution | `pyta-engine/src/execution.rs` |
| PyO3 registration or Rust/Python conversion | `pyta-python/src/lib.rs` |
| Supported input containers or column rules | `python/pyta/_validation.py` |
| Result container restoration | `python/pyta/_validation.py` (`Prepared`) |
| The shared call path for indicators | `python/pyta/_api.py` |
| A public indicator function | `python/pyta/indicators/` |
| Public exports | `python/pyta/__init__.py` |
| Packaging or build configuration | `pyproject.toml`, `Cargo.toml` |

## 11. Naming conventions

- Python modules and Rust source files: `snake_case`. Rust crate directories: kebab-case (`pyta-trend`). Private Python modules start with `_`.
- Crates are named `pyta-<category>`; one indicator per file when practical.
- Python function names are `snake_case` (`sma`, `rsi`). Use consistent parameter names across indicators (`period`, `column`).
- Anything re-exported from `pyta/__init__.py` is public API. Internal modules and `pyta._native` carry no stability promise.
- Document any non-default formula variants or smoothing methods.

## 12. Keeping this document current

1. Check this document before adding a directory or module.
2. Prefer existing ownership boundaries over new abstractions.
3. When adding a permanent component, document its purpose and dependency direction here.
4. Update the layout tree and tables in the same change.
5. A change that adds a permanent component is not complete until this document explains it.