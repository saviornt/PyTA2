# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

PyTA is a TA-Lib replacement: a Python API that cleans/validates user data and a Rust backend that calculates indicators. Python 3.15+ and Rust 1.99.1+ (edition 2024). `docs/ARCHITECTURE.md` is the authoritative design; `docs/DEVELOPMENT.md` holds the sprint plan; `TODO.md` is the daily scratchpad. Update the docs in the same change as code that alters them.

## Workflow rules

- Commit only on a worktree branch (one task per worktree); never commit to, stage on or merge into `main`, and never `git push`. The maintainer reviews the branch, merges it into `main` locally with `scripts/merge_into_main.sh` (never run it yourself) and pushes.
- Be concise in answers. Use the latest stable Rust and Python, no deprecated APIs.
- Every performance change needs a benchmark justification; tunable numbers go in `pyta-common`, not inline.
- Tooling (LSP, Context7, review skills): read the `pyta-tooling` skill. Prefer the LSP tools over grep for references and call trees.

## Commands

```bash
./scripts/test-suite.sh      # fmt, Clippy, cargo test, build ext, smoke, pytest+coverage, ruff, pyright, stubtest, optional nextest/llvm-cov; report in tests/results/
./scripts/benchmark.sh --single|--batch|--all [--rust|--python] [--indicator NAME] [--quick]   # report in benches/results/ (quiet machine; see scripts/README.md)

# Build/install the extension into .venv (required before pytest sees Rust changes)
uv run maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml

cargo test --workspace
cargo test -p pyta-trend sma                          # one Rust test (filter by name)
cargo clippy --workspace --all-targets --all-features -- -D warnings
uv run --extra pandas pytest                          # pandas is optional; tests need the extra
uv run pytest tests/python/test_batch.py::test_mapping_keeps_keys_and_order   # one Python test
uv run ruff check python tests && uv run ruff format --check python tests
cargo bench -p pyta-engine --bench workloads -- --noplot sma   # one Criterion target, name filter
```

CI (`.github/workflows/ci.yml`) auto-runs `cargo fmt --all` and commits the result, so run it locally too. `RUSTFLAGS=-D warnings` in CI.

## Architecture (big picture)

Data flows: user container → Python layer (clean/validate → 1-D float64 array, or one per slot for a multi-column indicator, matched by role) → `pyta._native` (PyO3, GIL released) → `pyta-engine` → category crate kernel → back to Python, which restores the caller's container type.

Crate dependency direction: `pyta-common` (constants only, no deps) ← `pyta-core` (Series/Ohlcv, IndicatorOutput, PytaError) ← category crates (`pyta-trend`, `pyta-momentum`; one indicator per file) ← `pyta-engine` ← `pyta-python`. Only `pyta-python` depends on PyO3/NumPy. Indicator formulas live only in Rust, never in Python.

Key rules that span files:
- **Division of validation.** Python handles containers, column selection, `None`/leading-NaN skipping (so indicators chain), `period` type/range (Pydantic), and checks across columns (high not below low). Rust is strict: rejects empty input, any non-finite value, and columns of unequal length or count.
- **Multi-column input.** Rust: `pyta-core::Columns` (equal-length `Series` in slot order); `IndicatorRequest.input` is `IndicatorInput::{Series, Columns}`; dispatch takes `input.series()` or `input.columns::<N>()`. Python: roles in a registry (`_validation.register_role`), each indicator declares `SLOTS`, `_columns.normalize_columns` matches them, `_api.run_columns`/`run_columns_batch` run them. `column=` is single-column only, `columns=` multi-column only. Output length equals input length, with `NaN` warm-up.
- **Two engine paths** sharing one `dispatch`: `execute_direct` (single dataset, calling thread, panics caught → `ExecutionFailed`) and the batch path `execute_parallel` (Rayon `par_iter`; `execute_sequential` is the same loop on one thread; `execute_batch` is only an async front door that hands the batch to Rayon in one hop). `planner::should_parallelize(requests, workers)` picks sequential vs parallel from cost estimates. The bridge owns a Rayon pool that is rebuilt after `fork()`. Adding an `IndicatorKind` must fail to compile until it has a dispatch arm and cost constant (`pyta-common/src/costs.rs`).
- **Errors.** `PytaError::ExecutionFailed` → `RuntimeError`; everything else → `ValueError`; Python raises `TypeError` for unsupported types.
- **Batch API (`pyta.batch.*`).** Takes a list or mapping; a failing dataset is returned *as its exception object in place*, never raised, so other datasets complete. Python validates each dataset first (`_api.run_batch`), valid ones go to Rust in one call. `period`/`column` are shared and raise for the whole call.
- **Per-indicator modules.** Each indicator has `python/pyta/indicators/<category>/<name>.py` (single + batch function) and `rust/crates/pyta-python/src/<name>.rs` (bindings). The category `__init__.py`, `pyta/indicators/__init__.py`, `pyta/<category>.py`, the `pyta/batch/` package and `pyta-python/src/lib.rs` only re-export/register, so `pyta.trend.sma is pyta.sma` (`docs/ARCHITECTURE.md` §5 "Adding a category"); shared plumbing is in `_api.py` and `single.rs`/`batch.rs`/`error.rs`.
- **Module naming** must stay consistent: `module-name = "pyta._native"` in `pyproject.toml`, `[lib] name = "_native"`, and the `#[pymodule]` function name. `pyta._native` is internal; its stubs are in `_native.pyi`.

Adding an indicator touches: category crate → engine `IndicatorKind`/dispatch/cost → `pyta-python/src/<name>.rs` + registration in `lib.rs` → `_native.pyi` → `indicators/<category>/<name>.py` + exports (category `__init__.py`, `indicators/__init__.py`, `pyta/<category>.py`) → `pyta/batch/<category>.py` + `pyta/batch/__init__.py` → tests (`tests/python/`, Rust unit/integration/proptest, `tests/fixtures/` + `tests/reference/`) → `docs/API.md`, `docs/indicators/` (per-indicator wiki, one page per indicator), README catalog (the `add-indicator` skill walks through every step).

`import pyta` must not import pandas (it is optional and only recognized if the caller already imported it).

@memory.md
