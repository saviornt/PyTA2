---
name: pyta-tooling
description: Which skills, MCP servers and tools to use in the PyTA repository (Rust indicator engine plus Python API), and how they are set up here. Read this at the start of any PyTA task that involves navigating code, looking up library docs, reviewing changes, benchmarking or charting, before calling Context7 or the LSP tools in this project, and before delegating PyTA work to an agent (researcher, implementer, reviewer, tester). It names the languages to register with LSP, the libraries worth a Context7 lookup and where their versions are pinned, the PyTA rules for each agent role, and what not to use.
---

# PyTA tooling

PyTA is Rust (Cargo workspace, PyO3 bindings) plus Python (uv, Pydantic, NumPy). The general how-to lives in global skills; this file only says what applies here.

## MCP servers

| Server | Use here | Setup in this repo |
| --- | --- | --- |
| karellen-lsp-mcp | Yes: the default for references, call trees and diagnostics. Follow the `lsp-navigation` skill. | Register the repo root twice: `language="rust"` with `["rust-analyzer"]`, and `language="python"` with `["pyright-langserver", "--stdio"]`. |
| Context7 | Sparingly: follow the `context7-budget` skill. | Libraries and versions below. |
| Finance and market-data connectors | No. PyTA computes indicators; it does not fetch data. | Reference values come from `tests/fixtures/`, not an API. |

## LSP in this repo

- `Cargo.toml` (workspace) and `pyproject.toml` are both at the repo root, so both registrations use the root.
- Run `cargo check --workspace` once if rust-analyzer shows unresolved proc-macro or build-script items.
- `pyproject.toml` sets `[tool.pyright] venvPath = "."` and `venv = ".venv"`, so Pyright resolves NumPy, Pydantic and pandas from the project venv. If imports still show as unresolved, the venv is missing or stale: run `uv sync`.
- `pyta._native` is the compiled extension; Pyright reads its types from `python/pyta/_native.pyi`, so keep the stubs in step with `rust/crates/pyta-python/src/`.
- Good LSP jobs here: every use of an `IndicatorKind` variant across `pyta-engine` (dispatch, cost, planner); callers of a kernel before changing its signature; who calls `_api.run_batch` or the validators in `_validation.py`.

## Context7 in this repo

Versions are pinned in `Cargo.lock` and `uv.lock`; read them there. The installed sources are in `~/.cargo/registry/src/*/` and `.venv/lib/python3.15/site-packages/`, and they come first.

Worth a lookup when local source does not settle it: PyO3 and rust-numpy (APIs change a lot between minor versions; PyO3 ships `guide/` in its crate source, so check that first), maturin build configuration, Pydantic validators, Criterion configuration, new Python 3.15 or Rust 1.99 features.

Not worth a lookup: indicator formulas or TA-Lib behaviour (use `tests/fixtures/`, the TA-Lib source, or `deep-research`), Rayon and NumPy basics, anything in `docs/`.

## Skills

- `add-indicator`: every new indicator, start to finish (spec checkpoint, then every layer, tests, benchmarks and docs).
- `pyta-sprint`: starting, running and closing a sprint (`docs/DEVELOPMENT.md` rules, `TODO.md` plan).
- `pyta-testing`: which tests to run, where new tests go, and how to read the test-suite report.
- `pyta-benchmarks`: which benchmark answers which question, baselines and noise, cost constants.
- `code-review`: before the maintainer pushes a sprint's changes. `simplify` after a feature lands.
- `security-review`: before a public release (FFI boundary, `unsafe`).
- `dataviz`: charts of benchmark results from `benches/results/`.
- `deep-research`: the canonical definition of an indicator when sources disagree (Wilder smoothing, ADX, Stochastic variants).
- `orchestrator` (global): delegating to the agent roles below.

## Agents

The global roles in `~/.claude/agents/` apply here, delegated by default (`orchestrator` skill). PyTA specifics:

- `implementer`: one task per worktree branch; commits there only, never on `main`, never pushes. The maintainer merges with `scripts/merge_into_main.sh`; Claude never runs it, even when told to merge (this overrides the `orchestrator` skill's "unless the user tells you to"). For an indicator, the orchestrator writes the `add-indicator` spec (a `researcher` may gather the sources) and gets it approved by the user, then hands the build to one implementer.
- One indicator at a time unless the user asks otherwise: every indicator edits the same shared files (engine `IndicatorKind`/dispatch/cost, `pyta-python/src/lib.rs`, `_native.pyi`, the `pyta/batch/` and export modules, the README catalog), so parallel implementers would conflict.
- `tester`: runs `scripts/test-suite.sh`, `scripts/benchmark.sh` or the targeted commands in `CLAUDE.md`, following `pyta-testing` or `pyta-benchmarks`.
- A benchmarking tester runs alone: the orchestrator starts no other agent until it finishes, since parallel builds and tests skew the numbers through CPU contention (the tester cannot see other agents).
- `researcher`: for formulas, TA-Lib's convention wins (`add-indicator`); cite `tests/fixtures/` or published sources.
- `reviewer`: review against `CLAUDE.md`, `docs/ARCHITECTURE.md` and the `add-indicator` checklist.

## Project rules that affect tool use

- Commit only on worktree branches, never on `main`; never push. The maintainer reviews, merges into `main` locally and pushes (see `CLAUDE.md`).
- Tests and benchmarks run only through `scripts/test-suite.sh` and `scripts/benchmark.sh`.
