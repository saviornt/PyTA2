# PyTA — Agile Development Plan

**Project:** PyTA — Python technical analysis library with a Rust calculation engine  
**Methodology:** Lightweight Agile, incremental delivery, test-driven development where practical  
**Initial scope:** Trend and Momentum indicators first, then additional categories, all consumable from Python through one consistent API  
**Completion tracking:** Check off each task as it is finished. Mark a sprint with ✓ only after its acceptance criteria pass.

> Note 1: This is the development plan for the first project milestone: the public, open-source PyTA library. It is a backbone project that other projects are built on top of, so everything here is about the library itself.

> Note 2: PyTA has no dependency on any data provider. It supports the data types that providers return: yFinance returns pandas DataFrames and Series, tuples, and dicts; AlphaVantage returns JSON and CSV. Testing may use yFinance-shaped data, but PyTA never imports a provider.

---

## Guiding principles

1. **Build a vertical slice first.** Each sprint should produce something that runs and can be tested, not just scaffolding.
2. **Rust owns the calculations.** Indicator formulas, numerical processing, concurrency, and performance-critical work live in Rust.
3. **Python owns the user experience.** Python accepts the user's container, cleans, validates, and normalizes it, sends clean arrays to Rust, and returns results in the same kind of container. Users should never have to convert to a container type they didn't choose.
4. **Concurrency is transparent.** Users never need `asyncio` or threads. The engine chooses between direct execution, sequential batches, and Rayon-parallel batches, so concurrency overhead is only paid when it helps.
5. **Test from the outside.** A separate project (`PyTA-Integration`) verifies PyTA from an external user's point of view.
6. **Correctness before optimization.** Establish trusted results and benchmarks first; every optimization needs a measured justification.
7. **One shared architecture.** New indicators fit the existing crates, engine, and Python call path rather than requiring new infrastructure.
8. **Helpful errors.** Use built-in exceptions wherever possible, and always explain what went wrong and how to fix it.

---

## Sprint 0 — Development environment and repository foundations

**Goal:** Establish a reproducible development environment before writing indicator code.

### Tasks

- [x] Confirm `rustup` is installed and the stable Rust toolchain is active.
- [x] Install and verify `rustfmt` and `clippy`.
- [x] Create and activate the root Python virtual environment, `.venv`.
- [x] Install Python development dependencies, including Maturin and pytest.
- [x] Configure Visual Studio Code / Code OSS to use the project virtual environment and Rust Analyzer.
- [x] Create the initial repository structure.
- [x] Add `.gitignore`, a README, and basic project documentation directories.
- [x] Initialize or verify Git and commit the clean starting point.
- [x] Verify Rust, Cargo, Python, pip, Git, and Maturin versions.

### Acceptance criteria

- The development environment works from a fresh terminal.
- Python commands use the intended virtual environment.
- Rust commands use the intended rustup-managed toolchain.
- Generated build artifacts and virtual-environment files are excluded from Git.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 1 — Rust workspace and Python packaging skeleton

**Goal:** Create the smallest valid mixed Rust/Python project that builds and imports.

### Tasks

- [x] Create the root `Cargo.toml` as the Rust workspace manifest, with crates under `rust/crates/`.
- [x] Create the initial crates: `pyta-core`, `pyta-engine`, `pyta-momentum`, `pyta-trend`, and `pyta-python`.
- [x] Configure shared dependency versions and workspace settings.
- [x] Add `rust-toolchain.toml` to pin the selected stable toolchain policy.
- [x] Configure the root `pyproject.toml` for Maturin and the `python/pyta/` source layout.
- [x] Add a minimal PyO3 extension module, installed as `pyta._native`.
- [x] Build and install the package into the development virtual environment.
- [x] Import `pyta` from Python.
- [x] Add a minimal automated build/import smoke test.

### Acceptance criteria

- `cargo check --workspace` succeeds.
- `cargo fmt --all -- --check` succeeds.
- `cargo clippy --workspace --all-targets` succeeds without unresolved warnings that violate project policy.
- Maturin builds the extension successfully.
- Python can import `pyta` and call a minimal native function.
- The package does not require manually copying a compiled extension into the Python source directory.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 2 — Core data contracts and numerical conventions

**Goal:** Establish the shared contracts every indicator follows.

### Tasks

- [x] Define the Rust input types: `Series` (non-empty, finite) and `Ohlcv` (aligned series).
- [x] Define the output type, `IndicatorOutput`, with `NaN` marking positions with no valid result.
- [x] Establish the missing-value and warm-up conventions (output length equals input length; warm-up is `NaN`).
- [x] Define behavior for empty input, insufficient input, invalid parameters, and non-finite values.
- [x] Implement shared input validation in `pyta-core`.
- [x] Define error handling between Rust and Python (`ValueError` for invalid input, `RuntimeError` for internal failures).
- [x] Establish a reference-test format for comparing numerical outputs.
- [x] Document the public API and numerical conventions.

### Acceptance criteria

- Input validation is shared instead of being reimplemented independently for every indicator.
- Invalid inputs produce predictable errors.
- Numerical behavior is documented and testable.
- The API can accommodate additional indicators without changing the foundational data contracts.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 3 — First indicator: Simple Moving Average (Trend)

**Goal:** Deliver one complete indicator through the Rust-to-Python interface.

**Indicator:** Simple Moving Average (SMA) in the `pyta-trend` crate.

### Tasks

- [x] Implement the SMA calculation in Rust.
- [x] Add unit tests for known values and hand-calculated examples.
- [x] Test warm-up periods, short inputs, empty inputs, and invalid window sizes.
- [x] Compare results against an independent reference implementation.
- [x] Expose SMA through the PyO3 extension.
- [x] Add a Python-facing API with clear parameter names and documentation.
- [x] Add Python tests for output shape, values, and errors.
- [x] Document the indicator's formula and output conventions.

### Acceptance criteria

- SMA is calculated in Rust, not reimplemented in Python.
- Rust and Python tests pass.
- Results match the reference within the defined numerical tolerance.
- The indicator can be called using the intended public API.
- The behavior for warm-up values is explicitly documented.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 4 — Second indicator: Relative Strength Index (Momentum)

**Goal:** Prove that the architecture supports a separate indicator category without duplicating infrastructure.

**Indicator:** Relative Strength Index (RSI) in the `pyta-momentum` crate.

### Tasks

- [x] Implement RSI in Rust using Wilder's smoothing.
- [x] Document the RSI formula and the exact smoothing method.
- [x] Define behavior for flat prices, all-gain inputs, all-loss inputs, and insufficient history.
- [x] Add unit tests for hand-calculated and reference results.
- [x] Compare output against a trusted independent implementation using matching settings.
- [x] Expose RSI through the Python extension.
- [x] Add Python tests for expected values, output shape, and errors.
- [x] Confirm the RSI and SMA APIs share the same core input and error contracts.

### Acceptance criteria

- RSI is calculated in Rust.
- Tests cover edge cases and numerical conventions.
- SMA and RSI work through the same Python package.
- Adding RSI has not required duplicating the core validation or packaging architecture.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 5 — Python API layer

**Goal:** Let users pass whatever container they have and get the same kind of container back.

### Tasks

