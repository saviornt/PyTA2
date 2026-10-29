---
name: pyta-testing
description: How to test PyTA - which command answers which question, the full scripts/test-suite.sh run and its report, fast targeted Rust and Python test runs, where each kind of test belongs, how to write Rust and Python tests in this repository's style, reference and property tests, and how to triage failures. Use this whenever writing, running, fixing or reviewing tests in PyTA, before reporting any code change as done, when the test suite or CI fails, or when deciding where a new test goes.
---

# Testing PyTA

## Which command

| Question | Command |
|---|---|
| Is everything green? (before saying any change is done) | `./scripts/test-suite.sh` |
| Does one Rust crate or test pass? | `cargo test -p <crate> <name_filter>` |
| Does one Python test pass? | `uv run pytest tests/python/<file>.py::<test>` |
| All Python tests, including pandas ones | `uv run --extra pandas pytest` |
| Python tests after a Rust change | rebuild first: `uv run maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml` |

Use the targeted commands while iterating, then the full suite once at the end. The suite is the only thing that counts as "tests pass".

## The full suite

`./scripts/test-suite.sh` (no options) runs thirteen steps and never stops early, so one run shows everything broken:

1. `cargo fmt --all` (fixes formatting in place, as CI does)
2. `cargo fmt --all -- --check`
3. Clippy with `-D warnings`
4. `cargo test --workspace`
5. building the extension (debug)
6. the smoke test
7. pytest with the pandas extra (strict markers and config, warnings as errors, branch coverage of `pyta` with the floor in `pyproject.toml`)
8. Ruff lint
9. Ruff format check
10. Pyright, strict, on `python/`
11. `mypy.stubtest pyta._native` (stubs match the compiled module)
12. `cargo nextest run` (optional; SKIP when not installed)
13. `cargo llvm-cov` (optional; SKIP when not installed)

The report is `tests/results/test-suite_<date>_<time>.txt`: result, duration, commit, dirty-tree flag, tool versions, a step table with timings, Rust and Python test counts, and Python and Rust coverage, then each step's full output.

- Read only the top of the report, up to the `FULL RESULTS` heading: `sed '/^FULL RESULTS/q' tests/results/test-suite_<date>_<time>.txt`. Open Full Results only for a failing or odd step, and grep for that step's section (`<n>. <step name>  [STATUS, Ns]`, for example `grep -n -A 60 '^7\. ' <report>`) instead of reading the whole log. Give spawned agents (tester, reviewer) the same rule in their brief.
- **Compare the test counts with the previous report.** A count that drops without a deleted test means tests stopped being collected.
- Step 1 changes files. If it reports fixes, mention them; the `format-on-edit` hook should normally have prevented them.
- Quote the failing assertion or error in the report to the user. Never describe a failing run as passing.

## Where tests go

| Kind | Location | Notes |
|---|---|---|
| Kernel formulas, boundaries, warm-up, errors | `rust/crates/<crate>/tests/<name>_tests.rs` | One file per indicator, like `pyta-momentum/tests/rsi_tests.rs` |
| Private helpers | `#[cfg(test)] mod tests` in the source file | Only for what integration tests cannot reach |
| Engine ordering, error isolation, planner | `rust/crates/pyta-engine/tests/`, `planner.rs` unit tests | Parallel and sequential paths must give identical results |
| Public Python API | `tests/python/` | Containers, NaN policy, parameters, errors, batch, columns, fork safety, import rules |
| Per-indicator Python numerics | `tests/python/test_<name>.py` | Like `test_sma.py`, `test_rsi.py` |
| Python properties | `tests/python/test_properties.py` | `hypothesis` |
| Kernel invariants | `rust/crates/<crate>/tests/property_tests.rs` | `proptest` |
| Reference values (published, or TA-Lib-generated) | `tests/fixtures/<name>_<params>_<source>.csv` (`ema_10_talib.csv`, `macd_12_26_9_talib.csv`), read by `tests/reference/test_<name>_reference.py` and `rust/crates/<crate>/tests/reference_tests.rs` | Fixture cites its source and tolerance; Rust reads it through `rust/test-support/reference.rs` |
| Build and import | `tests/smoke/test_smoke.py` | Fast; keep it small |

Benchmarks never go in tests: no timing assertions anywhere (see `pyta-benchmarks`).

## Writing Rust tests

- Integration tests use the public API only (`use pyta_momentum::rsi;`).
- Name tests for the behaviour they check: `rsi_rejects_insufficient_data`, not `test_3`.
- Errors are compared exactly: `assert_eq!(rsi(&close, 3), Err(PytaError::InsufficientData { required: 4, length: 3 }));`.
- Exact values only where the arithmetic is exact (100.0 for an RSI with no losses); otherwise compare within a tolerance and state it (`1e-9` relative, or the reference's printed precision).
- Check warm-up positions explicitly: the first `k` values are `NaN` and the next is finite.
- Property tests (`proptest`, in `tests/property_tests.rs`): output length equals input length, exact warm-up count, value bounds (RSI in [0, 100], SMA within its window's min and max).

## Writing Python tests

- Plain pytest functions; `@pytest.mark.parametrize` for the same check across indicators or containers (see `tests/python/test_batch.py`).
- pandas is optional: mark the test `@pytest.mark.pandas` and get it with `pd = pytest.importorskip("pandas")` inside the test, never a module-level import. `import pyta` must not import pandas.
- Errors: `with pytest.raises(ValueError, match="...")`, matching the part of the message a user relies on.
- Floats: `np.testing.assert_allclose` with an explicit `rtol`; NaN positions with `np.isnan`.
- Realistic input: take the `ohlcv` fixture (`tests/conftest.py`; 300 real SPY sessions as read-only arrays, `.columns()`, `.lists()`, `.dates`) and compare with an independent result such as `rolling_mean` from `tests/ohlcv_data.py`. Keep small hand-checked arrays for exact known values and for tests about one specific value (NaN, infinity, limits, error messages).
- Test through the public API (`pyta.<name>`, `pyta.batch.<name>`); call `pyta._native` only in tests that are about the native boundary.
- Property tests (`hypothesis`, in `test_properties.py`): containers round-trip their type, leading NaN carries through, output length matches.

## Reference tests

Reference values come from published worked examples (textbooks, StockCharts ChartSchool, the indicator author's book) and are stored once in `tests/fixtures/` with the source cited in the file, so Rust and Python check the same numbers. Hand-computed values are fine for edge cases but are not references.

Differential testing against TA-Lib itself (the project follows TA-Lib's conventions) is not possible yet: TA-Lib is not installed. It is a QA-phase decision; do not install it or add it as a dependency.

## Triage

- **Formatting step fixed or failed:** run `cargo fmt --all` / `uv run ruff format python tests` and re-check; formatting is never a reason to touch logic.
- **Clippy:** fix the code. An `#[allow(...)]` needs a comment saying why, and the user's agreement for anything beyond a single item.
- **Python tests fail after a Rust change:** rebuild the extension first; stale builds are the usual cause.
- **A test looks wrong:** say why and what the correct expectation is; never weaken an assertion or delete a test only to get green.
- **Flaky test** (passes on rerun): report it as flaky with both outcomes; do not retry until green and call it fixed.
