# TODO Scratchpad — PyTA

## Sprint 12.5: performance against TA-Lib (planned 2026-10-30)

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 12.5 — Performance against TA-Lib". Goal: PyTA as fast as TA-Lib or faster in every comparison cell, with accuracy kept (1e-9 to every fixture; no cell's difference from TA-Lib above Sprint 12's 8.7e-12). Yardstick: `PyTA-Integration/benchmarks/compare_talib.py` (Sprint 12 baseline `docs/benchmarks/talib_comparison_2026-10-30.md`) plus `--single --rust` stages and same-session A/Bs against the Sprint 12 tip.

Carried over from Sprint 12 (parking lot): `period=True`'s message wording; Aroon 1 ulp below 100 for some periods.

Where things stand (measured 2026-10-30, governor `performance`, release builds):
- **Kernels are slow, not only the bridge.** `--single --rust --quick` at 1,000,000 rows (`benchmark_2026-10-30_23-12-26` to `_23-12-56`): kernel EMA 2.89 ms, DEMA 3.18, TEMA 3.48, ATR 4.53, OBV 2.35, SMA 1.94; `Series::from_slice` (copy + validation) ~0.5 ms per column. TA-Lib's whole call: EMA 0.93 ms, ATR 1.5, OBV 3.4, SMA 1.8.
- **EMA's dependency chain.** `kernels::ema_step` is `(x - prev) * k + prev`: sub, mul, add in the loop-carried chain (~12 cycles, 2.9 ns/row). TA-Lib's `beta * prev + k * x` has `k * x` off the chain (mul + add, ~8 cycles; ~4 fused). Same for every `ema_step` user (EMA, DEMA, TEMA, MACD, TRIX, Keltner middle). `WilderAverage` already has the short form.
- **ATR** costs 4.5 ns/row in the kernel against TA-Lib's ~1.5 for the whole call: cause unknown (true range + Wilder should be ~2).
- **Unexplained bridge time.** `pyta.obv` on two 1M columns: 7.6 ms; kernel 2.35 + two copies ~1.0 + `reject_negative` ~0.5 leaves ~3.7 ms (allocation and page faults of three 8 MB buffers? `Columns` building? a second scan?). A fresh 8 MB NumPy alloc+touch costs 0.18 ms; THP is `always`.
- **Python layer.** NumPy single call ~3.7 µs (SMA, 100 rows) against TA-Lib 1.7; multi-column dict 10-15 µs (ATR, STOCH, OBV) against 1.4-3.3; DataFrame 140-180 µs against 16-57 (pandas column access and per-column conversion); batches pay per-dataset Python validation (100 x 100 NumPy 0.48x median).
- **Where PyTA already wins:** ADX, Aroon, CCI at 10,000+ rows (van Herk extremes, fused passes); large NumPy batches (Rayon).
- Sprint 17 ("Performance tuning") stays for later scaling; this sprint is the TA-Lib gap for the current 29 indicators.

### Part A: start and decide (about 30 min)

