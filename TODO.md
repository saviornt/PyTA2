# TODO Scratchpad — PyTA Python Boundary & Data Standardization

## Sprint 7.5: testing foundation and unified logging (before Sprint 8)

Sprint 7 is accepted. Before Sprint 8 adds more surface, the foundation needs real tests and a logging system. Add **Sprint 7.5** to `docs/DEVELOPMENT.md` between Sprints 7 and 8 (`Sprint completion: ☐` until its acceptance criteria pass).

Review findings that drive this:
- **Tests** (94 Python, about 35 Rust, all passing): seven placeholder files are empty, nothing checks SMA or RSI against an independent source, and there are no property tests, coverage measurement, Python type checking, or `[workspace.lints]`. Ruff's rule set is narrow (`E, F, I, UP`). The rule "`import pyta` must not import pandas" has no test.
- **Logging:** none anywhere. Batch failures are returned in place and are otherwise invisible.
- **Sprint 8 and 9** need their text revised (see Part D).

### Part A: housekeeping (about 30 min)

- [x] Fill the Sprint 7 **Retrospective** in `docs/DEVELOPMENT.md` (worked: benchmark-first design, Rayon over Tokio, fork test; didn't: biased benchmark arm, planner misses at the break-even; next: tests and logging). Earlier sprints' retrospectives are blank too; fill them only if wanted.
- [x] Delete the empty `tests/python/test_async_api.py` and the one-line `python/pyta/_async.py` (re-add when an async API is designed).
- [x] Fix the stale `pyta-engine` Cargo description ("Asynchronous calculation engine").
- [x] Refresh Claude's memory files: rewrite `project_batch-api-decisions.md` (still mentions the OnceLock runtime) and add the `MEMORY.md` index entries.

### Part B: Sprint 7.5a, testing to current standards (about half a day)

Use the latest stable versions of every tool, checked at implementation time.

**Rust**
- [x] Add `[workspace.lints]` to the root `Cargo.toml` (`unsafe_code` denied outside `pyta-python`, a curated Clippy `pedantic` subset, `missing_docs` for public items); each crate opts in with `[lints] workspace = true`. Fix what it flags.
- [x] Add `proptest` invariants to `pyta-trend` and `pyta-momentum`: output length equals input length, warm-up count is exact, SMA lies within its window's min and max, RSI is in [0, 100], constant input gives a constant SMA.
- [x] Fill `rust/crates/pyta-core/tests/error_tests.rs` (currently one line).
- [x] Add edge cases per kernel: `period` of 1 and of the series length, huge values, flat series.
- [x] Add an engine test that `execute_parallel` and `execute_sequential` give identical results.
- [x] Add reference tests from published worked examples (textbook only): a standard SMA example and the Wilder/StockCharts RSI-14 table, stored under `tests/fixtures/` with the source cited and read by both the Rust and Python tests.
- [x] Add `cargo nextest` and `cargo llvm-cov` as optional steps in `scripts/test-suite.sh`.
- [ ] Add `cargo deny` (licenses and advisories) as a CI job. *(Job and `deny.toml` written; `deny.toml` passes locally; the job runs on the next push.)*

**Python**
- [x] `pyproject.toml`: `--strict-markers --strict-config`, `filterwarnings = ["error"]`, a `pandas` marker, and `pytest-cov` with a coverage floor on `python/`.
- [x] Add `hypothesis` tests for container and NaN-policy properties (leading NaN round-trips, output length, container type preserved).
- [x] Broaden Ruff to `B, SIM, RUF, PT, PERF, C4, TID` and fix what it flags.
- [x] Type-check `python/` with a current checker (decide between `ty` and Pyright when implementing).
- [x] Verify `_native.pyi` matches the compiled module with `mypy.stubtest`.
- [x] Replace the empty `tests/python/test_trend.py` and `test_momentum.py` with `test_sma.py` and `test_rsi.py` (per-indicator numerics).
- [x] Fill `tests/python/test_import.py` (no pandas import, public names, `__all__`).
- [x] Fill `tests/reference/test_sma_reference.py` and `test_rsi_reference.py` using the fixtures.

**Scripts, CI and docs**
- [x] Update `scripts/test-suite.sh` (lint, type check, coverage, stub check) and `scripts/README.md`.
- [ ] Update CI to mirror the test suite. *(`ci.yml` updated; not yet run on GitHub.)*
- [x] Update `docs/ARCHITECTURE.md` §8 (Tests and quality checks).

### Part C: Sprint 7.5b, unified logging (about half a day)

Design: Python's `logging` is the one system. Rust uses the `log` macros, and `pyo3-log` forwards them to Python loggers.

- [x] Add `log` to the engine and the bridge, with targets `pyta::engine`, `pyta::planner` and `pyta::bridge`; install `log_bridge.rs` in the `#[pymodule]` (it stands in for `pyo3-log`, whose 0.13.4 needs PyO3 < 0.30) in `rust/crates/pyta-python/src/lib.rs`, so they appear as the Python loggers `pyta.engine`, `pyta.planner` and `pyta.bridge`.
- [x] Add Python-side loggers (`logging.getLogger("pyta.api")` and so on) for validation and batch handling.
- [x] In `pyta/__init__.py`, add a `NullHandler` to the `pyta` logger; never configure handlers or levels.
- [x] Apply the level policy:
  - DEBUG: planner choice (request count, estimated costs, sequential or parallel), pool creation and fork rebuild, column resolution, each failed dataset.
  - WARNING: one summary per batch with failures ("3 of 100 datasets failed").
  - ERROR: a kernel panic caught by `catch_unwind`.
  - No INFO in normal operation.
- [x] Keep logging out of kernels and per-element loops: log from the calling thread at the boundary, after workers finish (`pyo3-log` takes the GIL), behind a level check.
- [x] Keep `pyta-common` and the kernel crates free of `pyo3`; add `env_logger` as a dev-dependency for benchmarks and Rust tests.
- [x] Test with pytest `caplog`: messages from Rust and Python at each level; the library adds no handlers except `NullHandler`; logging works inside the fork test.
- [x] Add a Rust test that the planner logs its choice.
- [x] Performance gate: rerun `./scripts/benchmark.sh --single --python` and `--batch --python`; single-call cost with logging disabled must stay within the ~5% noise of the latest baseline.
- [x] Docs: a "Logging" section in `ARCHITECTURE.md` and in `API.md` (with a 3-line example), a README mention, and a `.claude/memory.md` decision.

### Part D: docs revisions (about 30 min)

- [x] Add **Sprint 7.5** to `docs/DEVELOPMENT.md` after Sprint 7, with Parts B and C as its tasks and the acceptance criteria below.
- [x] Update **Sprint 9** to the current decisions: roles found by name; `columns=[...]` override in any order, assigned to per-indicator slots (a slot may accept several roles, such as `close` or `adj_close`); unrecognized names raise; the role registry stays extensible for fundamentals.
- [x] Add a **Sprint 8** note: decide the category layout at its start (indicator modules are flat today), and `pyta/batch.py` becomes a package for `pyta.batch.trend` and `pyta.batch.momentum`.

### Acceptance criteria for Sprint 7.5

- [x] No empty placeholder test files remain, and SMA and RSI have reference tests from cited published examples.
- [ ] `scripts/test-suite.sh` passes, including lint, type check, coverage floor and stub check, and CI mirrors it. *(The suite passes: `tests/results/test-suite_2026-10-28_14-30-53.txt`. CI not yet run.)*
- [x] `logging.getLogger("pyta").setLevel(DEBUG)` shows Rust and Python messages in one stream; with no configuration the library emits nothing and adds only a `NullHandler`.
- [x] Benchmarks show no regression beyond noise.

### Verification

- [x] `./scripts/test-suite.sh` after Part B and again after Part C (reports kept in `tests/results/`). *(Part C was built first; the suite ran after both parts.)*
- [x] `./scripts/benchmark.sh --single --python` and `--batch --python` after Part C, compared with the latest baseline reports. *(No `--single --python` baseline existed, so `main` was benchmarked in the same session, alternating with this branch; see `.claude/memory.md`.)*
- [x] Manual check: `uv run python -c "import logging, pyta; logging.basicConfig(level='DEBUG'); pyta.batch.sma([[1.0]*50]*20, period=5)"` shows planner and batch messages from both languages.

Out of scope: Sprint 8 itself (namespaces), `tracing` spans, EMA, optional-`period` defaults (dropped), and committing anything (you push manually).

## Parking lot
