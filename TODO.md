# TODO Scratchpad — PyTA Python Boundary & Data Standardization

## Repository Analysis

### Blocking bugs
[x] 1. Smoke test path mismatch: `rebuild-and-run.sh` runs `tests/smoke/smoke_test.py`, but the file is `test_smoke.py`. The script fails.
[x] 2. Rayon panics abort the process: rayon::spawn with no panic handler aborts on panic, so the ExecutionFailed fallback in `batch.rs` never runs. Wrap the kernel in `std::panic::catch_unwind` inside `execution.rs`.
[x] 3. `.gitignore` ignores *.lock: Cargo.lock and uv.lock are never committed, which contradicts the architecture doc. Also add *.pyd, *.dylib, dist/ and *.egg-info.
[x] 4. `cargo fmt --check` fails: `error.rs` is missing a trailing comma, `rsi.rs` has period -1 and trailing whitespace, and `pyta-engine/src/lib.rs` is unformatted.
[x] 5. Doc comments attached to use: in `rsi.rs` and `sma.rs` the `///` blocks sit above use, so they never document rsi/sma. Move them onto the functions.
[x] 6. `PytaError::ExecutionFailed` maps to `ValueError:` it should be a `RuntimeError`.

### Design conflicts to resolve
[x] 1. **Output type:** `Vec<Option<f64>>` costs 16 bytes per element plus a copy at the boundary. Consider `Vec<f64>` with NaN internally.
[ ] 2. RSI period == len error: it reports `PeriodExceedsLength`, but the real problem is that RSI needs period + 1 points. Add an `InsufficientData` variant.
[ ] 3. Single-call overhead: one call goes through Tokio, a worker, Rayon and a oneshot channel. Benchmark a direct-dispatch fast path.

### Packaging
[x] 1. LICENSE is not MIT: it’s the X11 text with a non-advertising clause, a leftover “X CONSORTIUM”, and <...> placeholders, while pyproject.toml and Cargo say MIT. Use the standard MIT text.
[x] 2. No `_native.pyi` stub despite `py.typed`, so type checkers see an untyped module.
[ ] 3. `numpy` is declared in the workspace but unused. Use `PyReadonlyArray1` for NumPy input. Currently `Vec<f64>` copies everything - check this to ensure we are using Numpy input.


### Minor Issues
[x] 1. `batch.rs` guards results with a mutex. A `JoinSet` returning (index, result) is simpler and lock-free.
[x] 2. SMA’s running sum accumulates drift on long series. Consider periodic recompute or Kahan summation.
[x] 3. `pyta-engine` declares `thiserror` but doesn’t use it.
[x] 4. `test-suite.sh` runs Rust only (no `cargo fmt --check`, no `pytest`) and calls `clear`.

### Script Updates
[x] 1. Create a script to run benchmark tests on pyta-engine.
[ ] 2. Generate a summarized report after the Criterion benchmark.


> The following TODOs are automated TODOs and may not be applicable.

### Documentation & API Changes/Notes
1. Pydantic: Agreed, a mandatory dependency is fine if it’s your validation layer. Keep it off the hot path for large arrays, though. Pydantic validating a 1M-element list is slow, and Series::new in Rust already checks emptiness and finiteness. Use Pydantic for structure and parameters (field names, periods, OHLCV shape) and let Rust handle element-level checks.


## Phase 1: Public Python API Architecture

[x] **5. Audit the existing `python/pyta` package**
- Review `__init__.py`, `_api.py`, `_async.py`, `_types.py`, and `_validation.py`.
- Review `indicators/__init__.py`, `indicators/momentum.py`, and `indicators/trend.py`.
- Identify existing functionality, duplication, inconsistencies, and incomplete implementations.
- Confirm the current public API against the Rust engine and PyO3 bindings.
- Preserve useful implementations and document necessary changes before refactoring.

[ ] **6. Define the public API contract**
- Define supported imports and public names under `import pyta`.
- Establish consistent function signatures for individual indicators.
- Define how users access indicators through `pyta` and `pyta.indicators`.
- Standardize parameter naming, defaults, and keyword argument behavior.
- Define return types, warm-up behavior, and output alignment.
- Establish consistent Python exception types and error messages.
- Keep `pyta._native` an internal implementation detail.
- Update `API.md` as decisions are finalized.

[ ] **7. Decide the role of `_async.py`**
- Distinguish asynchronous Rust execution from asynchronous Python interfaces.
- Determine whether Python-level `asyncio` integration is an immediate requirement.
- Verify behavior when synchronous API calls originate inside an existing async event loop.
- Test concurrent Python callers and runtime lifecycle behavior.
- Keep `_async.py` deferred unless a concrete Python async API is justified.
- Avoid exposing Rust runtime implementation details to users.