- [x] A1. **Goal and speed targets.** *(2026-10-30, user: every Part A recommendation approved as written.)* **Goal raised by the user (2026-10-30): as fast as TA-Lib or faster in every cell (ratio ≥ 1.0x), with accuracy kept (every fixture to 1e-9, and no comparison cell's largest difference above Sprint 12's 8.7e-12 relative).** The numbers below are the floors for closing the sprint; a cell between its floor and 1.0x is parked with its cause and the next step. *Recommend* (ratios TA-Lib / PyTA from `compare_talib.py`, full run): (a) single, NumPy, 1,000,000 rows: median ≥ 1.0x, none below 0.8x; (b) single, NumPy, 10,000 rows: median ≥ 0.9x; (c) single, NumPy, 100 rows: median ≥ 0.7x (Python layer ≤ ~2.5 µs single-column, ≤ ~4 µs multi-column); (d) DataFrame, 100 rows: median ≥ 0.4x; (e) batch NumPy 100 x 10,000 and 1,000 x 1,000: median ≥ 1.2x; batch DataFrame: median ≥ 0.5x. Indicators TA-Lib lacks: no regression beyond noise.
- [x] A2. **EMA recurrence form.** *Recommend:* switch `ema_step` to TA-Lib's unfused `beta * prev + k * x` (`beta = 1 - k`), shortening the chain; changes EMA/DEMA/TEMA/MACD/TRIX/Keltner bits within the tolerance policy (TA-Lib's plain form was within 3.9e-12 of TRIX's fixtures; check every fixture); keep DEMA/TEMA/TRIX bit-identical to their cascaded `kernels::ema` definitions.
- [x] A3. **Runtime FMA dispatch** (`#[target_feature(enable = "fma")]` + `is_x86_feature_detected!`, as TA-Lib's `TA_FMA_MULTIVERSION`). *Recommend:* not now: results would differ between CPUs with and without FMA, and the bit-parity policy (2026-10-30) chose plain multiply-adds; revisit only if A2 leaves the EMA family below target.
- [x] A4. **Input copy.** The bridge copies each column so the GIL can be released. *Recommend:* keep the copy (thread safety), but fuse every per-value check into it (finite, magnitude, negative volume) so input is read once; borrowing without a copy (GIL held) only if B1 shows the copy, not allocation, is the cost.
- [x] A5. **Allocator / page faults.** *Recommend:* decide after B1; if allocation and first-touch dominate, try reusing or pre-faulting buffers before a new dependency; a global allocator (mimalloc) only with an A/B and your approval (new dependency).
- [x] A6. **SIMD.** *Recommend:* rely on auto-vectorization of non-recursive passes (true range, typical price, copies, ROC); no nightly `std::simd`, no SIMD crate.
- [x] A7. **Python fast paths.** *Recommend:* a fast path for the common cases (one C-contiguous float64 array; a dict of them; a DataFrame with exact role names) that skips the general container machinery, measured with interleaved `timeit` like Sprint 10's; behaviour and errors unchanged (the integration tests pin messages).

### Part B: measure (about 3 h; researcher/tester)

- [ ] B1. Stage breakdown for SMA, EMA, RSI, MACD, ATR, STOCH, BBANDS, OBV at 100, 10,000, 1,000,000 rows (NumPy and DataFrame): Python layer (`cProfile`/`timeit`), copy + validation, kernel (`--single --rust` stages), output, allocation (`perf stat -e page-faults`, `perf record` on the 1M calls). Explain OBV's ~3.7 ms.
- [ ] B2. Each slow kernel against TA-Lib 0.8.3's C loop (EMA family, ATR, ADX, RSI, STOCH, WILLR, MFI, BBANDS/STDDEV, SAR, OBV, AD): dependency chain, divisions, branches, passes, allocations. Output: a ranked list (expected gain, risk to bits) in this file.
- [ ] B3. Baseline: full `compare_talib.py` and `--single --python` / `--batch --python` on the Sprint 12 tip (reuse `talib_comparison_2026-10-30.md` if the machine state matches).

### Part C: kernels (about 6 h; implementer per kernel family, `pyta-benchmarks` A/B each)

- [ ] C1. EMA family per A2 (`ema_step` and every user); fixtures to 1e-9; DEMA/TEMA/TRIX proptests still bit-identical to cascades.
- [ ] C2. ATR, ADX and the shared true range / Wilder kernels.
- [ ] C3. The next kernels from B2's ranking (rolling extremes: STOCH, WILLR, Donchian, Ichimoku; BBANDS/STDDEV; MFI; SAR), one commit each.
- [ ] C4. Planner cost constants re-measured for every changed kernel (batch rows near break-even, memory "Cost constants near the crossover").

### Part D: native call and memory (about 3 h)

- [ ] D1. Fix the cause B1 finds for the time beyond copy + kernel (OBV and multi-column first).
- [ ] D2. Fuse Python's negative-volume scan and any other per-value pass into the Rust copy (A4), keeping error messages (column and row).

### Part E: Python layer (about 4 h)

- [ ] E1. Single-array and dict-of-arrays fast paths (A7); interleaved `timeit` against the Sprint 12 tip.
- [ ] E2. DataFrame: extract the needed columns once, as NumPy, without per-column pandas overhead; index restore unchanged.
- [ ] E3. Batch: per-dataset validation cost (100 x 100 and 1,000 x 1,000 rows).

### Part F: close (about 2 h)

- [ ] F1. Full `compare_talib.py`; README tables replaced (Sprint 12 baseline kept in `docs/benchmarks/`), with before/after medians.
- [ ] F2. Full `--all` benchmark run; test suite; `PyTA-Integration/scripts/setup.sh`.
- [ ] F3. Docs (`ARCHITECTURE.md`, `API.md`, wiki, memory); `DEVELOPMENT.md` ticks, retrospective and ✓ once the criteria pass.

### Acceptance criteria for Sprint 12.5

- [ ] Every TA-Lib reference fixture still matches to 1e-9; `./scripts/test-suite.sh` passes.
- [ ] Each adopted change has a same-session A/B benchmark showing its gain.
- [ ] Every comparison cell is at least its A1 floor; cells below 1.0x are listed with their cause and next step.
- [ ] No comparison cell's largest difference from TA-Lib exceeds 8.7e-12 relative (Sprint 12's worst).
- [ ] The README comparison is current and reproducible from `PyTA-Integration/`.