- [x] Support `list`, `tuple`, NumPy array, pandas Series and DataFrame, `dict` of columns, and JSON (`str` and `bytes`) as input.
- [x] Restore the result in the caller's container type, with the input's index and `<indicator>_<period>` naming where applicable.
- [x] Implement column selection (`column=`, single-column fallback, `close` aliases, case- and whitespace-insensitive matching, ambiguity rejection).
- [x] Implement the leading-`NaN` skip and re-padding policy so indicators can be chained.
- [x] Treat `None` and JSON `null` as gaps.
- [x] Validate parameters (including `period` type and range) with Pydantic, never per element.
- [x] Release the GIL at the native boundary.
- [x] Add type stubs and `py.typed`.
- [x] Add Python tests for every container, the NaN policy, and error cases.
- [x] Add a Python-boundary benchmark that separates Python-layer cost from native cost.

### Acceptance criteria

- Every supported container round-trips to the same container type.
- Python cleans and validates; Rust never receives non-finite or malformed data.
- `import pyta` does not import pandas.
- Indicator formulas are not reimplemented in Python.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 6 — Indicator engine and execution paths

**Goal:** Introduce a unified engine that runs one dataset directly or many datasets concurrently, paying concurrency overhead only when it helps.

### Tasks

- [x] Define a common indicator request model.
- [x] Implement dispatch from the engine to the appropriate indicator crate.
- [x] Implement the direct path (`execute_direct`) for a single dataset, with panics caught and returned as errors.
- [x] Implement the batch path: Rayon `par_iter` (`execute_parallel`), with an async front door (`execute_batch`) for async callers. (Originally Tokio tasks per request; replaced after benchmarks showed Rayon alone was up to 10x faster.)
- [x] Implement the planner that chooses sequential or concurrent execution from estimated cost.
- [x] Define deterministic result ordering and a stable result structure.
- [x] Isolate failures so one failed request never cancels the others.
- [x] Add tests for single requests, mixed-category batches, ordering, and invalid requests.
- [x] Add Criterion benchmarks for the kernel, direct, sequential, batch, and planner paths.

### Acceptance criteria

- The same engine executes one dataset or many.
- SMA and RSI can be requested together.
- Independent calculations execute concurrently without callers coordinating tasks manually.
- Results map back to their requests deterministically.
- A new indicator cannot be added without a dispatch arm and a cost estimate.

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 7 — Batch API in Python

**Goal:** Expose batch execution as one simple call, with no async code for the user.

### Tasks

- [x] Bind `execute_batch` in `pyta-python`, releasing the GIL.
- [x] Add `pyta.batch` mirroring the top-level indicator functions.
- [x] Accept a list or a mapping of datasets, each in any supported container.
- [x] Return results in the same shape and order, each in its own input's container type.
- [x] Return a result for every dataset; a failed dataset is represented by the exception explaining why, in the same position or under the same key.
- [x] Add tests for list and mapping input, mixed containers, ordering, and partial failures.
- [x] Add a Python-level benchmark for batch calls (`benches/python/bench_batch.py`).
- [x] Document the batch API and error policy in `API.md`.
- [x] Benchmark the batch scheduling options (Tokio per request, Tokio one hop, Rayon, chunked Rayon, per-call runtime) and keep the fastest: plain Rayon.
- [x] Make parallel batches safe after `fork()` (own Rayon pool rebuilt in the child; `tests/python/test_fork.py`).

### Acceptance criteria

- `pyta.batch.sma(datasets, period=14)` works with lists and mappings.
- One failing dataset never prevents results for the others, and the failure names the reason.
- Users do not need `asyncio` or threads.
- Batch and single calls share the same Rust kernels and validation.

**Retrospective:** *Worked:* benchmarking the scheduling options before committing to one; replacing Tokio with plain Rayon (up to 10x faster, and simpler); the fork test, which caught the inherited-pool hang. *Didn't:* one benchmark arm was biased, so an early comparison favored the wrong option; the planner still misses near the sequential/parallel break-even. *Next:* real tests (reference data, property tests, coverage, type checking) and a logging system, as Sprint 7.5, before Sprint 8 adds more surface.  
**Sprint completion:** ✓

---

## Sprint 7.5 — Testing foundation and unified logging

**Goal:** Before Sprint 8 adds more surface, bring the tests up to current standards and give PyTA one logging system for its Python and Rust code.

### Tasks: testing to current standards (7.5a)

Rust:

- [x] Add `[workspace.lints]` (`unsafe_code` denied, `missing_docs`, a curated Clippy `pedantic` subset); every crate opts in. Fix what it flags.
- [x] Add `proptest` invariants to `pyta-trend` and `pyta-momentum`: output length, exact warm-up, SMA within its window's range, RSI in [0, 100], constant input.
- [x] Fill `pyta-core/tests/error_tests.rs`.
- [x] Add edge cases per kernel: `period` of 1 and of the series length, huge, tiny and flat values.
- [x] Test that `execute_parallel` and `execute_sequential` give identical results.
- [x] Add reference tests from published worked examples (StockCharts SMA-5, SMA-10 and RSI-14), stored under `tests/fixtures/` with their sources cited and read by both the Rust and Python tests.
- [x] Add `cargo nextest` and `cargo llvm-cov` as optional steps in `scripts/test-suite.sh`.
- [x] Add `cargo deny` (licenses and advisories) as a CI job.

Python:

- [x] pytest: `--strict-markers --strict-config`, warnings as errors, a `pandas` marker, and `pytest-cov` with a coverage floor on the `pyta` package.
- [x] Add `hypothesis` tests for containers and the NaN policy.
- [x] Broaden Ruff to `B, SIM, RUF, PT, PERF, C4, TID` and fix what it flags.
- [x] Type-check `python/` with Pyright in strict mode (chosen over `ty`, which is still a 0.0.x beta).
- [x] Check `_native.pyi` against the compiled module with `mypy.stubtest`.
- [x] Replace the empty `test_trend.py` and `test_momentum.py` with `test_sma.py` and `test_rsi.py`.
- [x] Fill `test_import.py` and the reference tests.

Scripts, CI and docs:

- [x] Update `scripts/test-suite.sh` and `scripts/README.md`.
- [x] CI mirrors the test suite.
- [x] Update `ARCHITECTURE.md` (tests and quality checks).

### Tasks: unified logging (7.5b)

- [x] Rust uses the `log` macros (targets `pyta::engine`, `pyta::planner`, `pyta::bridge`), forwarded to the Python loggers `pyta.engine`, `pyta.planner` and `pyta.bridge` by `pyta-python/src/log_bridge.rs`, installed in the `#[pymodule]`. (`pyo3-log` does not support PyO3 0.30 yet; the bridge stands in for it.)
- [x] Add Python loggers (`pyta.api`, `pyta.validation`) for validation and batch handling.
- [x] Add a `NullHandler` to the `pyta` logger; never configure handlers or levels.
- [x] Apply the level policy: DEBUG for the planner's choice, the worker pool starting or being rebuilt after `fork()`, column resolution and each failed dataset; WARNING for one summary per batch with failures; ERROR for a kernel panic caught by `catch_unwind`; no INFO in normal operation.
- [x] Keep logging out of kernels and per-element loops: log from the calling thread at the boundary, behind a level check. *(Exception: a kernel panic inside a parallel batch logs at ERROR from its worker; panics are bugs.)*
- [x] Keep `pyta-common` and the kernel crates free of `pyo3`; `env_logger` is a dev-dependency for benchmarks.
- [x] Test with pytest `caplog` (Rust and Python messages, levels, silence by default, only a `NullHandler`), in a forked child, and in Rust (the planner logs its choice).
- [x] Performance gate: single-call cost with logging disabled stays within noise of the baseline. *(Same-session A/B against `main`, 2026-10-28: `--single --python` and `--batch --python` twice each, plus an interleaved best-of-5 microbenchmark: single and batch calls within ±0.6%.)*
- [x] Document logging in `ARCHITECTURE.md`, `API.md` and the README.

