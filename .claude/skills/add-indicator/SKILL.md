---
name: add-indicator
description: Step-by-step procedure for adding a technical indicator to PyTA, from formula spec through Rust kernel, engine dispatch and cost, PyO3 bindings, Python API, batch, tests, benchmarks and docs. Use this whenever the user asks to add, implement or port an indicator (EMA, WMA, MACD, Bollinger Bands, ATR, Stochastic, CCI, ADX, OBV, ROC, or any other), works on a Sprint 15 or 16 indicator task, or invokes /add-indicator <name>. Also covers indicators that need more than one input series, extra parameters or several outputs, by extending the engine contracts.
---

# Add an indicator to PyTA

The indicator to add is the argument (`/add-indicator ema`). If there is none, ask which one.

An indicator is done only when, in the words of `docs/DEVELOPMENT.md`, "its correctness, error behavior, Python API, batch access, documentation, and regression tests all pass". Formula code returning numbers is step 2 of 9.

## Before starting

- Read the `pyta-tooling` skill (LSP registration, Context7 rules).
- Check the indicator is not already there: `IndicatorKind` in `rust/crates/pyta-engine/src/requests.rs` and the README "Indicators" tables.
- **Copy from the code, not from this skill.** Open the most recently added indicator's files (at the time of writing, RSI) and follow them. Sprints 7.5 (tests and fixtures), 8 (category namespaces), 9 (OHLCV input) and 10 (multi-output) change the layout; where the code and this skill disagree, the code wins, and say so in the report so the skill can be updated.
- Commit only on worktree branches, never on `main`; never push. The maintainer reviews, merges into `main` locally and pushes.

## Step 1: Spec, then stop

Write the spec with `references/spec-template.md` and present it. **Do not write code until the user approves it.** This is the only checkpoint; after approval, do steps 2 to 9 without pausing.