## Phase 2: Canonical Data Model and Input Normalization

[ ] **8. Define canonical Python-side data types in `_types.py`**
- Define the internal representation of a single numeric series.
- Define the internal representation of OHLCV market data.
- Establish contracts for normalized field names, numeric values, and array dimensions.
- Define how optional timestamps and original indexes are handled.
- Keep Python types consistent with `pyta-core`'s `Series`, `Ohlcv`, and `IndicatorOutput`.
- Avoid unnecessary data copies during normalization.

[ ] **9. Define input validation and normalization in `_validation.py`**
- Centralize input conversion and validation for all indicators.
- Normalize field names using whitespace trimming and case folding.
- Support explicitly defined field aliases.
- Detect duplicate or conflicting names after normalization.
- Validate dimensions, lengths, numeric types, and finite values.
- Standardize empty-input and insufficient-data behavior.
- Validate indicator parameters before native execution where appropriate.
- Produce clear, consistent Python exceptions.

[ ] **10. Support standard Python sequences**
- Accept lists and tuples for individual numeric series.
- Validate numeric elements and reject unsupported nested sequences.
- Define behavior for booleans, strings, `None`, NaN, and infinity.
- Ensure consistent conversion and error messages.

[ ] **11. Support NumPy inputs**
- Accept one-dimensional NumPy arrays for individual indicators.
- Define supported numeric dtypes and conversion rules.
- Decide how non-contiguous arrays, array views, and non-native byte order are handled.
- Reject ambiguous multidimensional inputs unless column layout is explicitly specified.
- Keep NumPy optional if practical; document installation and missing-dependency behavior.
- Test conversion cost and avoid unnecessary copies.

[ ] **12. Support pandas inputs**
- Accept pandas Series as individual numeric series.
- Accept DataFrames using case-insensitive column matching.
- Define behavior for duplicate columns, missing columns, and mixed dtypes.
- Preserve index alignment where meaningful without silently reordering observations.
- Decide how users explicitly select a column when multiple candidates exist.
- Keep pandas optional if practical.

[ ] **13. Support dictionary inputs**
- Accept dictionaries containing a named numeric series.
- Support column-oriented OHLCV dictionaries.
- Normalize canonical field names and explicitly supported aliases.
- Detect key collisions after normalization.
- Validate equal column lengths and required fields.
- Define how ambiguous dictionaries are handled.

[ ] **14. Support Pydantic models**
- Accept Pydantic model instances through their standard serialization interface.
- Support both Pydantic v2 and any explicitly selected v1 compatibility path, if needed.
- Avoid requiring Pydantic as a mandatory dependency.
- Define how nested models and extra fields are treated.
- Reuse the same normalization and validation rules as dictionaries.

[ ] **15. Standardize OHLCV validation**
- Require the appropriate fields for OHLCV operations.
- Validate consistent column lengths.
- Define and validate the relationship between high, low, open, and close.
- Decide whether zero or negative prices are permitted by default.
- Define volume validation rules separately from price validation.
- Handle timestamps, missing rows, and ordering explicitly.
- Ensure validation behavior is consistent across all supported input formats.

## Phase 3: Shared Execution Bridge

[ ] **16. Implement the shared `_api.py` boundary**
- Centralize normalized input conversion and native calls.
- Keep indicator-specific modules independent of PyO3 implementation details.
- Map native errors to stable Python exception types.
- Standardize conversion of native results into public Python results.
- Preserve full-series output and warm-up alignment.
- Define batch execution integration without exposing internal async machinery.
- Avoid duplicate validation or conversion across layers.

[ ] **17. Standardize output behavior**
- Return results with a consistent length and ordering.
- Represent warm-up positions consistently.
- Define behavior for insufficient input data.
- Decide whether the initial API returns Python lists or offers optional NumPy output.
- Define how users retrieve the latest value without changing full-series defaults.
- Keep result behavior consistent across indicators.

## Phase 4: Indicator Public Modules

[ ] **18. Implement `indicators/__init__.py`**
- Export the supported indicator functions.
- Establish a predictable indicator namespace.
- Avoid duplicate or conflicting public names.

[ ] **19. Implement `indicators/trend.py`**
- Expose SMA through the shared API boundary.
- Prepare the module for EMA and future trend indicators.
- Apply the same input normalization, validation, and output conventions.
- Document supported input types and parameters.

