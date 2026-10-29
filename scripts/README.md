# Scripts

Two scripts run everything: `test-suite.sh` checks correctness and `benchmark.sh` measures performance. Both print progress as they run and write a timestamped report with a summary at the top and the full output of every step below it. Keep the reports: they are the long-term performance history. To judge one change, compare it with its base in the same session (see "Getting reliable numbers").

| File | Purpose |
|---|---|
| `test-suite.sh` | All checks; report in `tests/results/` |
| `benchmark.sh` | All benchmarks; report in `benches/results/` |
| `benchmark_summary.py` | Helper: turns Criterion output into tables (called by `benchmark.sh`) |
| `activate_venv.sh` | Convenience for fish: `source scripts/activate_venv.sh` |
| `merge_into_main.sh` | Maintainer only: merges a reviewed worktree branch into `main` (never pushes) |

Run the scripts from anywhere; they find the project root themselves. They need `cargo`, `uv`, and `python3` on the path.

---

## `merge_into_main.sh`

```bash
./scripts/merge_into_main.sh [BRANCH] [--test] [--clean] [--yes]
```

For the maintainer, after reviewing a worktree branch; Claude never runs it. Run it from the main checkout or from any worktree; it always merges in the main checkout.

- With no `BRANCH`, it finds the worktrees whose branch has commits that `main` lacks. One is merged directly; for several it asks which.
- It fast-forwards if `main` has not moved, and otherwise makes a merge commit with no editor.
- It refuses to start if the main checkout is not on `main`, has uncommitted changes to tracked files, or is mid-merge. It warns if the worktree has uncommitted changes, which the merge does not include.
- It shows the branch's commits and asks before merging (`--yes` skips the question).
- `--test` runs `test-suite.sh` on the merged `main`. `--clean` then removes the worktree and deletes its branch.
- On conflicts it stops: resolve them and `git commit`, or `git merge --abort`.
- It never pushes; run `git push` when ready.

---

## `test-suite.sh`

```bash
./scripts/test-suite.sh
```

No options. Steps, in order:

| # | Step | Notes |
|---|---|---|
| 1 | `cargo fmt --all` | Fixes Rust formatting in place, like CI. The report notes how many places it fixed |
| 2 | `cargo fmt --all -- --check` | Confirms formatting is clean |
| 3 | Clippy | `-D warnings` |
| 4 | `cargo test --workspace` | |
| 5 | Build Python extension | `maturin develop` (debug build) |
| 6 | Smoke test | `tests/smoke/test_smoke.py` |
| 7 | pytest | With the pandas extra. Strict markers and config, warnings as errors, and branch coverage of `pyta` with a floor (`--cov-fail-under` in `pyproject.toml`) |
| 8 | Ruff lint | `ruff check python tests` |
| 9 | Ruff format check | `ruff format --check python tests` |
| 10 | Type check | `pyright` in strict mode on `python/` |
| 11 | Stub check | `python -m mypy.stubtest pyta._native`: `_native.pyi` matches the compiled module |
| 12 | `cargo nextest run` | Optional: skipped if `cargo-nextest` is not installed |
| 13 | `cargo llvm-cov` | Optional: Rust line and region coverage; skipped if `cargo-llvm-cov` is not installed. Uses rustup's `llvm-tools` component, or else the system `llvm-cov`/`llvm-profdata` |

Every step runs even if an earlier one fails, so one run shows everything that is broken. The exit status is non-zero if any step failed. A skipped optional step does not fail the run.

The optional tools are in the Arch repositories: `sudo pacman -S cargo-nextest cargo-llvm-cov`. `cargo-deny` (licenses and advisories, `deny.toml`) runs as its own CI job; locally, `cargo deny check licenses advisories`.

**Report:** `tests/results/test-suite_YYYY-MM-DD_HH-MM-SS.txt`. The top has the result, duration, commit and whether the tree has uncommitted changes, tool versions, a step table with timings, Rust and Python test counts, and Python and Rust coverage.

> Step 1 changes files. If it reports a fix, review the diff before committing.