### Acceptance criteria

- No empty placeholder test files remain, and SMA and RSI have reference tests from cited published examples.
- `scripts/test-suite.sh` passes, including lint, type check, coverage floor and stub check, and CI mirrors it.
- `logging.getLogger("pyta").setLevel(DEBUG)` shows Rust and Python messages in one stream; with no configuration the library emits nothing and adds only a `NullHandler`.
- Benchmarks show no regression beyond noise.

**Retrospective:** *Worked:* one logging system for Rust and Python at no measurable cost (same-session A/B against `main`, within ±0.6%); property tests earned their place at once, when Hypothesis found RSI rounding to `100.00000000000001`; published reference examples stored once in `tests/fixtures/` and checked by both languages; real SPY OHLCV as test input. *Didn't:* the sprint was first ticked done with almost nothing built, because two sessions shared one checkout (now one worktree per task); CI broke twice on things a local run could not show (a `setup-uv` tag that does not exist, and `uv run --with maturin` installing into a throwaway environment); StockCharts publishes its examples only as rounded images, so the RSI reference needs a 0.1 tolerance. *Next:* Sprint 8 category namespaces, with the test suite and CI as the gate for every change.  
**Sprint completion:** ✓

---

## Sprint 8 — Category namespaces

**Goal:** Let users call indicators by category or by short-hand name.

> Note: Indicator modules live in category subpackages (`pyta/indicators/<category>/<name>.py`), and `pyta/batch/` is a package mirroring the category namespaces. The convention for a new category is in `ARCHITECTURE.md` §5, "Adding a category".

### Tasks

- [x] Decide the category layout for the indicator modules. *(2026-10-28: category subpackages, `pyta/indicators/<category>/<name>.py`, with thin `pyta/<category>.py` re-exports; see `.claude/memory.md`.)*
- [x] Expose category namespaces: `pyta.trend` and `pyta.momentum`.
- [x] Keep short-hand names (`pyta.sma`) pointing at the same implementation.
- [x] Mirror the namespaces under `pyta.batch`, turning `pyta/batch.py` into a package (`pyta.batch.trend`, `pyta.batch.momentum`).
- [x] Define the convention for adding a new category namespace. *(`ARCHITECTURE.md` §5, "Adding a category"; guarded by `tests/python/test_namespaces.py`.)*
- [x] Add tests confirming both styles return identical results.
- [x] Update `API.md` to mark the namespaces available. *(§2 and §9.)*

### Acceptance criteria

- `pyta.trend.sma` and `pyta.sma` call the same function.
- Importing the whole package or a single category both work.
- Adding a category does not change existing imports.

**Retrospective:** *Worked:* category subpackages with thin re-exports, so `pyta.trend.sma`, `pyta.indicators.sma` and `pyta.sma` are one function object and nothing was duplicated; `git mv` kept each module's history; `test_namespaces.py` guards the layout rule, the documented import paths and the no-pandas import, so a new category cannot quietly break them; the first sprint run in its own worktree and merged locally after review. *Didn't:* the branch started behind `main` and had to catch up before work began; `main` moved during review, so the merge needed `--no-ff` instead of a fast-forward; CI did not run before the merge; `import pyta.indicators.trend.sma as m` binds the function rather than the module, because they share a name (documented, not fixed). *Next:* Sprint 9 multi-column (OHLCV) input; start each task's worktree from the current `main`, and push to let CI run before closing a sprint.  
**Sprint completion:** ✓

---

## Sprint 9 — Multi-column input (OHLCV)

**Goal:** Let users pass full OHLCV data and have PyTA find what each indicator needs.

### Tasks

