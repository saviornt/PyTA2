# PyTA — Agile Development Plan

**Project:** PyTA — Python technical analysis library with a Rust calculation engine  
**Methodology:** Lightweight Agile, incremental delivery, test-driven development where practical  
**Initial scope:** Two indicator categories, one indicator per category, independently consumable from Python  
**Completion tracking:** Check off each task as it is finished. Mark a sprint with ✓ only after its acceptance criteria pass.

> Note 1: This is the development plan for the first project milestone - the creation of the public and open-source portion of PyTA. The second milestone, which is not a part of this development plan, is to use what we are building and adding machine learning and period-based predictions based on indicators and market sentiment.

> Note 2: Initial data source for testing will be through yFinance while RC1 will be capable of using a variety of data providers such as yFinance and AlphaVantage.

> Note 3: There will be 3 different versions of PyTA > 1. PyTA-Core: Drop-in replacement for TA-Lib, free & open-source. 2. PyTA-ML: Adds machine learning, market sentiment and market predictions on top of PyTA-Core. 3. PyTA-Pro: Adds an additional, navigational dashboard on top of PyTA-ML.

---

## Guiding principles

1. **Build a vertical slice first.** Each sprint should produce something that runs and can be tested, not just scaffolding.
2. **Rust owns the calculations.** Indicator formulas, numerical processing, and performance-critical work live in Rust.
3. **Python provides the interface.** Python exposes a consistent, user-friendly API and integrates with the Python ecosystem.
4. **Asynchronous execution is designed explicitly.** A Python `async` function must await a real Rust-backed execution path; merely declaring a function asynchronous does not make CPU calculations nonblocking.
5. **Test outside the repository.** A separate Python project verifies the experience of a real library consumer.
6. **Correctness before optimization.** Establish trusted results and benchmarks before introducing caching, parallel execution strategies, or GPU acceleration.
7. **One shared execution architecture.** New indicators should be added to the existing architecture rather than requiring new infrastructure for every category.

## Sprint 0 — Development environment and repository foundations

**Goal:** Establish a reproducible development environment before writing indicator code.

### Tasks

- [ ] Confirm `rustup` is installed and the stable Rust toolchain is active.
- [ ] Install and verify `rustfmt` and `clippy`.
- [ ] Create and activate the root Python virtual environment, `.venv`.
- [ ] Install Python development dependencies, including Maturin and pytest.
- [ ] Configure Visual Studio Code / Code OSS to use the project virtual environment and Rust Analyzer.
- [ ] Create the initial repository structure.
- [ ] Add `.gitignore`, a README, and basic project documentation directories.
- [ ] Initialize or verify Git and commit the clean starting point.
- [ ] Verify Rust, Cargo, Python, pip, Git, and Maturin versions.

### Acceptance criteria

- The development environment works from a fresh terminal.
- Python commands use the intended virtual environment.
- Rust commands use the intended rustup-managed toolchain.
- Generated build artifacts and virtual-environment files are excluded from Git.

**Sprint completion:** ☐

---

## Sprint 1 — Rust workspace and Python packaging skeleton

**Goal:** Create the smallest valid mixed Rust/Python project that builds and imports.

### Tasks

- [ ] Create `rust/Cargo.toml` as the Rust workspace manifest.
- [ ] Create the initial crates: `pyta-core`, `pyta-engine`, `pyta-momentum`, `pyta-trend`, and `pyta-python`.
- [ ] Configure shared dependency versions and workspace settings.
- [ ] Add `rust-toolchain.toml` to pin the selected stable toolchain policy.
- [ ] Configure the root `pyproject.toml` for Maturin and the chosen Python source layout.
- [ ] Add a minimal PyO3 extension module.
- [ ] Build and install the package into the development virtual environment.
- [ ] Import `pyta` from Python.
- [ ] Add a minimal automated build/import smoke test.

### Acceptance criteria

- `cargo check --workspace` succeeds.
- `cargo fmt --all -- --check` succeeds.
- `cargo clippy --workspace --all-targets` succeeds without unresolved warnings that violate project policy.
- Maturin builds the extension successfully.
- Python can import `pyta` and call a minimal native function.
- The package does not require manually copying a compiled extension into the Python source directory.

