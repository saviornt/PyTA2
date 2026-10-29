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

> Indicator formulas belong in their category crate. Tunable constants belong in `pyta-common`. Shared contracts belong in `pyta-core`. Execution policy belongs in `pyta-engine`. Python/Rust conversion belongs in `pyta-python`. Data cleaning, validation, and container handling belong in the Python package.

---

## 2. Repository layout

```text
PyTA/
├── .github/workflows/          # CI and release automation
├── benches/
│   ├── python/bench_boundary.py    # Single-call Python-boundary benchmark
│   ├── python/bench_batch.py       # pyta.batch vs a loop of single calls
│   └── results/                    # Timestamped benchmark reports
├── docs/
│   ├── ARCHITECTURE.md             # This document
│   ├── API.md                      # Public API reference
│   └── DEVELOPMENT.md              # Contributor workflow
├── python/
│   └── pyta/
│       ├── __init__.py             # Public exports
│       ├── _api.py                 # Shared execution boundary
│       ├── _columns.py             # Multi-column normalization (slots matched by role)
│       ├── _native.pyi             # Type stubs for the extension
│       ├── _types.py               # Internal types
│       ├── _validation.py          # Normalization, validation, role registry
│       ├── py.typed
│       ├── trend.py                # pyta.trend namespace; re-exports only
│       ├── momentum.py             # pyta.momentum namespace; re-exports only
│       ├── batch/                  # pyta.batch namespaces; re-exports only
│       │   ├── __init__.py         # pyta.batch.<name>
│       │   ├── trend.py            # pyta.batch.trend.<name>
│       │   └── momentum.py         # pyta.batch.momentum.<name>
│       └── indicators/
│           ├── __init__.py         # pyta.indicators.<name>
│           ├── trend/
│           │   ├── __init__.py
│           │   └── sma.py          # sma() and sma_batch()
│           └── momentum/
│               ├── __init__.py
│               ├── cci.py          # cci() and cci_batch() (high, low, close)
│               └── rsi.py          # rsi() and rsi_batch()
├── rust/crates/
│   ├── pyta-common/                # Tunable constants (no logic, no dependencies)
│   ├── pyta-core/                  # Shared types, validation, errors
│   ├── pyta-engine/                # Requests, dispatch, planning, execution
│   ├── pyta-trend/                 # Trend indicators
│   ├── pyta-momentum/              # Momentum indicators
│   └── pyta-python/                # PyO3 bridge (pyta._native)
├── rust/test-support/reference.rs  # Reads tests/fixtures/ for the Rust reference tests
├── scripts/                        # test-suite.sh, benchmark.sh, benchmark_summary.py, README.md
├── tests/
│   ├── fixtures/                   # Published reference examples (CSV, sources cited)
│   ├── python/                     # Public-API tests
│   ├── reference/                  # Comparisons with trusted references
│   ├── results/                    # Timestamped test-suite reports
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
Python layer         clean, validate, normalize -> one float64 array, or one per slot
                     (multi-column: columns matched to the indicator's slots by role)
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

1. `pyta-common` depends on nothing.
2. `pyta-core` depends only on `pyta-common`.
3. Category crates depend only on `pyta-core` (and may use `pyta-common`).
4. `pyta-engine` depends on `pyta-common`, `pyta-core`, and the category crates it dispatches to.
5. `pyta-python` is the only crate that depends on PyO3 and NumPy.
6. The Python package must not reimplement indicator formulas.
7. Production code never depends on test-only code. Avoid circular dependencies; move shared contracts to the lowest layer that needs them.

---

## 4. Rust crates

### `pyta-common`: tunable constants

One place to adjust values while tuning, shared by the engine, benchmarks, and tests. It holds only documented `pub const`s and no logic.

| File | Contents |
|---|---|
| `scheduling.rs` | Concurrent-engine overheads used by the planner |
| `costs.rs` | Estimated ns per element for each indicator |
| `limits.rs` | Batch concurrency cap and validation block length |
| `benchmarks.rs` | Benchmark input sizes and sample counts, and the worker count assumed by planner tests |

Values that define an algorithm (for example RSI's 0 to 100 scale) stay with their formula.

### `pyta-core`: shared contracts

Owns the types and rules every indicator shares.

| File | Responsibility |
|---|---|
| `input.rs` | `Series` (non-empty, all values finite) and `Columns` (one or more `Series` of equal length, in an indicator's slot order) |
| `output.rs` | `IndicatorOutput`: one or more equal-length series (outputs) in the indicator's documented order, with `NaN` marking positions with no valid result |
| `error.rs` | `PytaError` and `PytaResult` |

Does not own formulas, scheduling, or Python concerns.

**Numerical conventions**

- Rust is strict: empty input, any non-finite value (`NaN` or infinity), and any value whose magnitude exceeds `MAX_ABS_INPUT` (`1e290`, in `pyta-common`) are rejected by `Series` validation.
- Output length always equals input length. Warm-up positions are `NaN`, and only warm-up positions: for valid input every other output is finite.
- `MAX_ABS_INPUT` is what makes that guarantee hold. Kernels may form sums of up to `period` values and differences of two values; with every input at most `1e290` in magnitude, those stay below `f64::MAX` (about `1.8e308`) for any series that fits in memory (at most 2^60 elements). Without it, `sma([f64::MAX, f64::MAX], 2)` returned `inf`. Checking against the limit costs the same as checking for finiteness: it is one compare per value, and it also rejects `NaN` and infinity. A future kernel that squares values (for example a standard deviation) must scale or centre them before squaring, or this limit must be revisited.
- Rust errors are structured (for example `InvalidPeriod`, `InvalidParameter { name, minimum, value }` for a parameter other than `period`, `PeriodExceedsLength`, `InsufficientData`, `NonFiniteValue { index }`, `ValueOutOfRange { index }`, `LengthMismatch`, `ColumnCount { expected, actual }`, `ExecutionFailed`).
- **Outputs.** `IndicatorOutput::new(values)` wraps a single output; `IndicatorOutput::with_outputs(vec![...])` wraps several (MACD: line, signal, histogram), rejecting none or unequal lengths with `LengthMismatch`. `values()` / `into_values()` give the first (main) output, `outputs()` / `into_outputs()` all of them, `output_count()` how many. Outputs are positions only; their names live in Python, like slots. Each output has its own warm-up.
- `Columns` knows nothing about roles: Python matches columns to slots and passes them in slot order, so a new role (such as a fundamental) needs no new Rust type. Rust does not check columns against each other (high below low); Python does, so the error can name the columns.

### Category crates: formulas

Each crate owns the formulas for one technical-analysis category. One indicator per file where practical (`sma.rs`, `rsi.rs`), with unit and integration tests alongside.

| Crate | Indicators |
|---|---|
| `pyta-trend` | SMA; EMA (TA-Lib `TA_EMA`: seeded with the SMA of the first `period` values, `k = 2 / (period + 1)`); MACD (TA-Lib `TA_MACD`: three outputs, both EMAs start at `slow - 1`, `slow < fast` swapped; one fused pass after the seeds, bit-identical to separate EMA passes) |
| `pyta-momentum` | RSI (Wilder's smoothing), CCI (high, low, close; compensated running mean, O(rows × period) for the mean deviation) |

New categories (volatility, volume, valuation) are added as new `pyta-<category>` crates when there is a concrete indicator to implement.

### `pyta-engine`: requests, dispatch, execution

| File | Responsibility |
|---|---|
| `requests.rs` | `Params`, `IndicatorKind`, `IndicatorInput`, `IndicatorRequest`, `IndicatorResult`, `IndicatorStatus` |
| `dispatch.rs` | Routes a request to its kernel; holds each indicator's estimated cost |
| `execution.rs` | `execute_direct`: one request on the calling thread, panics caught |
| `batch.rs` | `execute_sequential`, `execute_parallel` (Rayon), and `execute_batch` (async front door) |
| `planner.rs` | `should_parallelize`: predicts whether parallel execution beats sequential execution |

**Parameters.** `IndicatorRequest { input, params }`. `Params` has one variant per indicator, carrying that indicator's own parameters: `Cci { period }`, `Ema { period }`, `Macd { fast, slow, signal }`, `Rsi { period }`, `Sma { period }`. The indicator is the variant, so it cannot disagree with its parameters; `params.kind()` (or `request.kind()`) gives the fieldless `IndicatorKind`, used for logging and benchmark labels. Each `dispatch` arm destructures its own variant, and `estimated_cost_ns` reads the parameters it depends on (CCI's `period`; EMA's and MACD's cost per row does not depend on theirs).

**Input.** `IndicatorRequest.input` is an `IndicatorInput`: `Series` for a single-column indicator (`IndicatorRequest::new(series, Params::Rsi { period: 14 })`) or `Columns` for a multi-column one (`IndicatorRequest::with_columns(columns, Params::Cci { period: 20 })`). Each `dispatch` arm takes what its kernel needs, `input.series()` or `input.columns::<N>()` (the slots in order), so a kernel receives only `&Series` values; input with the wrong number of columns is a `ColumnCount` error, never a panic. A cost is per row, not per row and column or per output; a multi-column or multi-output constant is measured per row.

The engine has two execution paths. Both use the same `dispatch`, so results are identical.

**Direct path (`execute_direct`).** For a single dataset. Runs the kernel on the calling thread with no thread-pool or channel overhead. A panic inside a kernel is caught and returned as `ExecutionFailed`.

**Batch path (`execute_parallel`).** For multiple datasets. Rayon `par_iter` runs `execute_direct` over the requests: Rayon owns the worker threads, splits the batch, and balances the load. Results come back in input order, and a failed request never cancels the others. `execute_sequential` is the same loop on the calling thread.

**Async front door (`execute_batch`).** For async Rust callers. It moves the whole batch to a blocking thread in one hop and runs `execute_parallel`, so Tokio never schedules individual requests and no second calculation path exists. The Python API is synchronous and does not use it; it exists for a future Python `await` API.

*Why not Tokio per request?* Benchmarks showed Tokio adds a task spawn, semaphore, channel, and wake-ups per request (about 1 ms per 1,000 requests), while nothing here waits on I/O. For 1,000 datasets of 100 points, Rayon took about 90 µs against about 1 ms for per-request Tokio tasks.

**Planner.** Parallel execution has a fixed cost, so it only helps when there is enough work. `should_parallelize(requests, workers)` estimates each request's cost (from `estimated_cost_ns`), adds the scheduling overhead, caps the expected speed-up (`MAX_PARALLEL_SPEEDUP`), and chooses parallel execution only when it predicts a win. Single requests and small batches run sequentially via `execute_sequential`. All constants live in `pyta-common`.

Adding a `Params` variant fails to compile until it has a kind, a dispatch arm and a cost estimate. When adding an indicator, benchmark it and include any dependence on its parameters in its estimate.

### `pyta-python`: native bridge

- Registers `pyta._native` and its functions (`sma`, `rsi`, `cci`, `ema`, `macd`, and their `_batch` forms). Each takes its indicator's own parameters (`macd(values, fast, slow, signal)`) and builds the matching `Params` variant.
- `lib.rs` only declares modules and registers functions. `error.rs` maps errors to exceptions, `single.rs` and `batch.rs` hold the shared conversion and execution plumbing, and each indicator's bindings live in a file named after it (`sma.rs`, `rsi.rs`, `cci.rs`, `ema.rs`, `macd.rs`).
- A single-column function accepts a read-only 1-D `float64` NumPy array; a multi-column one (`compute_columns`, `compute_columns_batch`) accepts a list of them in slot order. Each array is copied once with validation fused into the copy (`series_from`, `columns_from`), then the GIL is released, the engine runs, and the output is returned without copying by `output_to_python`: a NumPy array for a single-output indicator, or a list of NumPy arrays in documented order for a multi-output one (`macd` returns `[macd, signal, hist]`). Single- and multi-column batches share one loop (`run_datasets`); each batch entry has the same shape as a single call's result, or is the dataset's exception.
- Maps `PytaError::ExecutionFailed` to `RuntimeError` and every other error to `ValueError`.
- Single calls use `execute_direct`; batch calls use the planner, then `execute_sequential` or `execute_parallel` (see §6).
- Parallel batches run on PyTA's own Rayon pool (`batch.rs`), built on first use and rebuilt in a forked child, because a child process does not inherit its parent's worker threads and work sent to an inherited pool would wait forever. `tests/python/test_fork.py` covers this.

### Logging across Rust and Python

Python's `logging` is PyTA's one logging system; users configure it once and see Rust and Python records in one stream (API.md §14).

- **Rust** uses the `log` macros with targets `pyta::engine`, `pyta::planner` and `pyta::bridge`. `pyta-python/src/log_bridge.rs` is the `log` logger: installed in the `#[pymodule]`, it hands each record to the Python logger of the same dotted name (`pyta.planner`), keeping the Rust file and line. It stands in for `pyo3-log`, whose latest release (0.13.4) supports PyO3 below 0.30 only.
- **Python** uses `pyta.api` (batch failures) and `pyta.validation` (column resolution). `pyta/__init__.py` adds a `NullHandler` to `pyta` and nothing else.
- **Levels.** DEBUG: the planner's choice, the worker pool starting or rebuilt after `fork()`, column resolution, each failed dataset. WARNING: one summary per batch with failures. ERROR: a kernel panic caught by `catch_unwind` (`execute_direct`). No INFO.
- **Cost.** `log`'s global maximum level is set from the Python loggers when the module loads and refreshed at the start of each batch call (three cached `isEnabledFor` calls); with DEBUG off every Rust statement costs one atomic load. Single calls do no logging work. Records that pass take the GIL, so logging stays out of kernels and per-element loops: the planner and pool log from the calling thread before work starts, and only a panic logs from a worker.
- `pyta-common` and the kernel crates have no logging and no PyO3. Rust tests and benchmarks use their own loggers (`env_logger` in the benchmarks, enabled by `RUST_LOG`).

