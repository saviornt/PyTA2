---
name: pyta-benchmarks
description: How to benchmark PyTA - choosing the right scripts/benchmark.sh run for a question, preparing the machine, running quick versus full benchmarks, comparing a branch with its base by a same-session A/B run within the ~5% noise, reading the Criterion and Python summaries (auto/best, speedup, Python-layer cost), writing new benchmarks without harness bias, and re-measuring the planner's cost constants. Use this whenever a change could affect performance, the user asks how fast something is or whether it got slower, a sprint has a performance gate, planner or cost constants are involved, or benchmark code in benches/ is written or changed.
---

# Benchmarking PyTA

Every performance change needs a benchmark that justifies it (`CLAUDE.md`), and tunable numbers live in `pyta-common`. `./scripts/benchmark.sh` is the only way to run benchmarks; its report goes to `benches/results/benchmark_<date>_<time>.txt`. Those reports are the long-term history; a change is judged by a same-session A/B run against its base (below), not by an old report.

## Which run answers which question

| Question | Run |
|---|---|
| Did a change to the Python layer or a single call get slower? | `--single --python` (about a minute) |
| Did the batch API get slower? | `--batch --python` |
| Kernel or single-call cost per stage (clone, validation, kernel, direct path) | `--single --rust` |
| Planner, Rayon pool, batch engine | `--batch --rust` |
| One indicator only | add `--indicator <name>` (Rust treats it as a name filter, so mixed workloads match too) |
| Fast feedback while iterating | add `--quick`; never compare quick numbers with full ones |
| Sprint or release baseline | `--all`, full (about 30 minutes) |

Run the smallest run that answers the question. Full Rust runs take long: run them in the background and tell the user what is running.

## Before a run that will be compared

- **Quiet machine:** ask the user to close heavy work; their activity shows up as noise.
- **CPU governor:** check `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`. It is normally `powersave`, which adds variance. For a gate or a sprint baseline, suggest the user switch it to `performance` for the run (it needs `sudo`; give the command, do not run it), and say in the result which governor was used.
- **Same conditions for both arms:** same machine, governor and mode (full or quick). This machine is the 16-thread i9-9900K the planner constants were measured on.
- The Python benchmarks install a release build of the extension; the next `test-suite.sh` run rebuilds the debug one. Nothing else needs doing.

## Comparing with a baseline: same-session A/B

Reports from different days differed by more than the effects being measured, so a performance claim or gate is decided by an A/B run in one session, not by an old report.

1. **Base tree.** From the task worktree, add a scratch worktree of the branch's merge-base with `main` inside it (the path is git-ignored, and a worktree-confined session can reach it): `git worktree add --detach .claude/worktrees/bench-base "$(git merge-base main HEAD)"`. Comparing with `main`'s tip instead would credit the branch with changes made on `main` since it was cut. Never switch branches or stash changes instead.
2. **Warm up.** The base tree has its own `target/` and `.venv`, so its first run compiles everything. Run the gate's flags once with `--quick` in the base tree and discard the report, so neither arm is measured straight after a long build.
3. **Alternate.** Run only the flags the gate needs (usually `--single --python` and `--batch --python`; `--all` full takes about 30 minutes per run) in both trees, alternating: base, branch, base, branch. Each tree writes its own report with its commit in the header. When the expected difference is near the ~5% noise, add a third round of each.
4. **Compare** row by row, using the mean of each tree's runs, and give the ratio (branch / base). **Run-to-run noise is about 5%**: a difference inside it is "no change", not a gain or a regression.
5. **Keep the base reports.** Reports are git-ignored, so `git worktree remove` deletes the base tree's reports with it. First copy them into the task worktree's `benches/results/` with the base commit in the name (`cp .claude/worktrees/bench-base/benches/results/<report>.txt benches/results/base-<commit>_<report>.txt`), then run `git worktree remove .claude/worktrees/bench-base`.
6. **Report** a short table (workload, base, branch, ratio, verdict) and name every report file, base copies included.

Older reports in `benches/results/` remain the history for "how fast is X" and long-term trends; use one for a gate only when an A/B run is impossible, and say so in the result.

## Reading the report

- **`auto/best`** (batch workloads): the planner against the best other strategy for that row. About 1.00x means it chose well.
- **Single-dataset workloads:** `auto` and `sequential` run the same code, so `auto/sequential` should be about 1.00x. If it is not, suspect the benchmark harness before the planner.
- **Python `speedup`** (`bench_batch.py`): loop time divided by batch time. Below 1.0 the batch is slower, which is expected for many tiny datasets.
- **Python-layer cost** (`bench_boundary.py`): `public - native`, about 3.4 µs per call regardless of size. It bounds the speedups possible on small series.
- The Criterion summary only shows results written in this run; a filtered run never shows older numbers.

## Writing or changing benchmarks

- **Same harness for every arm** in `rust/crates/pyta-engine/benches/workloads.rs`: `iter_batched` with the clone made outside the timed section, and results returned so they are dropped outside timing. A `sequential` arm on `iter_with_large_drop` once looked 10–15% slower than identical code.
- Sizes, counts and sample settings are constants in `rust/crates/pyta-common/src/benchmarks.rs`, not literals in the bench files.
- `pyta-engine`'s library target keeps `bench = false`, or Criterion flags such as `--noplot` reach the unit-test harness.
- New indicators register in four places (see `scripts/README.md`, "Adding an indicator"); the `add-indicator` skill covers it.
- Benchmarks never become assertions in tests.

## Planner cost constants

- `rust/crates/pyta-common/src/costs.rs` holds nanoseconds per element per indicator, used by `planner::should_parallelize`. Relative accuracy matters more than absolute.
- Re-measure them after changing a kernel or the engine (`--single --rust`, the `kernel` stage at the largest size). For a new indicator, scale against RSI measured in the same run (see `add-indicator`).
- The 2026-10-27 refit decision stands: the remaining planner misses at 3,000 points cost under 7 µs each; do not re-chase them without new data or a model with a per-element term.