---

## `benchmark.sh`

```bash
./scripts/benchmark.sh (--single | --batch | --all) [options]
```

With no arguments it prints usage and exits, because a full run takes about 30 minutes.

### What to run

| Flag | Runs |
|---|---|
| `--single` | One dataset per call, through the direct path |
| `--batch` | Many datasets per call, through the batch path |
| `--all` | Both |

### Options

| Option | Effect |
|---|---|
| `--rust` | Only the Rust (Criterion) benchmarks |
| `--python` | Only the Python benchmarks (no Criterion, about a minute) |
| `--indicator NAME` | Only one indicator, for example `sma`. Rust uses it as a name filter, so mixed workloads such as `3_sma_rsi_ds1` match both `sma` and `rsi` |
| `--quick` | Shorter runs for fast iteration. The report says QUICK; do not compare those numbers with full runs |
| `-h`, `--help` | Show usage |

With neither `--rust` nor `--python`, both layers run.

### What each combination runs

| | `--single` | `--batch` |
|---|---|---|
| **Rust** | `single_call` (Criterion): per indicator and size, the cost of each stage of one call: clone, validation, kernel, and `execute_direct`; the `engine` stage times the async `execute_batch` path with one request | `workloads` (Criterion): `sequential`, `parallel` (Rayon), `batch` (async front door), and `auto` (the planner) for one to four requests; plus few-request runs (3 / 5 / 10 requests of 100 to 10k points, `few_*`) and many-dataset runs (10 / 100 / 1,000 datasets of 100 / 1k / 10k points) |
| **Python** | `bench_boundary.py`: public call vs native call vs a plain copy, so the Python-layer cost is `public - native` | `bench_batch.py`: `pyta.batch` vs a loop of single calls, as time per dataset and speedup |

The Python benchmarks use a release build of the extension, which the script installs first. That replaces the debug extension from `test-suite.sh`; the next `test-suite.sh` run rebuilds it.

### Examples

```bash
./scripts/benchmark.sh --all                          # everything, full (slow)
./scripts/benchmark.sh --batch --python --quick       # fast check after changing the batch API
./scripts/benchmark.sh --batch --rust                 # tuning the planner or batch engine
./scripts/benchmark.sh --single --indicator rsi       # one indicator, single calls
```

### Reading the report

`benches/results/benchmark_YYYY-MM-DD_HH-MM-SS.txt` has, in order: result and timing, the options used, the environment (commit, tool versions, CPU, CPU governor), a step table, the summary tables, and the full output of every step.

- **`auto/best`** compares the planner with the best other strategy for that row. A value near 1.00x means the planner chose well. In the single-dataset workloads, `auto` and `sequential` run the same code, so the ratio should be about 1.00x; if it is not, suspect the benchmark harness before the planner.
- **Python `speedup`** is the loop time divided by the batch time. Below 1.0, the batch call is slower. Expect that for many tiny datasets, where per-dataset Python work dominates.
- The Criterion summary only includes results written during this run, so a filtered run never shows numbers from an earlier one.

### Getting reliable numbers

- Run on a quiet machine and close other work. Run-to-run noise is about 5%.
- A `powersave` CPU governor (shown in the report) adds variance. Setting it to `performance` for the run makes results more repeatable.
- Compare reports from the same machine, governor, and mode (full vs quick).
- To judge a change, run its base and the branch in the same session, alternating (base, branch, base, branch), with the base in a scratch worktree. Reports from different days can differ by more than the effect being measured. The `pyta-benchmarks` skill has the steps.
- Planner constants in `rust/crates/pyta-common` are measured on a specific machine; re-measure them after changing the kernels or the engine.

### Adding an indicator

Add one line to `INDICATORS` in each of `rust/crates/pyta-engine/benches/single_call.rs`, `benches/python/bench_boundary.py`, and `benches/python/bench_batch.py`, and one entry to the loop in `many_datasets` in `rust/crates/pyta-engine/benches/workloads.rs`. The script itself needs no change.