**Sprint completion:** ☐

---

## Sprint 2 — Core data contracts and numerical conventions

**Goal:** Establish the shared contracts every indicator will follow.

### Tasks

- [ ] Define accepted input representations, starting with one-dimensional numerical arrays.
- [ ] Define output types, including numeric arrays and indicator metadata where needed.
- [ ] Establish the initial missing-value and warm-up conventions.
- [ ] Define behavior for empty input, insufficient input, invalid parameters, and non-finite values.
- [ ] Implement shared input validation in `pyta-core`.
- [ ] Define consistent error handling between Rust exceptions and Python exceptions.
- [ ] Establish a reference-test format for comparing numerical outputs.
- [ ] Document the initial public API and numerical conventions.

### Acceptance criteria

- Input validation is shared instead of being reimplemented independently for every indicator.
- Invalid inputs produce predictable errors.
- Numerical behavior is documented and testable.
- The API can accommodate additional indicators without changing the foundational data contracts.

**Sprint completion:** ☐

---

## Sprint 3 — First indicator: Simple Moving Average (Trend)

**Goal:** Deliver one complete indicator through the Rust-to-Python interface.

**Indicator:** Simple Moving Average (SMA) in the `pyta-trend` crate.

### Tasks

- [ ] Implement the SMA calculation in Rust.
- [ ] Add unit tests for known values and hand-calculated examples.
- [ ] Test warm-up periods, short inputs, empty inputs, and invalid window sizes.
- [ ] Compare results against an independent reference implementation.
- [ ] Expose SMA through the PyO3 extension.
- [ ] Add a Python-facing API with clear parameter names and documentation.
- [ ] Add Python tests for output shape, values, and errors.
- [ ] Document the indicator's formula and output conventions.

### Acceptance criteria

- SMA is calculated in Rust, not reimplemented in Python.
- Rust and Python tests pass.
- Results match the reference within the defined numerical tolerance.
- The indicator can be called using the intended public API.
- The behavior for warm-up values is explicitly documented.

**Sprint completion:** ☐

---

## Sprint 4 — Second indicator: Relative Strength Index (Momentum)

**Goal:** Prove that the architecture supports a separate indicator category without duplicating infrastructure.

**Indicator:** Relative Strength Index (RSI) in the `pyta-momentum` crate.

### Tasks

- [ ] Implement RSI in Rust using the selected smoothing convention.
- [ ] Document the RSI formula and the exact smoothing method.
- [ ] Define behavior for flat prices, all-gain inputs, all-loss inputs, and insufficient history.
- [ ] Add unit tests for hand-calculated and reference results.
- [ ] Compare output against a trusted independent implementation using matching settings.
- [ ] Expose RSI through the Python extension.
- [ ] Add Python tests for expected values, output shape, and errors.
- [ ] Confirm the RSI and SMA APIs share the same core input and error contracts.

### Acceptance criteria

- RSI is calculated in Rust.
- Tests cover edge cases and numerical conventions.
- SMA and RSI work through the same Python package.
- Adding RSI has not required duplicating the core validation or packaging architecture.

**Sprint completion:** ☐

---

## Sprint 5 — Asynchronous Rust execution path

**Goal:** Make indicator execution awaitable from Python while keeping CPU-heavy work off the asynchronous runtime's event-loop thread.

### Tasks

- [ ] Define the public asynchronous calling convention, such as `await pyta.async_api.sma(...)`.
- [ ] Select and configure the Rust-to-Python async integration, such as PyO3 with `pyo3-async-runtimes` and Tokio.
- [ ] Implement an execution layer that schedules CPU-bound indicator work appropriately, using `spawn_blocking` or a deliberately chosen CPU worker pool.
- [ ] Ensure a single indicator call uses the same execution path as a batch of indicators.
- [ ] Add cancellation and error-propagation behavior appropriate to the selected runtime integration.
- [ ] Add tests that await SMA and RSI from Python's `asyncio`.
- [ ] Test that unrelated Python coroutines can make progress while calculations run.
- [ ] Document the distinction between asynchronous scheduling and actual CPU parallelism.

### Acceptance criteria

