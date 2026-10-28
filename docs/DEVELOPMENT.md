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

**Retrospective:**  
**Sprint completion:** ✓

---

## Sprint 8 — Category namespaces

**Goal:** Let users call indicators by category or by short-hand name.

### Tasks

- [ ] Expose category namespaces: `pyta.trend` and `pyta.momentum`.
- [ ] Keep short-hand names (`pyta.sma`) pointing at the same implementation.
- [ ] Mirror the namespaces under `pyta.batch`.
- [ ] Define the convention for adding a new category namespace.
- [ ] Add tests confirming both styles return identical results.
- [ ] Update `API.md` to mark the namespaces available.

### Acceptance criteria

- `pyta.trend.sma` and `pyta.sma` call the same function.
- Importing the whole package or a single category both work.
- Adding a category does not change existing imports.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 9 — Multi-column input (OHLCV)

**Goal:** Let users pass full OHLCV data and have PyTA find what each indicator needs.

### Tasks

- [ ] Grow `IndicatorRequest` from a single `Series` to named multi-column input, building on `Ohlcv`.
- [ ] Detect the container and identify column roles automatically (open, high, low, close, volume).
- [ ] Ignore columns an indicator does not need.
- [ ] Support an explicit `columns=[...]` override.
- [ ] Keep column roles open-ended (not hard-coded to OHLCV), so fundamental roles such as `eps`, `book_value`, `sales`, `dividends`, and `ebitda` can be added for valuation indicators without redesigning the role system.
- [ ] Raise a `ValueError` that names the required columns and the available columns when a role cannot be found.
- [ ] Return results in the input's container type.
- [ ] Add tests across every supported container, including extra columns and overrides.
- [ ] Update `API.md` and `ARCHITECTURE.md`.

### Acceptance criteria

- A user can pass a full OHLCV DataFrame to a multi-column indicator without naming columns.
- Users who don't know which columns an indicator needs get an error that tells them.
- Single-column indicators are unaffected.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 10 — Multi-output indicators

**Goal:** Support indicators that produce several series.

### Tasks

- [ ] Extend the output contract to carry several named series.
- [ ] Return outputs in the input's container type: extra columns for DataFrames, extra keys for dicts and JSON objects.
- [ ] Define output naming (for example `macd`, `macd_signal`, `macd_hist`) and match the casing of the input's columns.
- [ ] Validate the design with MACD.
- [ ] Add tests for naming, casing, container types, and warm-up per output.
- [ ] Update `API.md`.

### Acceptance criteria

- MACD returns three named outputs in every supported container.
- Output casing matches the input's columns.
- Single-output indicators are unchanged.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 11 — CSV input

**Goal:** Support the CSV data that AlphaVantage returns.

### Tasks

- [ ] Accept CSV (`str` and `bytes`) as input.
- [ ] Return CSV in the same form as the input.
- [ ] Apply the same column selection and NaN policy as other containers.
- [ ] Add tests, including headers, missing values, and mixed-case column names.
- [ ] Update `API.md`.

### Acceptance criteria

- CSV in produces CSV out, with the same conventions as JSON.
- No provider dependency is added.

**Retrospective:**  
**Sprint completion:** ☐

---

## Sprint 12 — Independent integration project

**Goal:** Validate PyTA from the perspective of an external consumer.

**Project:** `PyTA-Integration/`, a testing project with its own `pyproject.toml` and virtual environment.

### Tasks

- [ ] Create the separate integration repository or sibling project directory.
- [ ] Create an independent Python virtual environment.
- [ ] Install PyTA as a built or locally installed package, never by importing its source files.
- [ ] Add examples for SMA and RSI using a pandas DataFrame shaped like yFinance output.
- [ ] Add examples using AlphaVantage-shaped JSON and CSV.
- [ ] Add an example of a batch call across several datasets.
- [ ] Add integration tests for expected values, invalid parameters, and error messages.
- [ ] Verify that the project does not depend on PyTA's internal crate paths or `pyta._native`.
- [ ] Document how a new developer installs and runs the examples.

### Acceptance criteria

- The integration project installs and imports PyTA independently.
- All example workflows run successfully.
- Integration tests pass against the installed package.
- The public API works without access to the PyTA source tree.
- A package build can be tested from a clean environment.

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

## Sprint 15 — Expand indicators within existing categories

**Goal:** Add indicators without redesigning the infrastructure.

### Tasks

- [ ] Review the priority list for Trend and Momentum indicators (EMA, CCI, and Stochastic first).
- [ ] Rank indicators by usefulness, implementation complexity, and validation requirements.
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

## Sprint 16 — Additional indicator categories

**Goal:** Expand the architecture into a broader technical analysis library.

### Tasks

- [ ] Prioritize additional categories: Volatility, Volume, and Valuation (see [Valuation plan](#valuation-plan)).
- [ ] Create each new category as a separate `pyta-<category>` crate and Python namespace.
- [ ] Reuse the shared core and engine contracts.
- [ ] Implement and validate the first indicator in each new category.
- [ ] Add each indicator to batch execution.
- [ ] Expand integration tests.
- [ ] Review cross-category naming, parameter conventions, and output consistency.

### Acceptance criteria

- New categories integrate with the same public Python interface.
- Core behavior is consistent across categories.
- New indicators have numerical reference tests and documented edge cases.
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
- [ ] Output names: extend the `<indicator>_<period>` convention with a no-period form for ratios (`pe`, `pb`, `ev_ebitda`).

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