### Verification

- [ ] `./scripts/test-suite.sh` after each part and at close (cite the reports).
- [ ] `PyTA-Integration/scripts/setup.sh --bench` and a full `compare_talib.py` at close.
- [ ] Benchmark reports cited for every A/B.

Out of scope: new indicators, runtime FMA dispatch (unless A3 is reopened), text-input (CSV/JSON) parsing speed, async API, CI (Sprint 13).

## Parking lot

- `bench_boundary.py` single-column rows time only NumPy input; Series, list and dict inputs are not benchmarked. Its `**params` call adds ~0.1 µs that `main`'s did not.
- A CCI batch row (100 × 1,000) read +8.7% in one implementer's A/B but +3.9% in the final one; check with `--batch --rust` if it recurs.

- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
- CI had not run when Sprint 9 closed; check it is green after the maintainer's push.
- Chaining from a multi-output frame needs the Series (`pyta.sma(out["macd_signal"], ...)`), since `column=` takes role names only; revisit if users ask.
- Bare output names (A5) collide when two runs of one indicator (say SMA 20 and SMA 50) are joined into one frame; the caller renames. Revisit if users ask for a `name=` option.
- AlphaVantage's nested JSON time series (dates as keys, `1. open` names, numbers as strings) would need a provider adapter; decide whether one belongs in PyTA (Sprint 11, A6).
- CSV and JSON text cost 15-70x an array call at 100 rows (parsing dominates: SMA CSV 99 µs, JSON records 211 µs); a faster parser (or `np.loadtxt`-style bulk conversion) is a Sprint 17 candidate if text input matters.
- A nested multi-column dict column reads `column 0 expected a 1-D series ...` (the slot number as the name); reword if users meet it.
- Delete the merged agent worktrees and branches (`.claude/worktrees/agent-*`, `worktree-agent-*`) once the sprint is merged.
- `ma=` option (TA-Lib `matype`) for BBANDS and STOCH, reusing the Sprint 11.5 kernels (A5).
- VWAP session or date anchoring; needs a datetime role (A9).
- Further indicators: Stochastic RSI, PPO, Momentum, CMO, Hull MA, Supertrend, Pivot Points, ROCP/ROCR/ROCR100, ADXR, PLUS_DI/MINUS_DI alone (A14).

- The CCI 10 x 10,000 batch cell flips between ~60 and ~95 µs/dataset on `main` too; check whether it is the planner's crossover. CCI's cost constant reads +25% at 1M rows but every batch row chooses right (2026-10-30), so it stays.
- `pyta.sma(x, period=True)` raises `period must be an integer, not bool` while a str gives `..., got str` (`_validation.py`); `API.md` §7 shows only the "got" form. The integration tests pin the current wording.
- Aroon: for periods 97, 161, 167, 193-195, 199, 289 `(100 / period) * period` is 1 ulp below 100 (within range and tolerance); write exactly 100 when the extreme is the current row if users notice.