[ ] **20. Implement `indicators/momentum.py`**
- Expose RSI through the shared API boundary.
- Prepare the module for CCI and Stochastic.
- Apply the same input normalization, validation, and output conventions.
- Document supported input types and parameters.

[ ] **21. Finalize `python/pyta/__init__.py`**
- Export the agreed public API.
- Ensure the documented import patterns work.
- Keep native implementation details private.
- Define `__all__` explicitly.
- Verify package imports do not unnecessarily load optional dependencies.

## Phase 5: Automated Testing and Integration

[ ] **22. Establish Python API tests**
- Add a Python test suite using pytest.
- Test public imports and function signatures.
- Test SMA and RSI against known reference values.
- Test warm-up behavior and output alignment.
- Test invalid parameters, empty inputs, and insufficient data.
- Test native error translation.
- Retain the smoke test as a quick build-and-run check.

[ ] **23. Test input-format equivalence**
- Test equivalent price data as lists, tuples, NumPy arrays, pandas Series, DataFrames, dictionaries, and Pydantic models.
- Verify equivalent inputs produce equivalent indicator results.
- Test lowercase, uppercase, mixed-case, and whitespace-padded field names.
- Test conflicting normalized names and missing required fields.
- Test inconsistent lengths, invalid dtypes, NaN, and infinity.
- Test optional dependencies both present and absent.

[ ] **24. Test execution and concurrency behavior**
- Verify synchronous Python calls use the Rust engine correctly.
- Test concurrent callers and error isolation.
- Verify batch result ordering.
- Test calls made from an existing asyncio event loop.
- Check runtime initialization and shutdown behavior where applicable.
- Confirm Python callers cannot accidentally deadlock the runtime.

[ ] **25. Integrate tests into the project workflow**
- Update the test scripts to run Rust and Python test suites.
- Ensure the native extension is built before Python integration tests.
- Make test failures propagate through scripts and CI.
- Keep fast smoke tests separate from comprehensive tests.
- Document local development and test commands.

## Phase 6: Performance and Documentation

[ ] **26. Benchmark normalization and conversion**
- Measure overhead for each supported input format.
- Compare list, NumPy, pandas, dictionary, and Pydantic inputs.
- Measure allocation and copying costs.
- Separate Python-boundary overhead from indicator computation.
- Use measurements to guide optimization.

[ ] **27. Benchmark the Rust execution engine**
- Add Criterion benchmarks for direct SMA and RSI calculations.
- Benchmark individual engine calls and batch sizes of 1, 8, 32, 128, and 1,024.
- Test multiple input lengths and mixed valid/invalid batches.
- Measure the combined Tokio and Rayon execution model.
- Record Rust version, CPU details, and benchmark configuration.
- Avoid timing-sensitive assertions in regular tests.

[ ] **28. Update documentation**
- Update `API.md` with finalized signatures, data contracts, and examples.
- Document supported input formats and optional dependencies.
- Document case-insensitive column names and aliases.
- Explain output alignment, warm-up values, and error behavior.
- Add examples for individual indicators and batch calculations.
- Keep documentation synchronized with tested behavior.

## Phase 7: Expand the Indicator Library

[ ] **29. Add EMA to `pyta-trend`**
- Implement the chosen EMA initialization and smoothing conventions.
- Add reference-value and edge-case tests.
- Expose EMA through the shared Python API.

[ ] **30. Add CCI and Stochastic to `pyta-momentum`**
- Define required inputs and parameter conventions.
- Implement and test the Rust calculations.
- Validate OHLCV input requirements where applicable.
- Expose both indicators through the shared Python API.

[ ] **31. Review engine scalability**
- Evaluate global versus per-batch concurrency limits.
- Preserve async orchestration and CPU execution separation.
- Optimize based on benchmark evidence rather than assumptions.

## Previously Completed Milestones

[x] 1. `pyta-core`
- Canonical Rust series and OHLCV types, validation primitives, shared errors, and output conventions.

[x] 2. `pyta-momentum` and `pyta-trend`
- Initial RSI and SMA implementations with edge-case tests.

[x] 3. `pyta-engine`
- Tokio orchestration, Rayon CPU execution, batch processing, result ordering, and error isolation.

[x] 4. `pyta-python`
- Initial PyO3 bridge and public `pyta` package with working SMA and RSI calls.

> **Architecture reminder:** Tokio orchestrates asynchronous execution; Rayon executes CPU-heavy calculations. Batch-worker concurrency and Rayon pool concurrency are separate controls. Benchmark the combined system before optimizing.