- Both SMA and RSI are callable with `await`.
- The async API does not simply run long CPU-bound calculations on the async runtime's event-loop thread.
- Errors propagate to the Python caller in a predictable way.
- Tests verify nonblocking behavior without relying on fragile timing thresholds.
- Synchronous and asynchronous APIs, if both exposed, share the same underlying calculation implementations.

**Important design rule:** `async` does not automatically make a calculation faster. It enables cooperative scheduling; CPU parallelism requires an appropriate worker strategy.

**Sprint completion:** ☐

---

## Sprint 6 — Indicator engine and batch execution

**Goal:** Introduce a unified engine for requesting one or many indicators.

### Tasks

- [ ] Define a common indicator request model.
- [ ] Implement dispatch from the engine to the appropriate indicator crate.
- [ ] Support a single-indicator request through the engine.
- [ ] Support a batch containing indicators from different categories.
- [ ] Identify independent calculations and schedule them concurrently where beneficial.
- [ ] Define deterministic result ordering and a stable result structure.
- [ ] Handle partial failures according to a documented batch-error policy.
- [ ] Add tests for single requests, mixed-category batches, and invalid requests.
- [ ] Confirm that batch execution reuses shared input validation and avoids unnecessary conversions.

### Acceptance criteria

- The same engine can execute one indicator or multiple indicators.
- SMA and RSI can be requested together.
- Independent calculations can execute concurrently without requiring callers to coordinate separate tasks manually.
- Results are mapped back to their requests deterministically.
- The engine is ready to accept more indicator categories without changes to the public execution model.

**Sprint completion:** ☐

---

## Sprint 7 — Independent Python integration project

**Goal:** Validate PyTA from the perspective of an external consumer.

**Project:** `PyTA-Integration/`, with its own `pyproject.toml` and virtual environment.

### Tasks

- [ ] Create the separate integration repository or sibling project directory.
- [ ] Create an independent Python virtual environment.
- [ ] Install PyTA as a built or locally installed package, rather than importing its source files directly.
- [ ] Write an example that calculates SMA using `asyncio`.
- [ ] Write an example that calculates RSI using `asyncio`.
- [ ] Write an example that requests both indicators in one batch.
- [ ] Add integration tests for expected values, invalid parameters, and exceptions.
- [ ] Verify that the integration project does not depend on PyTA's internal Rust crate paths.
- [ ] Document how a new developer can install and run the examples.

### Acceptance criteria

- The integration project can install and import PyTA independently.
- All three example workflows run successfully.
- Integration tests pass against the installed package.
- The public API works without direct access to the PyTA source tree.
- A package build can be tested from a clean environment.

**Sprint completion:** ☐

---

## Sprint 8 — Quality gates, documentation, and first release candidate

**Goal:** Turn the initial proof of concept into a dependable baseline.

### Tasks

- [ ] Run the full Rust unit-test suite.
- [ ] Run the Python unit and integration test suites.
- [ ] Add CI checks for formatting, linting, compilation, and tests.
- [ ] Test package builds in a clean environment.
- [ ] Add API documentation for SMA, RSI, async calls, and batch execution.
- [ ] Document installation, supported Python/Rust versions, and known limitations.
- [ ] Add basic benchmarks for SMA, RSI, and mixed-indicator batches.
- [ ] Record baseline latency and throughput for representative input sizes.
- [ ] Review error messages and public API naming.
- [ ] Tag the initial milestone once all acceptance criteria pass.

### Acceptance criteria

- All required automated checks pass.
- An external user can install the package and follow the documentation.
- Baseline benchmarks are reproducible and recorded.
- Known numerical conventions and limitations are documented.
- The team has a stable foundation for adding more indicators.

**Sprint completion:** ☐

---

## Sprint 9 — Expand indicators within existing categories

**Goal:** Add indicators without redesigning the infrastructure.

### Tasks

- [ ] Review the next priority list for Momentum and Trend indicators.
- [ ] Rank indicators by usefulness, implementation complexity, and validation requirements.
- [ ] Add one indicator at a time using the established development workflow.
- [ ] Add formula documentation, reference tests, and edge-case tests for each indicator.
- [ ] Verify synchronous and asynchronous access according to the established API contract.
- [ ] Add each indicator to the engine's dispatch and batch execution support.
- [ ] Update the separate integration project's coverage.
- [ ] Measure performance against the established baseline.