- [x] Grow `IndicatorRequest` from a single `Series` to multi-column input: a generic `Columns` type (equal-length columns in the indicator's slot order) replaces the unused `Ohlcv`.
- [x] Validate the design with CCI (high, low, close), the first multi-column indicator.
- [x] Find each column's role by name, using the existing role and alias rules (`open`, `high`, `low`, `close`, `adj_close`, `volume`; case, whitespace and `. _ -` ignored).
- [x] Give each multi-column indicator named slots for the columns it needs. A slot may accept several roles (for example `close` or `adj_close`).
- [x] Ignore columns an indicator does not need.
- [x] Support an explicit `columns=[...]` override, in any order: each name is assigned to the indicator's slot for its role. An unrecognized name, a duplicate role, or a missing slot raises `ValueError`.
- [x] Keep the role registry extensible (not hard-coded to OHLCV), so fundamental roles such as `eps`, `book_value`, `sales`, `dividends`, and `ebitda` can be added for valuation indicators without redesigning it.
- [x] Raise a `ValueError` that names the required columns and the available columns when a role cannot be found.
- [x] Return results in the input's container type.
- [x] Add tests across every supported container, including extra columns and overrides.
- [x] Update `API.md` and `ARCHITECTURE.md`.

### Acceptance criteria

- A user can pass a full OHLCV DataFrame to a multi-column indicator without naming columns.
- Users who don't know which columns an indicator needs get an error that tells them.
- Single-column indicators are unaffected.

**Retrospective:** *Worked:* deciding the two open questions (CCI as the proving indicator, a generic `Columns` type instead of the fixed `Ohlcv`) before any code, so the contract has room for fundamentals and the old struct could go; one role registry and declared slots let every container, `columns=` in any order and the error messages share one path; measuring paid off twice, halving the multi-column Python overhead (36 → 15 µs) and making the CCI kernel 2.1-2.5x faster with compensated window sums, which also fixed a drift a plain running sum showed (a flat window after a large price read -66.7 instead of 0); SMA and RSI stayed within noise in a same-session A/B against `main`. *Didn't:* there was no `--single --python` baseline in `benches/results/`, so `main` had to be benchmarked alongside; CCI's cost constants were provisional until a second pass refitted them; the multi-column Python layer still costs about 12 µs per 100-row call against about 3.8 µs for SMA; CI had not run when the sprint closed. *Next:* Sprint 10 multi-output indicators, validated with MACD; keep a current `--single --python` baseline in `benches/results/`; the multi-column overhead is in the parking lot for Sprint 17.  
**Sprint completion:** ✓

---

## Sprint 10 — Multi-output indicators

**Goal:** Support indicators that produce several series.

### Tasks

- [x] Add the MACD indicator.
- [x] Add the EMA indicator (its kernel also serves MACD).
- [x] Give each indicator its own parameters (`period=` for SMA, RSI, CCI and EMA; `fast=`, `slow=`, `signal=` for MACD).
- [x] Extend the output contract to carry several named series.
- [x] Return outputs in the input's container type: extra columns for DataFrames, extra keys for dicts and JSON objects, a tuple of outputs for a single series.
- [x] Name outputs after the indicator, without parameters (`sma`, `rsi`, `cci`; `macd`, `macd_signal`, `macd_hist`), for every indicator.
- [x] Match output casing to the input's columns (lower, upper, or title case with abbreviations upper), for every indicator.
- [x] Validate the design with MACD.
- [x] Add tests for naming, casing, container types, and warm-up per output.
- [x] Benchmark multi-output indicators and optimize while ensuring calculation accuracy.
- [x] Update documentation (`API.md`, `README.md`, indicator's wiki-doc, `DEVELOPMENT.md`)

### Acceptance criteria

- MACD returns three named outputs in every supported container.
- EMA and MACD match TA-Lib-generated reference values.
- Output names and casing follow the new rules for every indicator.
- Single-output indicators are otherwise unchanged (values, containers, errors, and single-call cost within ~5%).

**Retrospective:** *Worked:* settling every design question (per-indicator `Params`, bare names, casing, one-series tuples, TA-Lib-generated references) before code, then building Rust and Python in two separate, reviewed halves; TA-Lib's own output compared at 1e-9 made EMA and MACD exact rather than approximately right, and a bit-for-bit proptest let the MACD kernel be fused into one pass (2.1-2.3x) without risk; reviews caught EMA(1) not being an exact copy and a casing-cache collision. *Didn't:* the first same-session A/B showed single calls 8-16% slower at 100 rows (Pydantic per call, per-call closures and casing work), which took a second optimization pass to bring back to 0.87-0.95x of `main`; the Python benchmark now passes parameters as `**params`, a small bias, and covers only NumPy input for single-column indicators; EMA and MACD cost constants are still from quick runs. *Next:* Sprint 11 CSV input; confirm the two in-sprint calls (all-capitals words as title case, the Pydantic fast path) and the provisional cost constants with full runs.  
**Sprint completion:** ✓

---

## Sprint 11 — Data containers: CSV input and round-trip conformance

**Goal:** Support the CSV data that AlphaVantage returns; prove that every supported container (pandas, `dict`, `tuple`, JSON and CSV) imports correctly and exports back to the same container, for every indicator shape (one or several input columns, one or several outputs); and let callers convert the result to another container with `output=`.

### Tasks: decide

- [x] **What "export" means.** *(2026-10-29, maintainer's decision.)* By default the output keeps the input's container type, as today (guiding principle 3). A new `output=` option converts the result to another container, for example DataFrame in and JSON out.
- [x] **`output=` design.** *(2026-10-29, maintainer accepted the recommendation; an index goes first in a `dict` or JSON object, dates become ISO 8601 strings, and each target always has its fixed shape.)*
  - `output=None` (the default) keeps the input's container; otherwise one of `"list"`, `"tuple"`, `"numpy"`, `"pandas"`, `"dict"`, `"json"`, `"json_bytes"`, `"csv"`, `"csv_bytes"`. Any other value raises `ValueError` listing the valid names.
  - Names and casing are the same as in the default output.
  - Each target has one fixed shape:
    - `"pandas"` gives a Series for one output and a DataFrame for several.
    - `"dict"` gives one key per output, with NumPy arrays as values.
    - `"json"` and `"csv"` give an object of arrays and a CSV with a header row.
    - Unnamed targets (`"list"`, `"tuple"`, `"numpy"`) give one sequence for one output and a tuple of sequences for several.
  - A pandas index on the input becomes the pandas index, a `dict` key, a JSON field and a CSV column, named after the index (or `index`). It is dropped for unnamed targets.
  - `"pandas"` imports pandas only when asked; if pandas isn't installed, it raises `ModuleNotFoundError` saying to install the `pandas` extra. `import pyta` still never imports pandas.
  - In a batch, `output=` is shared by every dataset, and failures stay in place as exceptions.
- [x] **Container matrix.** Write down which input forms each indicator shape accepts and what each returns, as one table in `API.md` §4, covering every form listed below. Mark each pairing as supported, raising (with which exception), or out of scope. *(2026-10-29: `API.md` §4 "Container matrix" and Limitations, probed against the code; later fixes added (columns, rows) tables, lists of rows and lists of Series.)*

### Tasks: CSV

- [x] Accept CSV (`str` and `bytes`) as input. *(2026-10-29: text starting with `[` or `{` is JSON, anything else CSV; header row required; `,` only. Built 2026-10-29 for single- and multi-column indicators, single and batch.)*
- [x] Return CSV in the same form as the input. *(2026-10-29: header of output names, empty field for `NaN`, shortest `repr`, `\n`; `str` → `str`, bytes → bytes.)*
- [x] Apply the same column selection and NaN policy as other containers. *(2026-10-29: picked like a dict, numbered names such as `1. open` matched; empty field or `NaN` text is a gap, and the same string parser now reads numbers as strings in every container.)*
- [x] Add tests, including headers, missing values, and mixed-case column names. *(2026-10-29: `tests/python/test_csv.py` and property tests; `tests/results/test-suite_2026-10-29_01-34-55.txt` PASSED (Python 640, was 510; Rust 145; coverage 99%).)*

### Tasks: import and export of every container

- [x] **pandas:** Series and DataFrame with a default, date, datetime or non-unique index; nullable dtypes (`Float64`, `Int64` with `pd.NA`); integer and float columns; extra non-numeric columns; title-case (yfinance) and upper-case column names. Output keeps the index, its name and its order, and the casing rule. *(2026-10-29: `tests/python/test_roundtrip.py`; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] **dict:** values as list, tuple, NumPy array or pandas Series, including mixed types in one dict; keys that aren't strings; extra keys; each output value keeps its input column's type. *(2026-10-29: `tests/python/test_roundtrip.py`; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] **tuple:** a tuple of numbers (one series) and a tuple of arrays or lists (unnamed multi-column input, documented order); multi-output results as a tuple of outputs. *(2026-10-29: `tests/python/test_roundtrip.py`; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] **JSON (`str`, `bytes`, `bytearray`):** array of numbers, array of records and object of arrays; `null` gaps; numbers as strings accepted (2026-10-29, maintainer's decision; in every container, not only JSON); names with a numbered prefix (`1. open`) matched without it, in every container; output in the same shape and type, with `null` for `NaN`. *(2026-10-29: `tests/python/test_roundtrip.py`; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] **Round-trip tests:** one parametrized matrix over container × indicator shape (SMA, CCI, MACD, and one multi-column multi-output indicator if one exists by then) checking the output type, length, names and casing, index, and that values equal the NumPy result exactly. *(2026-10-29: `test_roundtrip.py::test_every_container_round_trips_for_every_shape`, 154 cases; the stand-in from `test_multi_output.py` is the multi-column multi-output shape; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] **Hypothesis:** for random valid data, every container gives the same values as the plain NumPy call. *(2026-10-29: two Hypothesis tests in `test_roundtrip.py`, every matrix container including CSV and pandas; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*
- [x] Fix every gap the matrix finds, or record it as a documented limitation in `API.md`. *(2026-10-29: the round-trip tests found no wrong result; the last open gap, unclear messages for a table or one-item container given to a one-column indicator, is fixed in `_validation.py`; the remaining limitations are in `API.md` §4; `tests/results/test-suite_2026-10-29_02-21-17.txt` PASSED (Python 1319, was 1148; Rust 145; coverage 99%).)*

### Tasks: `output=` conversion

- [x] One shared export layer in Python. Each indicator restores from the native result through it, so no indicator has conversion code of its own; `output=None` keeps today's path and cost. *(2026-10-29: `python/pyta/_export.py`, applied by the `_api` runners; `output=None` 1-8% faster than 2dc64a1 at 100 rows, interleaved timeit.)*
- [x] `output=` on every single and batch function (SMA, EMA, MACD, RSI, CCI, and every later indicator through the `add-indicator` skill), in the stubs and docstrings. *(2026-10-29: Python signatures and docstrings with a `Literal` type; `_native.pyi` needs no change, since conversion is Python-only.)*
- [x] Tests: every input container × every `output=` target × indicator shape, checking type, names, casing, the index carried over or dropped, `null` in JSON, an empty CSV field for `NaN`, an invalid target, and `"pandas"` without pandas installed (simulated). *(2026-10-29: `tests/python/test_output.py`; `tests/results/test-suite_2026-10-29_02-01-57.txt` PASSED (Python 1148, was 640; Rust 145; coverage 99%).)*

### Tasks: close

- [x] Same-session A/B against `main`: single and batch calls within ~5% for the containers that existed before. *(2026-10-29, b165f12 vs c51c111, two alternating runs each, governor `performance`: worst ratio 1.030, every row outside ±5% faster; `benches/results/base-b165f12_benchmark_2026-10-29_02-24-53.txt`, `_02-28-04` vs `benchmark_2026-10-29_02-26-27.txt`, `_02-29-38` (single); `base-b165f12_..._02-31-15`, `_02-37-36` vs `_02-34-22`, `_02-40-45` (batch).)*
- [x] Update `API.md` (§4 container matrix, CSV in §12 Data sources) and `ARCHITECTURE.md` if the normalization code changes shape. *(2026-10-29: also §5 "Output conversion" and §9; ARCHITECTURE has `_export.py` and text input.)*

### Acceptance criteria

- CSV in produces CSV out, with the same conventions as JSON.
- Every container in the matrix imports and exports correctly for every indicator shape, proven by the round-trip and Hypothesis tests; every unsupported form raises a clear error.
- `output=` converts any supported input to every target for every indicator, single and batch, and `output=None` behaves exactly as before.
- `API.md` documents the full container matrix and its limitations.
- No provider dependency is added, and existing containers are no slower than on `main`.

**Retrospective:** *What worked:* probing the container matrix against the code before building turned up the gaps early (CSV, numeric strings, numbered names, unnamed multi-column forms), and the round-trip and Hypothesis tests then found no wrong result; `output=` went through one module, and keeping the default path untouched left every existing call within noise of `main` (most small calls 3-9% faster, as the `Prepared` types were unfrozen). *What did not:* implementers could not commit in the sprint worktree, so each part came back on its own branch to fast-forward; text input is slow (CSV 99 µs, JSON records 211 µs for 100 rows), since parsing dominates. *Next:* Sprint 11.5's indicators, with Stochastic as the first real multi-column, multi-output indicator (replacing the stand-in in the matrix tests) and `output=` from the start via the `add-indicator` skill.  
**Sprint completion:** ✓

---

## Sprint 11.5 — The major technical indicators

**Goal:** Ship every major technical indicator before the integration project and the first release, so PyTA can replace TA-Lib for everyday technical analysis.

**Scope:** the technical catalog in `README.md` (24 indicators beyond SMA, EMA, MACD, RSI and CCI). Valuation indicators are not technical and stay in Sprint 16.

| Category | Indicators | TA-Lib function | Shape (inputs → outputs; parameters) |
|---|---|---|---|
| Trend | WMA, DEMA, TEMA, KAMA | `WMA`, `DEMA`, `TEMA`, `KAMA` | close → 1; `period` |
| Trend | ADX | `ADX` (+`PLUS_DI`, `MINUS_DI`) | high, low, close → 3 (`adx`, `adx_plus_di`, `adx_minus_di`); `period` |
| Trend | Parabolic SAR | `SAR` | high, low → 1; `acceleration`, `maximum` (floats) |
| Trend | Aroon | `AROON` (+`AROONOSC`) | high, low → 3 (`aroon_up`, `aroon_down`, `aroon_osc`); `period` |
| Trend | Ichimoku Cloud | none | high, low, close → 5; `tenkan`, `kijun`, `senkou` |
| Momentum | Stochastic | `STOCH` | high, low, close → 2 (`stoch_k`, `stoch_d`); `k`, `k_smooth`, `d` |
| Momentum | Williams %R | `WILLR` | high, low, close → 1; `period` |
| Momentum | ROC | `ROC` | close → 1; `period` |
| Momentum | MFI | `MFI` | high, low, close, volume → 1; `period` |
| Momentum | TRIX | `TRIX` | close → 1; `period` |
| Momentum | Ultimate Oscillator | `ULTOSC` | high, low, close → 1; `short`, `medium`, `long` |
| Volatility | ATR | `ATR` | high, low, close → 1; `period` |
| Volatility | Bollinger Bands | `BBANDS` | close → 3 (`bbands_upper`, `bbands_middle`, `bbands_lower`); `period`, `k` (float) |
| Volatility | Keltner Channels | none | high, low, close → 3; `period`, `atr_period`, `k` (float) |
| Volatility | Donchian Channels | none | high, low → 3; `period` |
| Volatility | Standard Deviation | `STDDEV` | close → 1; `period`, `k` (float) |
| Volume | OBV | `OBV` | close, volume → 1; none |
| Volume | VWAP | none | high, low, close, volume → 1; none (cumulative) |
| Volume | Accumulation/Distribution | `AD` | high, low, close, volume → 1; none |
| Volume | Chaikin Money Flow | none | high, low, close, volume → 1; `period` |
| Volume | Volume ROC | `ROC` on volume | volume → 1; `period` |

The shapes are a starting point; each indicator's spec (the `add-indicator` skill) confirms them against TA-Lib's source before code.

### Tasks: decisions before code

- [x] Confirm the scope above, and whether to add other widely used indicators (candidates: Stochastic RSI, PPO, Momentum, CMO, Hull MA, Supertrend, Pivot Points). *(2026-10-29, user: scope as listed; no extra indicators this sprint, the candidates go to the parking lot. Research found no formal standard for any of the 24, so TA-Lib's calculation is the rule; `TODO.md` Part A.)*
- [x] **Indicator with no parameters** (OBV, A/D, VWAP): confirm the per-indicator `Params` handles an empty set, and that their bare output names (`obv`, `ad`, `vwap`) need no change to the naming rule. *(2026-10-29: unit `Params` variants already work; names unchanged.)*
- [x] **Float parameters** (SAR's `acceleration`/`maximum`, Bollinger's and Keltner's `k`): finite and positive validators beside the integer ones; extend the shared validators, not one per indicator. *(2026-10-29: `Params` drops `Eq`; shared float validators.)*
- [x] **Moving-average type** (TA-Lib's `matype` on BBANDS and STOCH): *recommended:* TA-Lib's default (SMA) only, with an `ma=` option in the parking lot; the alternative is `ma="sma" | "ema" | "wma" | ...`, reusing this sprint's kernels. *(2026-10-29, user: SMA only.)*
- [x] **Defaults:** TA-Lib's defaults unless the original author's standard differs and is what users expect. *Recommended exception:* Bollinger Bands `period=20, k=2` (TA-Lib's default period is 5). List every exception in the indicator's wiki page. *(2026-10-29, user: TA-Lib 0.8.3 now defaults BBANDS to 20, so no exception there; the one exception is Stochastic 14/3/3 (TA-Lib 5/3/3). `TODO.md` A2.)*
- [x] **Ichimoku displacement:** the spans are drawn 26 rows ahead and the lagging span 26 behind, which breaks "output length equals input length". *Recommended:* return each line on the row it is calculated from (unshifted) and document the plotting shift; the alternative is shifting within the input length and dropping what falls off. *(2026-10-29, user: unshifted.)*
- [x] **VWAP anchoring:** *recommended:* cumulative from the first row of the input (the caller slices per session); session or date anchoring needs a datetime role and goes to the parking lot. *(2026-10-29, user: as recommended.)*
- [x] **Negative volume:** *recommended:* a Python row check (like high not below low) rejects negative volume for any indicator with a `volume` slot. *(2026-10-29, user: as recommended.)*
- [x] **References for indicators TA-Lib lacks** (Ichimoku, Keltner, Donchian, VWAP, CMF): the original author's formula and a cited published example, or values generated by a second library in a throwaway env (as TA-Lib's are); decide per indicator in its spec. *(2026-10-29, user: Keltner from PyTA's EMA and ATR plus a hand table; Donchian from TA-Lib `MAX`/`MIN`; Ichimoku, VWAP, CMF hand-computed tables and StockCharts examples where published.)*
- [x] **Ordering and parallel work:** shared registration files (`IndicatorKind`, `costs.rs`, `lib.rs`, the `__init__.py` exports, README) mean two implementers can't add indicators at once without conflicts. *Recommended:* one category at a time, each indicator on its own reviewed branch, merged into the sprint branch in turn. *(2026-10-29, user: as recommended; infrastructure first, then Volatility, Trend, Momentum, Volume.)*

### Tasks: infrastructure

- [x] `pyta-volatility` and `pyta-volume` crates, `pyta.volatility` and `pyta.volume` namespaces (single and batch), wiki folders, following `ARCHITECTURE.md` §5 "Adding a category".
- [x] Float and empty parameter sets in Rust `Params` and the Python validators (per the decisions above).
- [x] Shared kernels where several indicators need the same building block (rolling highest/lowest, true range, Wilder smoothing, typical price, rolling standard deviation), in the crate that owns the concept, with no duplicated formulas.
- [x] One TA-Lib run in a throwaway env generates reference fixtures for every TA-Lib indicator in the sprint from `tests/fixtures/ohlcv_daily.csv`, citing the TA-Lib version.

### Tasks: indicators (one at a time, `add-indicator` skill, standard workflow below)

- [x] Trend: WMA, DEMA, TEMA, KAMA, ADX, Parabolic SAR, Aroon, Ichimoku Cloud. *(2026-10-29, `TODO.md` Part D: each through the `add-indicator` steps on its own branch; passing test-suite reports `test-suite_2026-10-29_07-27-23.txt` (WMA), `_07-38-54` (DEMA), `_07-44-46` (TEMA), `_08-01-22` (KAMA), `_11-26-56` (ADX), `_11-49-24` (Parabolic SAR), `_12-01-28` (Aroon), `_12-16-05` (Ichimoku Cloud). Cost constants provisional from quick runs, confirmed in Part G.)*
- [x] Momentum: Stochastic, Williams %R, ROC, MFI, TRIX, Ultimate Oscillator. *(2026-10-29, `TODO.md` Part E: each through the `add-indicator` steps on its own branch; passing test-suite reports `test-suite_2026-10-29_12-32-22.txt` (Stochastic), `_16-19-35` (Williams %R), `_16-30-28` (ROC), `_16-54-36` (MFI), `_17-04-43` (TRIX), `_17-18-39` (Ultimate Oscillator). Cost constants provisional from quick runs, confirmed in Part G.)*
- [x] Volatility: ATR, Bollinger Bands, Keltner Channels, Donchian Channels, Standard Deviation. *(2026-10-29, `TODO.md` Part C: each through the `add-indicator` steps on its own branch; passing test-suite reports `test-suite_2026-10-29_03-33-50.txt` (ATR), `_06-28-17` (STDDEV), `_06-43-11` (BBANDS), `_06-56-46` (Donchian), `_07-12-29` (Keltner). Cost constants provisional from quick runs, confirmed in Part G.)*
- [x] Volume: OBV, VWAP, Accumulation/Distribution, Chaikin Money Flow, Volume ROC. *(2026-10-30, `TODO.md` Part F: each through the `add-indicator` steps, one commit each on the implementer branch; passing test-suite reports `test-suite_2026-10-29_17-35-59.txt` (OBV), `_17-42-36` (A/D), `_17-50-23` (CMF), `_21-15-26` (VWAP), `test-suite_2026-10-30_09-45-54.txt` (Volume ROC, with the single-column negative-volume check). Cost constants provisional from quick runs, confirmed in Part G.)*

### Tasks: close

- [x] Cost constants for every new indicator from quick benchmarks, confirmed by one full `--single --rust` and `--batch --rust` run at the end.
- [x] Same-session A/B against `main`: existing indicators' single and batch calls within ~5%.
- [x] Update `README.md` (catalog), `API.md` (catalog, parameters, float parameters), `ARCHITECTURE.md` (new crates and shared kernels), and one wiki page per indicator.

### Acceptance criteria

- Every indicator in scope is available as `pyta.<name>`, `pyta.<category>.<name>` and `pyta.batch.<name>`, in every supported container, with its wiki page.
- Every TA-Lib indicator matches TA-Lib-generated values exactly (1e-9); every other one matches its cited reference within the stated tolerance.
- Each indicator has edge-case and property tests, and passes the indicator completion rule.
- No indicator adds engine special cases or per-indicator execution infrastructure.
- Existing indicators are unchanged, and their single-call cost stays within ~5% of `main`.
- `./scripts/test-suite.sh` passes.

**Retrospective:** *What worked:* settling the formula rule (a standard where one exists, else TA-Lib 0.8.3) and every shape, default and zero-denominator convention in Part A before code; shared kernels in `pyta-core` built first, so 24 indicators added no engine special cases and reused one EMA, Wilder, true-range, rolling-extreme and ROC implementation; fixtures generated by TA-Lib itself, so most match bit for bit and the rest within 4e-13 relative (`test-suite_2026-10-30_17-09-08.txt`: 600 Rust, 2561 Python tests; a DataFrame of the SPY data through every TA-Lib fixture matched to 1e-13); existing indicators stayed within noise of `main` in a same-session A/B (`benches/results/base-53a49af_*` against `benchmark_2026-10-30_09-53-59` to `_17-02-49`). *What did not:* usage limits cut off several implementers mid-task, and agents could not download TA-Lib's source; TA-Lib's wheel fuses `fma` in some functions (SAR, TRIX) but not others (KAMA), so bit parity needs a policy still open; scaling 1,000,000-row kernel times against RSI overstated cheap kernels where the planner decides (A/D ran small batches in parallel 1.8-1.9x slower until its constant was set from the batch rows); the benchmark report's first summary missed five flagged planner rows. *Next:* Sprint 12's integration project against the full catalog; decide the parked numeric calls (fma policy, ROC's ±inf on a tiny base, Aroon's 100 + 1 ulp) at QA.  
**Sprint completion:** ✓

---

## Sprint 12 — Independent integration project

**Goal:** Validate PyTA from the perspective of an external consumer.

**Project:** `PyTA-Integration/`, a testing project with its own `pyproject.toml` and virtual environment.

Order matters: the numeric decisions can change outputs and kernel speed, so they come before the cost refit, and all three come before any expected value or timing is recorded in the integration project. The TA-Lib comparison needs the installed package and the final kernels, and the checks and documentation come last because they cover everything above.

### Tasks: numeric decisions (in PyTA)

- [ ] Decide the bit-parity policy against TA-Lib 0.8.3: within 1e-9 everywhere (current), or bit for bit, using `f64::mul_add` where TA-Lib's wheel fuses (`TA_FMA_MULTIVERSION`: SAR, TRIX, the EMA family; KAMA's build does not). This settles the fma policy; evidence is in `TODO.md`'s parking lot.
- [ ] Under that policy, decide the other parked numeric calls (ROC's ±inf on a tiny base, inherited by Volume ROC; Aroon's 100 + 1 ulp), then implement every decision with tests, fixtures and docs.
- [ ] Refit cost constants from the batch rows where the planner decides (10 x 1,000 and 100 x 100), not by scaling a kernel's 1,000,000-row time against RSI's, which overstates cheap memory-bound kernels: SMA (+29%), CCI (+25%), STDDEV's period term (sweep), WMA's 100 x 100 row (1.16x). After the numeric changes, since `mul_add` changes kernel times.

### Tasks: integration project

- [ ] Create the separate integration repository or sibling project directory.
- [ ] Create an independent Python virtual environment.
- [ ] Install PyTA as a built or locally installed package, never by importing its source files.
- [ ] Add examples for SMA and RSI using a pandas DataFrame shaped like yFinance output.
- [ ] Add examples using AlphaVantage-shaped JSON and CSV.
- [ ] Add an example of a batch call across several datasets.
- [ ] Add integration tests for expected values, invalid parameters, and error messages.
- [ ] Benchmark PyTA against TA-Lib (PyPI `TA-Lib`, installed in the integration project's environment only, never a PyTA dependency) for every indicator both have, calling each library the way its documentation shows for normal production use and timing the whole call (input conversion and output wrapping included). Time each pair with `timeit` (`Timer.repeat`, best of at least 5 repeats, the two libraries interleaved in the same session, the same data) and record µs per call for each, the ratio (TA-Lib time / PyTA time) and the largest output difference. Two comparisons:
  - **Single indicator:** one dataset per call, `talib.<NAME>(...)` against `pyta.<name>(...)`, on float64 NumPy arrays and on a yFinance-shaped pandas DataFrame, at 100, 10,000 and 1,000,000 rows.
  - **Batch:** the same indicators over many datasets. TA-Lib has no batch call, so its production form is a Python loop calling `talib.<NAME>` per dataset; PyTA's is one `pyta.batch.<name>(...)` call over the list. Shapes as the batch benchmarks: 10 x 1,000, 100 x 100, 100 x 10,000 and 1,000 x 1,000 (datasets x rows).
- [ ] Add both tables to PyTA's `README.md` with the machine, CPU governor and date; list the indicators TA-Lib lacks (Ichimoku, Keltner, Donchian, CMF, VWAP, Volume ROC) as having no comparison.
- [ ] Verify that the project does not depend on PyTA's internal crate paths or `pyta._native`.
- [ ] Document how a new developer installs and runs the examples, tests and benchmark.

### Acceptance criteria

- The bit-parity policy and the parked numeric calls are decided, implemented and documented.
- The integration project installs and imports PyTA independently.
- All example workflows run successfully.
- Integration tests pass against the installed package.
- The public API works without access to the PyTA source tree.
- A package build can be tested from a clean environment.
- `README.md` has single-indicator and batch `timeit` comparisons with TA-Lib for every indicator both libraries have, reproducible from the integration project.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 13 — Quality gates, documentation, and first release candidate

**Goal:** Turn the initial proof of concept into a dependable baseline.

### Tasks

- [ ] Add CI checks for formatting, linting, compilation, and tests.
- [x] Write the `README.md`, `ARCHITECTURE.md`, `API.md`, and `DEVELOPMENT.md`.
- [x] Add basic benchmarks for SMA, RSI, and the execution paths.
- [ ] Run the full Rust unit-test suite.
- [ ] Run the Python unit, reference, and integration test suites.
- [ ] Test package builds in a clean environment.
- [ ] Keep `API.md` current as planned features land.
- [ ] Record baseline latency and throughput for representative input sizes.
- [ ] Review error messages so every raised exception explains its cause.
- [ ] Review public API naming.
- [ ] Tag the initial milestone once all acceptance criteria pass.

### Acceptance criteria

- All required automated checks pass.
- An external user can install the package and follow the documentation.
- Baseline benchmarks are reproducible and recorded.
- Numerical conventions and limitations are documented.
- The project has a stable foundation for adding more indicators.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 14 — Release to PyPI

**Goal:** Make "no compiler required" true for users.

### Tasks

- [ ] Confirm the release workflow builds prebuilt wheels for every supported platform on Python 3.15 or later.
- [ ] Test installing the wheels in a clean environment with no Rust toolchain or compiler.
- [ ] Publish to TestPyPI and verify installation from it.
- [ ] Publish to PyPI.
- [ ] Update the README installation section.
- [ ] Remove the "active development" warning from the README once the release is stable.

### Acceptance criteria

- `pip install pyta` works on every supported platform without a compiler.
- The released version passes the integration project's tests.
- The README and `API.md` match the released behavior.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 15 — Indicators beyond the major set

**Goal:** Add the less common technical indicators after the first release, without redesigning the infrastructure. The major ones ship in Sprint 11.5.

### Tasks

- [ ] List candidates not covered by Sprint 11.5: the rest of TA-Lib's overlap, momentum, volatility and volume functions (for example PPO, CMO, Momentum, Stochastic RSI, ADXR, Chaikin Oscillator, NATR, T3, MAMA), widely used non-TA-Lib indicators (Hull MA, Supertrend, Pivot Points, Chandelier Exit), and anything parked during Sprint 11.5 (an `ma=` option, anchored VWAP).
- [ ] SAREXT (TA-Lib `TA_SAREXT`, maintainer's request 2026-10-30): the extended Parabolic SAR, with separate acceleration start, step and maximum for long and short positions, a start value and a reversal offset; build it on the Sprint 11.5 SAR kernel and check it against TA-Lib-generated fixtures like the other TA-Lib indicators.
- [ ] Rank them by user demand, implementation complexity and validation requirements, and agree the list with the maintainer.
- [ ] Add one indicator at a time using the standard workflow below.
- [ ] Add formula documentation, reference tests, and edge-case tests for each indicator.
- [ ] Add each indicator to dispatch, the cost estimates, direct execution, and batch execution.
- [ ] Update the integration project's coverage.
- [ ] Measure performance against the recorded baseline.

### Acceptance criteria

- Each added indicator passes its own correctness and edge-case tests.
- Existing indicator behavior remains unchanged.
- No new per-indicator execution infrastructure is required.
- Documentation and integration coverage stay current.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 16 — Valuation category

**Goal:** Add valuation indicators, price-relative and fundamental, as their own category. Volatility and Volume are built in Sprint 11.5.

### Tasks

- [ ] Build the price-relative and fundamental indicators in the [Valuation plan](#valuation-plan) below.
- [ ] Register the fundamental roles (`eps`, `book_value`, `sales`, `dividends`, `ebitda`, ...) with `register_role`, as the Sprint 9 registry allows.
- [ ] Reuse the shared core and engine contracts.
- [ ] Add each indicator to batch execution.
- [ ] Expand integration tests.
- [ ] Review cross-category naming, parameter conventions, and output consistency across all five categories.

### Acceptance criteria

- The Valuation category integrates with the same public Python interface.
- Core behavior is consistent across categories.
- New indicators have numerical reference tests and documented edge cases, including look-ahead rules for fundamentals.
- The engine does not accumulate category-specific special cases.

**Retrospective:**  
**Sprint completion:** ☐

---

### Valuation plan

Valuation indicators come in three kinds, and only the first two belong in PyTA.

| Kind | Indicators | Inputs | When |
|---|---|---|---|
| Price-relative | Mayer Multiple, Z-Score | Price only | With the first Valuation work; uses the existing single-series API |
| Fundamental multiples | P/E (TTM), Earnings Yield, P/B, P/S, Dividend Yield, EV/EBITDA, PEG | Price plus per-share fundamentals | After Sprint 9 (multi-column input) |
| Absolute models | DCF, DDM, Residual Income, Justified P/E, Comparables, CAPE | Forecasts, discount rates, peer sets, CPI history | *Future*; single values from assumptions, not time series |

#### Tasks

- [ ] Create the `pyta-valuation` crate and the `pyta.valuation` namespace.
- [ ] Mayer Multiple: `mayer_multiple(data, period=200)` = price ÷ SMA(`period`). Reuse the SMA kernel. Document the 2.4 / 0.8 bands as Bitcoin-calibrated conventions, not rules.
- [ ] Z-Score: `zscore(data, period)` = (price − rolling mean) ÷ rolling standard deviation. Decide population vs sample standard deviation and document it. A zero standard deviation gives `NaN`.
- [ ] Ratio kernel shared by the fundamental multiples: element-wise division, with a zero or negative denominator giving `NaN` (P/E is undefined for losses). Earnings Yield (EPS ÷ price) stays defined for negative earnings.
- [ ] Align fundamentals to prices in Python with an as-of join (carry the last published value forward), using NumPy `searchsorted` on `datetime64` so pandas stays optional. Inputs without an index must already be aligned.
- [ ] TTM: decide whether callers pass trailing-twelve-month values or PyTA provides a `ttm()` helper (sum of the last four quarters).
- [ ] EV/EBITDA: EV = market cap + debt + preferred + minority interest − cash. Decide whether to accept EV directly or its components.
- [ ] PEG: P/E ÷ growth rate, with growth supplied by the caller. Never estimate it.
- [ ] Output names follow the bare-name rule from Sprint 10 (`mayer_multiple`, `zscore`, `pe`, `pb`, `ev_ebitda`), with casing from the input's columns.

#### Rules

- **No look-ahead bias.** Fundamentals must be dated by when they were published (filing date), not by fiscal period end. PyTA can't infer filing dates, so the API docs must state this requirement for every fundamental indicator.
- PyTA never fetches fundamentals; it only accepts them (see Note 2 at the top of this plan).

---

## Sprint 17 — Performance tuning

**Goal:** Keep the engine fast as the library grows, using measurement rather than assumption.

### Tasks

- [ ] Benchmark the expanded library using realistic workloads and data sizes.
- [ ] Profile time spent in calculation, scheduling, input conversion, and output conversion.
- [ ] Re-measure the planner's cost estimates for every new indicator.
- [ ] Tune the sequential-versus-concurrent decision and batch concurrency limits against the baseline.
- [ ] Add regression benchmarks for any adopted optimization.

### Acceptance criteria

- Each optimization has a measured justification.
- Numerical correctness is preserved.
- Performance improvements are demonstrated against the recorded baseline.

**Retrospective:**  
**Sprint completion:** ☐

---

## Standard workflow for every new indicator

Once the first two indicators are complete, each additional indicator follows the same lightweight cycle.

- [ ] Define the formula, parameters, and numerical conventions.
- [ ] Write reference and edge-case tests.
- [ ] Implement the calculation in its category crate.
- [ ] Validate Rust results against the reference.
- [ ] Add engine dispatch and a benchmarked cost estimate (a named constant in `pyta-common`'s `costs.rs`).
- [ ] Expose the indicator through the Python package (short-hand and category namespace).
- [ ] Add the batch variant.
- [ ] Test every supported container type.
- [ ] Add external integration coverage.
- [ ] Update documentation.
- [ ] Run the full regression suite and benchmarks where appropriate.

**Indicator completion rule:** An indicator is not complete merely because its formula returns numbers. It is complete when its correctness, error behavior, Python API, batch access, documentation, and regression tests all pass.

---

## Sprint tracking rules

1. Start each sprint by confirming its goal and acceptance criteria.
2. Keep work small enough to review and test independently.
3. Mark a task `[x]` only when its deliverable is finished and verified.
4. Leave a sprint's completion marker as `☐` until every required acceptance criterion passes.
5. Change the sprint marker to `✓` only after verification.
6. If a task reveals an architectural problem, fix the foundation before adding more indicators.
7. At the end of each sprint, fill in the sprint's **Retrospective** line: what worked, what did not, and the next sprint's priorities.
8. Update `ARCHITECTURE.md` and `API.md` in the same change as any code that alters them.

## Definition of done

The initial milestone is achieved when:

- [ ] The Rust workspace builds cleanly.
- [ ] The Python package installs and imports.
- [ ] SMA and RSI produce validated results through every supported container.
- [ ] Single calls run directly, and batch calls run through `pyta.batch` with transparent concurrency.
- [ ] Failures in a batch are reported per dataset with a clear reason.
- [ ] The separate integration project passes its tests.
- [ ] CI, documentation, and baseline benchmarks are in place.
- [ ] The package is published to PyPI and installs without a compiler.

**Initial milestone:** PyTA has proven its end-to-end architecture. From this point onward, the primary development work becomes adding and validating indicators rather than repeatedly rebuilding the foundation.