---

## 5. Python package

The Python layer is responsible for everything about the user's data. Rust only sees clean arrays.

### Public surface

- `pyta/__init__.py` exports the public API (`sma`, `rsi`, `cci`, `batch`, `indicators`, and the category namespaces `trend`, `momentum`).
- `pyta/indicators/<category>/` holds one module per indicator (`trend/sma.py`, `momentum/rsi.py`, `momentum/cci.py`). Each module contains that indicator's single-call function and its batch function, with full docstrings, delegating to `_api.run` and `_api.run_batch` (single-column) or `_api.run_columns` and `_api.run_columns_batch` (multi-column, with the indicator's `SLOTS`).
- Everything else only re-exports, so every import style reaches the same function object (`pyta.trend.sma is pyta.indicators.sma is pyta.sma`): the category `__init__.py`, `pyta/indicators/__init__.py`, the thin top-level `pyta/<category>.py` (a real module, because `import pyta.trend` cannot import an attribute), and the `pyta/batch/` package (`pyta.batch.<name>` and `pyta.batch.<category>.<name>`, both the indicator's `<name>_batch`). None holds logic.
- Function names shadow their module names (`pyta.indicators.trend.sma` is the function), so code that needs the module imports from it: `from pyta.indicators.trend.sma import sma_batch`.

### Adding a category

A category has one name used everywhere: the Rust crate `pyta-<category>`, the Python subpackage `pyta/indicators/<category>/`, and the user docs `docs/indicators/<category>/`. Add a category with its first indicator, never empty:

1. `pyta/indicators/<category>/__init__.py`: docstring naming the category and its planned members; re-exports each indicator's single-call function; sorted `__all__`. One module per indicator beside it.
2. `pyta/indicators/__init__.py`: import the subpackage and its functions; add the category and the names to the sorted `__all__`.
3. `pyta/<category>.py`: re-exports from `pyta.indicators.<category>`; sorted `__all__`.
4. `pyta/batch/<category>.py`: `from pyta.indicators.<category>.<name> import <name>_batch as <name>`; sorted `__all__`. `pyta/batch/__init__.py` imports the category and its names and lists them in `__all__`.
5. `pyta/__init__.py`: import the category module and add it to `__all__`.
6. `tests/python/test_namespaces.py`: add each indicator to `INDICATORS` and its documented paths to `DOCUMENTED_PATHS`. Its convention test checks the steps above for every subpackage it finds.

Adding a category or an indicator only adds names; no existing import path changes.

### Private modules

| File | Responsibility |
|---|---|
| `_api.py` | `run()` / `run_batch()`: normalize data, call native with the indicator's validated parameters, restore the container with every output named; also skip and re-pad a leading `NaN` run (for each output). `run_columns()` / `run_columns_batch()`: the same for multi-column indicators, plus the row-order check (`ORDERED_ROLES`) and column-named value errors |
| `_validation.py` | Parameter validators (`validate_period`, `validate_fast`, `validate_slow`, `validate_signal`) and `normalize` for every supported container; single-column selection; the role registry (`register_role`, `role_of`) and `Slot` |
| `_columns.py` | `normalize_columns`: every named container matched to an indicator's slots by role (or by `columns=`), unnamed ones in slot order |
| `_outputs.py` | `OutputNames` (an indicator's output names in lower, upper and title case) and the casing rule that picks one from the input's column names |
| `_types.py` | `Prepared` (a normalized series) and `PreparedColumns` (one series per slot, with labels and roles), each with the input column names used and a function that rebuilds the caller's container from (name, values) pairs |
| `_native.pyi` | Type stubs for the native module |

### Input and output contract

Every supported container is reduced to one 1-D, C-contiguous `float64` array, with a function to rebuild the caller's container from the results, one (name, values) pair per output.

| Input | Output |
|---|---|
| `list`, `tuple` | Same type; a tuple of them for a multi-output indicator |
| NumPy array (any real numeric dtype) | `float64` array; a tuple of them for a multi-output indicator |
| pandas Series | Series with the same index, named after the output (`sma`); a tuple of Series for a multi-output indicator |
| pandas DataFrame | DataFrame with one column per output and the same index |
| `dict` of columns | `dict` with one key per output, each value in the input column's container type |
| JSON (`str` or `bytes`): array, records, or object of arrays | JSON of the same shape and type, one key per output (a JSON array of numbers gives an object keyed by output name for a multi-output indicator); `NaN` is written as `null` |

**Output names.** Each indicator module declares `OUTPUTS` (lower case, documented order: `("macd", "macd_signal", "macd_hist")`) and which parts are abbreviations, as an `OutputNames`; names are bare, without parameters. Their casing follows the input column names the call used (`_outputs.casing`): all lower → lower; no lower-case letters → upper (`MACD_SIGNAL`); title case, where each word is capitalized or all capitals (`Close`, `Adj Close`, and PyTA's own `MACD_Signal`, so outputs chain) → abbreviations upper and words title (`SMA`, `MACD_Signal`); mixed, disagreeing or unnamed → lower. The separator is always `_`.

**Parameters.** Each indicator module validates its own parameters with the shared validators in `_validation.py` and passes them, in its native function's order, to the runners (`run(native, OUTPUTS, data, params, ...)`), which call `native(values, *params)`. A batch shares them across datasets, so an invalid one raises for the whole call.

Column selection (for DataFrame, dict, and JSON objects) uses an explicit `column=`, else the only column, else the indicator's own default column role. Each indicator function passes its default (`default_column=CLOSE` for `sma` and `rsi`) to `_api.run` / `_api.run_batch`; `_validation.py` holds no default of its own. Names ignore case, whitespace and `. _ -`, match the aliases of their role (`OPEN`, `HIGH`, `LOW`, `CLOSE`, `ADJ_CLOSE`, `VOLUME`; a role never matches another role's aliases), and are rejected when two collide after normalization.

**Responsibility split**

| Layer | Handles |
|---|---|
| Python | Container detection, column selection and matching columns to slots, dtype conversion, `None` and `null` gaps, parameter types and ranges, leading-`NaN` skipping so indicators can be chained, rows checked across columns (high not below low), restoring the user's container |
| Rust | Emptiness, finiteness, magnitude, equal column lengths and count, parameters against length (MACD's swap of `slow < fast`), and the calculation itself |

For multi-column input, Python checks values only after Rust has rejected one, to name the column and the row in the caller's data; on success it never scans them, so the Rust check is the only one paid.

Python raises `TypeError` for unsupported types and `ValueError` for invalid values. Native errors surface as `ValueError`, or `RuntimeError` for internal execution failures.

Pydantic is a hard dependency and is used only for structure and parameter validation, never per element. A parameter that is already a plain `int` in range skips it (Pydantic would return the same value; in context it cost about 1 µs of a 100-row call); anything else goes through Pydantic. pandas is optional and is only inspected if the caller has already imported it, so `import pyta` never loads it.

### Multi-column input

Multi-column indicators follow the same rule as single-column ones: the user passes OHLCV in whatever container they have, PyTA identifies the container, pulls the columns the indicator needs, and returns the same container type.

- **Roles.** A role is what a column holds (`open`, `high`, ..., `volume`). `_validation.register_role(name, *aliases)` adds one; it returns the name for use as a constant and raises if an alias already belongs to another role, so no alias is ambiguous. A fundamental role (`eps`, `book_value`, ...) is one call; nothing else changes, because Rust only sees columns in slot order.
- **Slots.** Each multi-column indicator declares `SLOTS`, a tuple of `Slot(name, roles)` in the order its native function takes the columns and unnamed input uses. A slot's roles are in preference order (CCI's `close` accepts `close`, or else `adj_close`).
- **Matching.** With no `columns=`, each slot takes the first role it accepts that the input has, under any alias; unneeded columns are ignored, whatever they hold. `columns=[...]`, in any order, assigns each name to the slot for its role; an unrecognized name, a role no slot takes, two names for one slot, an empty slot or a name not in the input raise `ValueError` naming the indicator's slots. A missing role raises `ValueError` naming the required and the available columns. The match is cached per set of column names.
- **Unnamed input.** A 2-D table (NumPy array, list of rows or of column lists, JSON array of arrays) or a tuple of arrays is taken in slot order. For a table, the axis whose length equals the slot count holds the columns, `(rows, columns)` when both do (`_columns._split`, an O(1) shape check); a tuple's count must match. A list or tuple of pandas Series sharing one index is matched by name like a dict when every Series is named by a role, else taken in slot order. A single series raises `TypeError`.
- **Rows.** The longest leading-`NaN` run across the slots is skipped (and re-padded), so chained outputs stay aligned. `ORDERED_ROLES` (in `_columns.py`) lists role pairs that must hold on every row, today `(high, low)`; a violation raises `ValueError` naming both columns and the row.

Still planned:

- CSV input will be added alongside the existing types, so data returned by AlphaVantage works directly.

---

## 6. Batch calculation

Batch calls apply one indicator to many datasets through the engine's concurrent path.

```python
results = pyta.batch.sma(datasets, period=14)
```

- `pyta.batch` mirrors the top-level indicator functions, with the same names and parameters. A new indicator gets a batch variant by following the same pattern.
- `datasets` is a list (or mapping) of any supported containers. Results are returned in the same shape and order, each in its own input's container type.
- The call is synchronous from the user's perspective; the planner decides internally whether to run sequentially or concurrently.
- The parameters (`period`, or MACD's `fast`, `slow`, `signal`) and `column` (or `columns` for a multi-column indicator) are shared by the whole batch. One indicator per call; mixed-indicator batches are a later sprint.
- **Error policy.** Nothing is raised for a bad dataset, so the others still complete. Python normalizes and validates each dataset first (`_api.run_batch`); a dataset that fails there becomes its exception. The rest go to Rust in a single call, and a per-request engine error becomes the matching exception (`ValueError`, or `RuntimeError` for internal failures). Invalid parameters or `column` raise, because they affect every dataset.
- **Native side.** `pyta._native.sma_batch` / `rsi_batch` / `ema_batch` / `macd_batch` take a list of arrays (`cci_batch` a list of lists of arrays, one per slot), copy and validate each, release the GIL, and return a list in input order whose entries are each an array (a list of arrays for `macd_batch`) or an exception. The bridge asks `should_parallelize` and then runs `execute_sequential` or `execute_parallel` on its own Rayon pool.

---

## 7. Concurrency model

- Rust owns concurrency. Python's `asyncio` is not part of PyTA's execution model, and no runtime details are exposed to users.
- Rayon owns the worker threads and runs the CPU-bound kernels, directly from the calling thread (GIL released). Tokio is not on the synchronous path; it is only the async front door (`execute_batch`).
- Parallelism adds overhead, so the planner chooses between sequential and parallel execution. Do not assume that concurrency makes one calculation faster.
- The native boundary releases the GIL while the engine runs, so other Python threads are not blocked.
- A Python-level async API is deferred. If one is added later, it must wrap the same engine and must not create a separate calculation path.

---

## 8. Tests and quality checks

| Location | Purpose |
|---|---|
| Rust `#[cfg(test)]` modules and crate `tests/` | Formulas, boundary cases, warm-up, validation, engine ordering and error isolation, sequential vs parallel equality, logging (a per-thread capturing logger in `pyta-engine`) |
| Crate `tests/property_tests.rs` (`proptest`) | Kernel invariants for any input: output length, exact warm-up (per output for MACD), SMA and EMA within the input's range, MACD's histogram exactly line minus signal and zero for constant input, RSI in [0, 100], constant input, CCI within `period / 0.03` and unchanged by a shift and a positive scale |
| Crate `tests/reference_tests.rs` | Reference examples from `tests/fixtures/` (published worked examples, and TA-Lib's own output for EMA and MACD at 1e-9), read by `rust/test-support/reference.rs` |
| `tests/fixtures/` | Reference examples as CSV (`label,input,expected`, one column per role such as `label,high,low,close,expected` for a multi-column indicator, or one `expected_<output>` column per output such as `expected_macd,expected_macd_signal,expected_macd_hist`), each citing its source, parameters (`period:`, or `fast:`, `slow:`, `signal:`) and tolerance in `#` comments, shared by Rust and Python; and realistic input data (`ohlcv_daily.csv`: 300 sessions of real SPY OHLCV, source cited), which is input only, never a reference. Python tests get it from the `ohlcv` fixture (`tests/conftest.py`, loader and an independent `rolling_mean` in `tests/ohlcv_data.py`) |
| `tests/python/` | Public API behavior: containers, NaN policy, parameters, errors, batch, logging, fork, import surface; per-indicator numerics (`test_sma.py`, `test_rsi.py`, `test_cci.py`); multi-column input for every container, `columns=`, the role registry and errors (`test_multi_column.py`); `hypothesis` properties (`test_properties.py`, and `columns=` permutations) |
| `tests/reference/` | The same published examples through the public API |
| `tests/smoke/` | Quick build-and-run check: the OHLCV fixture as a dict of columns through `pyta.sma`, `pyta.rsi`, `pyta.cci` and `pyta.batch` (stdlib only, so it also runs as a script) |

Quality gates, all in `scripts/test-suite.sh` and mirrored by CI:

- **Rust:** `rustfmt`; Clippy with `-D warnings` and the workspace lints in the root `Cargo.toml` (`unsafe_code` denied, `missing_docs`, a curated `pedantic` subset; every crate opts in with `[lints] workspace = true`; `clippy.toml` lists names such as PyTA that are not code); optional `cargo nextest` and `cargo llvm-cov`. CI also runs `cargo deny` for licenses and advisories (`deny.toml`).
- **Python:** pytest with `--strict-markers --strict-config`, warnings as errors, a `pandas` marker for tests that need the extra, and `pytest-cov` branch coverage of `pyta` with a floor; Ruff (`E, F, I, UP, B, SIM, RUF, PT, PERF, C4, TID`); Pyright in strict mode on `python/` (chosen over `ty`, which is still a 0.0.x beta); `mypy.stubtest` checks `_native.pyi` against the compiled module.

Every step runs even if one fails, and the report is written to `tests/results/test-suite_<datetime>.txt` (summary on top, full output below). Benchmarks must not be timing-sensitive assertions in regular tests.

## 9. Benchmarks

- `scripts/benchmark.sh (--single | --batch | --all) [--rust | --python] [--indicator NAME] [--quick]` runs the benchmarks and writes `benches/results/benchmark_<datetime>.txt` (options, environment and summaries on top, full output below). Keep the reports: they are the long-term record. A change is judged by a same-session A/B run against its base, not by an old report. See `scripts/README.md`.
- Single calls: Criterion `single_call` (cost of each stage of one call, per indicator) and `benches/python/bench_boundary.py` (Python layer vs native).
- Batch calls: Criterion `workloads` (`sequential`, `parallel`, `batch`, and planner `auto` for one to four requests, plus many-dataset runs of 10 / 100 / 1,000 datasets) and `benches/python/bench_batch.py` (`pyta.batch` vs a loop of single calls).
- `scripts/benchmark_summary.py` turns the Criterion output into tables.
- `benches/python/bench_boundary.py` separates Python-layer cost from native-boundary cost.
- Benchmark results are the basis for the planner's cost constants. Re-measure when adding indicators.

---

## 10. Where should a change go?

| If you are changing... | Start here |
|---|---|
| A tunable constant (overheads, costs, limits, benchmark sizes) | `pyta-common` |
| A shared input, output, or error contract | `pyta-core` |
| A technical-analysis formula | Its category crate |
| How requests are routed | `pyta-engine/src/dispatch.rs` |
| Sequential vs concurrent decisions | `pyta-engine/src/planner.rs` |
| Batch ordering or batch errors | `pyta-engine/src/batch.rs` |
| Panic handling or per-request execution | `pyta-engine/src/execution.rs` |
| PyO3 registration | `pyta-python/src/lib.rs` |
| Rust/Python conversion and batch execution | `pyta-python/src/single.rs`, `batch.rs` |
| An indicator's native bindings | `pyta-python/src/<indicator>.rs` |
| Supported input containers or column rules | `python/pyta/_validation.py` (single-column), `python/pyta/_columns.py` (multi-column) |
| A column role (for example a fundamental such as `eps`) | `register_role` in `python/pyta/_validation.py` |
| A rule between columns on every row (high not below low) | `ORDERED_ROLES` in `python/pyta/_columns.py` |
| An indicator's input columns | `SLOTS` in its `python/pyta/indicators/<category>/<name>.py` |
| Result container restoration | `python/pyta/_validation.py` (`Prepared`), `python/pyta/_columns.py` (`PreparedColumns`) |
| The shared call path for indicators | `python/pyta/_api.py` |
| A public indicator function | `python/pyta/indicators/<category>/<name>.py` |
| Public exports and category namespaces | `python/pyta/__init__.py`, `indicators/__init__.py`, `indicators/<category>/__init__.py`, `pyta/<category>.py`, `pyta/batch/` (see [Adding a category](#adding-a-category)) |
| Packaging or build configuration | `pyproject.toml`, `Cargo.toml` |

## 11. Naming conventions

- Python modules and Rust source files: `snake_case`. Rust crate directories: kebab-case (`pyta-trend`). Private Python modules start with `_`.
- Crates are named `pyta-<category>`; one indicator per file when practical.
- Python function names are `snake_case` (`sma`, `rsi`). Use consistent parameter names across indicators (`period`, `column`, `columns`); an indicator with other parameters names them as its usual definition does (MACD's `fast`, `slow`, `signal`).
- Anything re-exported from `pyta/__init__.py` is public API. Internal modules and `pyta._native` carry no stability promise.
- Document any non-default formula variants or smoothing methods.

## 12. Keeping this document current

1. Check this document before adding a directory or module.
2. Prefer existing ownership boundaries over new abstractions.
3. When adding a permanent component, document its purpose and dependency direction here.
4. Update the layout tree and tables in the same change.
5. A change that adds a permanent component is not complete until this document explains it.