### Acceptance criteria

- Each added indicator passes its own correctness and edge-case tests.
- Existing indicator behavior remains unchanged.
- No new per-indicator execution infrastructure is required.
- Documentation and integration coverage stay current.

**Sprint completion:** ☐

---

## Sprint 10 — Additional indicator categories

**Goal:** Expand the architecture into a broader technical analysis library.

### Tasks

- [ ] Prioritize additional categories such as Volatility, Volume, and Valuation.
- [ ] Create each new category as a separate Rust crate where justified by its responsibilities.
- [ ] Reuse the shared core and engine contracts.
- [ ] Implement and validate the first indicator in each new category.
- [ ] Add each indicator to async and batch execution.
- [ ] Expand external integration tests.
- [ ] Review cross-category naming, parameter conventions, and output consistency.

### Acceptance criteria

- New categories integrate with the same public Python interface.
- Core behavior is consistent across categories.
- New indicators have numerical reference tests and documented edge cases.
- The engine does not accumulate category-specific special cases unnecessarily.

**Sprint completion:** ☐

---

## Sprint 11 — Performance, caching, and future acceleration

**Goal:** Introduce optimizations only when measurement demonstrates a need.

### Tasks

- [ ] Benchmark the expanded library using realistic workloads and data sizes.
- [ ] Profile time spent in calculations, scheduling, input conversion, and output conversion.
- [ ] Identify repeated calculations and opportunities for shared intermediate results.
- [ ] Evaluate request-scoped caching and bounded LRU caching.
- [ ] Define cache keys, memory limits, invalidation, and concurrency behavior before implementing a persistent cache.
- [ ] Evaluate Rayon or other CPU-parallel execution strategies against the existing baseline.
- [ ] Investigate incremental calculations for streaming or frequently updated data.
- [ ] Evaluate GPU acceleration only for workloads where transfer and launch overhead can be justified.
- [ ] Add regression benchmarks for any adopted optimization.

### Acceptance criteria

- Each optimization has a measured justification.
- Numerical correctness is preserved.
- Cache behavior is bounded, deterministic, and documented if caching is adopted.
- Performance improvements are demonstrated against the recorded baseline.
- GPU support remains optional unless its benefits justify the added complexity.

**Sprint completion:** ☐

---

## Standard workflow for every new indicator

Once the first two indicators are complete, each additional indicator should follow the same lightweight cycle.

- [ ] Define the formula, parameters, and numerical conventions.
- [ ] Write reference and edge-case tests.
- [ ] Implement the calculation in its category crate.
- [ ] Validate Rust results against the reference.
- [ ] Expose the indicator through the Python package.
- [ ] Add engine dispatch and batch support.
- [ ] Test the asynchronous calling path.
- [ ] Add external integration coverage.
- [ ] Update documentation.
- [ ] Run the full regression suite and benchmarks where appropriate.

**Indicator completion rule:** An indicator is not complete merely because its formula returns numbers. It is complete when its correctness, error behavior, Python API, asynchronous access, documentation, and regression tests all pass.

---

## Sprint tracking rules

1. Start each sprint by confirming its goal and acceptance criteria.
2. Keep work small enough to review and test independently.
3. Mark a task `[x]` only when its deliverable is finished and verified.
4. Leave a sprint's completion marker as `☐` until every required acceptance criterion passes.
5. Change the sprint marker to `✓` only after verification.
6. If a task reveals an architectural problem, fix the foundation before adding more indicators.
7. At the end of each sprint, record what worked, what did not, and the next sprint's priorities.

## Definition of done

The initial milestone is achieved when:

- [ ] The Rust workspace builds cleanly.
- [ ] The Python package installs and imports.
- [ ] SMA and RSI produce validated results.
- [ ] Both indicators can be awaited from Python through the Rust-backed execution path.
- [ ] The engine can run them individually and in a mixed batch.
- [ ] The separate Python integration project passes its tests.
- [ ] CI, documentation, and baseline benchmarks are in place.

**Initial milestone:** PyTA has proven its end-to-end architecture. From this point onward, the primary development work becomes adding and validating indicators rather than repeatedly rebuilding the foundation.