- **Formula: TA-Lib's convention wins** when sources disagree, because PyTA is a TA-Lib replacement. Read TA-Lib's C source with WebFetch (free, no Context7 budget): `https://raw.githubusercontent.com/TA-Lib/ta-lib/main/src/ta_func/ta_<NAME>.c`. It gives the formula, the lookback (warm-up length), the defaults and the parameter ranges. Note any difference from the original author's definition for the docs. Use `deep-research` only if TA-Lib's behaviour is unclear or sources conflict on something TA-Lib does not settle.
- **Errors** map to existing `PytaError` variants (`InvalidPeriod`, `InsufficientData { required, length }`, ...) in `rust/crates/pyta-core/src/error.rs`. Add a variant only if none fits, and say so in the spec.
- **Reference values** come from a published worked example (textbook, StockCharts ChartSchool, the author's book), cited, and stored under `tests/fixtures/` for both the Rust and Python tests. Hand-computed tables are fine for edge cases; they are not the reference.
- **Shape check:** today's contract is one `Series` in, one `period`, one series out (`IndicatorRequest { kind, input, period }` → `IndicatorOutput`). If the indicator needs more input columns, other parameters or several outputs, the spec must include the contract extension: read `references/extending-contracts.md` and design it there. The extension is part of what the user approves.

## Step 2: Rust kernel

In `rust/crates/pyta-<category>/`:

- `src/<name>.rs`: `pub fn <name>(input: &Series, period: usize) -> PytaResult<IndicatorOutput>` (or the extended signature from the spec). Doc comment like `pyta-momentum/src/rsi.rs`: what it computes, how much input it needs, warm-up positions, edge cases, `# Errors`. Validate parameters first, then length. Output length equals input length, warm-up is `NaN`. Comment the non-obvious lines only, as `rsi.rs` does.
- `src/lib.rs`: `mod <name>;` and `pub use <name>::<name>;`, alphabetical.
- `tests/<name>_tests.rs`, mirroring `tests/rsi_tests.rs`: length and warm-up alignment, zero period, insufficient data with the exact `required` and `length`, the minimum amount of data, each edge case from the spec, and the reference values from the fixture (compare with a tolerance, such as `1e-9` relative, unless the source rounds; then use its precision).
- If the crate's dev-dependencies include `proptest`, add invariants: output length, exact warm-up count, and value bounds where the indicator has them.
- **New category:** create `pyta-<category>` like `pyta-momentum` (its `Cargo.toml` uses the workspace fields and depends only on `pyta-core`), add it to `members` in the root `Cargo.toml`, and to `pyta-engine/Cargo.toml`. Constants that define the algorithm stay in the kernel; tunables go in `pyta-common`.

## Step 3: Engine

- `rust/crates/pyta-engine/src/requests.rs`: add `IndicatorKind::<Name>`.
- `rust/crates/pyta-engine/src/dispatch.rs`: add the `use`, an arm in `dispatch()`, and an arm in `estimated_cost_ns()`. Both matches are exhaustive on purpose, so the build fails until both exist.
- `rust/crates/pyta-common/src/costs.rs`: `pub const <NAME>_NS_PER_ELEMENT: f64 = ...;` with a doc comment like the others. If the algorithm is O(n · period), the estimate in `estimated_cost_ns()` must include `period` (update the comment there too). The value comes from step 4; put in a provisional figure until then.
- `rust/crates/pyta-engine/tests/engine_tests.rs`: add the new kind to the success and error cases, following the existing `request(IndicatorKind::Rsi, ...)` entries.

## Step 4: Benchmarks and the cost constant

Register the indicator where `scripts/README.md` ("Adding an indicator") says:

- one line in `INDICATORS` in `rust/crates/pyta-engine/benches/single_call.rs` (and raise the array length in its type),
- one entry in the `for (kind, label) in [...]` loop of `many_datasets` in `rust/crates/pyta-engine/benches/workloads.rs`,
- one line in `INDICATORS` in `benches/python/bench_boundary.py` and in `benches/python/bench_batch.py`, with the benchmark period (the TA-Lib default).

Then measure: run `./scripts/benchmark.sh --single --rust --quick` (all indicators, so RSI is measured in the same run, on the same machine). Take the `kernel` time at 1,000,000 points for the new indicator and for RSI, and set the constant to `RSI_NS_PER_ELEMENT * new_kernel / rsi_kernel`. Scaling against RSI keeps the constants consistent with the planner's calibration (`pyta-common` constants were measured on the 16-thread i9-9900K; relative accuracy is what matters). Tell the user the figure is provisional from a quick run and should be confirmed with a full `./scripts/benchmark.sh --single --rust --indicator <name>` on a quiet machine.

## Step 5: PyO3 bindings

- `rust/crates/pyta-python/src/<name>.rs`: copy `rsi.rs`. `<name>` calls `single::compute(py, values, period, IndicatorKind::<Name>)`, `<name>_batch` calls `batch::compute_batch(...)`. Doc comments say what it calculates and what it returns.
- `rust/crates/pyta-python/src/lib.rs`: `mod <name>;` (alphabetical) and two `m.add_function(wrap_pyfunction!(...))` lines. Nothing else belongs in `lib.rs`.
- `python/pyta/_native.pyi`: stubs for `<name>` and `<name>_batch`, matching the existing signatures.

## Step 6: Python package

- `python/pyta/indicators/<name>.py`: copy `rsi.py`. Module docstring names the category. The single function delegates to `_api.run(_native.<name>, "<name>", data, period, column, default_column=<ROLE>)` and the batch function to `_api.run_batch(...)`. Default `period` = TA-Lib's default when it has a standard one (RSI 14); required otherwise (SMA). Docstrings follow `rsi.py`: Args, Returns (output name `<name>_<period>`), Raises. No formula code in Python.
- Exports, each with a sorted `__all__`: `python/pyta/indicators/__init__.py`, `python/pyta/__init__.py`, and `python/pyta/batch.py` (`from .indicators.<name> import <name>_batch as <name>`).
- If Sprint 8's category namespaces exist (`pyta.trend`, `pyta.momentum`, ...), add it to its category there and under `pyta.batch` too.

## Step 7: Python tests

- `tests/python/test_<name>.py`: values against the fixture, the default period, warm-up length, error types and messages (`pytest.raises(..., match=...)`), and chaining with another indicator. If the older `test_trend.py`/`test_momentum.py` still exist, still use a per-indicator file (the Sprint 7.5 layout).
- `tests/python/test_batch.py`: add the name to every `@pytest.mark.parametrize("name", [...])` list.
- `tests/smoke/test_smoke.py`: one call checking dtype, length and warm-up.
- `tests/reference/test_<name>_reference.py`: the published example from `tests/fixtures/`, the same fixture the Rust test reads.

## Step 8: Docs

- `docs/indicators/<category>/<name>.md`: user-facing, with the same headings as `docs/indicators/momentum/rsi.md` (What it is, What it is for, Usage, Parameters, Output, Edge cases, Missing and invalid data, Implementation notes, See also). Implementation notes state the TA-Lib convention followed and any difference from the original definition.
- `docs/API.md` section 3 ("Indicators"): a row in the table, the sentence that links the wiki pages, and a short `### <NAME> (<Full name>)` section with the formula. Update section 7's `ValueError` row if the error conditions are new.
- `README.md`: move the indicator from "Planned" to the "Available" table with its wiki link.
- `docs/ARCHITECTURE.md`: the category-crate table and the file listings (package tree, `pyta._native` functions).
- `docs/DEVELOPMENT.md`: tick the task if the indicator belongs to a sprint. Do not mark a sprint complete.

## Step 9: Verify and report

1. `uv run --with maturin maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml`
2. `./scripts/test-suite.sh`, and fix until it passes (its report lands in `tests/results/`).
3. Report: the files changed by layer, the test-suite result, the provisional cost constant and the benchmark to confirm it, any place the code and this skill disagreed, and any decision the spec left open.
