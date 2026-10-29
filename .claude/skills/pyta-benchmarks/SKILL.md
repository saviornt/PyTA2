---
name: pyta-benchmarks
description: How to benchmark PyTA - choosing the right scripts/benchmark.sh run for a question, preparing the machine, running quick versus full benchmarks, finding the baseline report, comparing runs within the ~5% noise, reading the Criterion and Python summaries (auto/best, speedup, Python-layer cost), writing new benchmarks without harness bias, and re-measuring the planner's cost constants. Use this whenever a change could affect performance, the user asks how fast something is or whether it got slower, a sprint has a performance gate, planner or cost constants are involved, or benchmark code in benches/ is written or changed.
---

# Benchmarking PyTA

Every performance change needs a benchmark that justifies it (`CLAUDE.md`), and tunable numbers live in `pyta-common`. `./scripts/benchmark.sh` is the only way to run benchmarks; its report goes to `benches/results/benchmark_<date>_<time>.txt`, and those reports are the history to compare against.

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
- **CPU governor:** check `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`. It is normally `powersave`, which adds variance. For a baseline, suggest the user switch it to `performance` for the run (it needs `sudo`; give the command, do not run it), and say in the result which governor was used.
- **Same conditions as the baseline:** same machine, governor and mode (full or quick). This machine is the 16-thread i9-9900K the planner constants were measured on.
- The Python benchmarks install a release build of the extension; the next `test-suite.sh` run rebuilds the debug one. Nothing else needs doing.

## Comparing with a baseline

1. The baseline is the latest report in `benches/results/` with the same flags and mode, from before the change. The report header lists the options, commit, CPU and governor; check they match. If there is no matching baseline, ask the user for one from the unchanged code; never switch branches or stash changes yourself.
2. Compare row by row and give the ratio (new / old). **Run-to-run noise is about 5%**: a difference inside it is "no change", not a gain or a regression.
3. A result that matters (a gain claimed for a change, or a regression near a gate) is repeated once; report both runs.
4. Report a short table: workload, old, new, ratio, verdict. Name both report files.

## Reading the report

Read only the top of a report: the header, Steps, and the Criterion / Python single / Python batch summaries. Stop at the `FULL RESULTS` heading, which is the long raw log:

```bash
sed '/^FULL RESULTS/q' benches/results/benchmark_<date>_<time>.txt
```

Open Full Results only to debug a step that failed or looks odd, and then grep for that step (sections are headed `<n>. <step name>  [STATUS, Ns]`) instead of reading the whole log, for example `grep -n -A 40 '^2\. Rust batch' <report>`. The Criterion summary step's output is printed only in the top section. Give spawned agents (tester, reviewer) the same rule in their brief.

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
