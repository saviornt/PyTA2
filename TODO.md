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
[x] 2. RSI period == len error: it reports `PeriodExceedsLength`, but the real problem is that RSI needs period + 1 points. Add an `InsufficientData` variant.
[x] 3. Single-call overhead: one call goes through Tokio, a worker, Rayon and a oneshot channel. Benchmark a direct-dispatch fast path.

### Packaging
[x] 1. LICENSE is not MIT: it’s the X11 text with a non-advertising clause, a leftover “X CONSORTIUM”, and <...> placeholders, while pyproject.toml and Cargo say MIT. Use the standard MIT text.
[x] 2. No `_native.pyi` stub despite `py.typed`, so type checkers see an untyped module.
[x] 3. `numpy` is declared in the workspace but unused. Use `PyReadonlyArray1` for NumPy input. Currently `Vec<f64>` copies everything - check this to ensure we are using Numpy input.


### Minor Issues
[x] 1. `batch.rs` guards results with a mutex. A `JoinSet` returning (index, result) is simpler and lock-free.
[x] 2. SMA’s running sum accumulates drift on long series. Consider periodic recompute or Kahan summation.
[x] 3. `pyta-engine` declares `thiserror` but doesn’t use it.
[x] 4. `test-suite.sh` runs Rust only (no `cargo fmt --check`, no `pytest`) and calls `clear`.

### Script Updates
[x] 1. Create a script to run benchmark tests on pyta-engine.
[x] 2. Generate a summarized report after the Criterion benchmark.

### Python API
[x] 1. Create the python API to connect to the Rust backend
[x] 2. Create benchmarks and pytest for testing and optimization
[x] 3. Optimization (see note 1)


> Note 1: Python layer: a fixed ~3–5 µs per call. The 55–78 µs at 1M is 1–2% of a 4 ms call, which is timing noise, since nothing in the Python layer scales with n. That fixed cost is large next to a 0.2 µs kernel at n=100, but small at realistic sizes. Users with thousands of small series are who the batch API (Sprint 7 in `docs/DEVELOPMENT.md`) is for. The finding is the native boundary at large n. At 1M elements it costs about as much as the calculation itself, 1.2–1.8 ms against 2–3.3 ms for the kernel. The memcpy accounts for at most ~0.3 ms, from the copy column. The rest is unexplained, and the best guess is the finite-value scan in Series::new, since position(|v| !v.is_finite()) exits early and may not vectorize. Fresh-allocation page faults are another possibility.
> Measuring it: In `single_call.rs`, change `Series::new(data)` to `Series::new(data.clone())` and add the following code inside the loop:

```rust
group.bench_with_input(BenchmarkId::new("series_new", n), &data, |b, d| {
    b.iter_batched(
        || d.clone(),
        |values| Series::new(values).unwrap(),
        BatchSize::LargeInput,
    );
});
```
> then run `cargo bench -p pyta-engine --bench single_call -- series_new`. If the scan is ~1 ms at 1M, speeding it up should be a small, safe change to `input.rs`. If it's small, then look at the allocation and page-fault side instead.

---

# Daily Scratchpad

> This section is for **what we are doing today**. Sprint plans and long-term work live in `docs/DEVELOPMENT.md`; do not duplicate them here. At the end of each day, delete finished items, move anything lasting into `docs/DEVELOPMENT.md`, and carry unfinished items forward.

## Today — 2026-10-27

**Focus:** Finish the documentation reset, then get CI working.

### Done today
- [x] Rewrite `README.md`.
- [x] Rewrite `docs/ARCHITECTURE.md` (replaces the stale `pyta_core.md`).
- [x] Rewrite `docs/API.md`.
- [x] Write `docs/DEVELOPMENT.md` (replaces `DEV_PLAN.md`).
- [x] Reset this file.

### To do
- [x] Delete the stale `DEV_PLAN.md` and any leftover `pyta_core.md` or old doc folders, so `docs/` holds only `API.md`, `ARCHITECTURE.md`, and `DEVELOPMENT.md`.
- [x] Finish the Python optimization as noted above.
- [ ] Fill in `.github/workflows/ci.yml` (currently empty): format check, Clippy, Rust tests, extension build, pytest, Ruff. Reuse the steps in `scripts/test-suite.sh`.
- [ ] Run `scripts/test-suite.sh` locally and confirm everything passes.
- [ ] Verify `docs/API.md` against the code: `rsi` default period, `column` aliases, the period range, masked-array handling, and the error table.
- [ ] Compare the real error messages with the examples in the `API.md` Errors section, then fix the code or the docs.
- [ ] Verify the Sprint 2–6 acceptance criteria and mark the sprints `✓` in `docs/DEVELOPMENT.md` where they pass.
- [ ] Python API optimization: run the `series_new` benchmark from Note 1.

### Decisions needed
- [ ] README data-provider wording. Suggested: "Accepts the data formats returned by yFinance (pandas, dict, tuple) and AlphaVantage (JSON, CSV)." Currently the README says PyTA will "support loading market data" from them.
- [ ] Valuation indicators: which ones belong in the planned list (currently "To be determined" in the README).
- [ ] Platforms for prebuilt wheels at release (Linux, macOS, Windows, and which architectures).

## Up next — Sprint 7: Batch API

See `docs/DEVELOPMENT.md` for the full sprint. Start with:

- [ ] Bind `execute_batch` in `pyta-python`, releasing the GIL.
- [ ] Add a `pyta.batch` module with `sma` and `rsi`, mirroring the top-level signatures.
- [ ] Accept a list or a mapping of datasets, returning the same shape and order.
- [ ] Return the exception in place of the result for any dataset that fails.
- [ ] Add pytest coverage for ordering, mixed containers, and partial failures.

## Parking lot

Ideas and loose ends that are not scheduled yet:

- EMA initialization convention (SMA seed or first value) must be decided before implementing it.
- `release.yml` is also empty; fill it in during Sprint 14.
- Decide how multi-column indicators map `columns=[...]` to roles (order only, or order plus names).