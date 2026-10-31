# TODO Scratchpad — PyTA

## Sprint 12: independent integration project ✓ (planned 2026-10-30, closed 2026-10-30)

**Still open after close** (parking lot): PyTA is slower than TA-Lib in most single calls and small batches (README "Performance against TA-Lib"); the next sprint should be performance. Also `period=True`'s message wording, Aroon's 1-ulp-below-100 periods.

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 12 — Independent integration project". Goal: validate PyTA as an external consumer sees it (installed wheel, public API only), settle the numeric calls parked at Sprint 11.5's close, and measure PyTA against TA-Lib the way each is used in production, single calls and batches.

Where things stand:
- **Parked numeric calls** (Sprint 11.5 close): fma policy, ROC's ±inf on a tiny non-zero base, Aroon's 100 + 1 ulp. Decided in A2-A4 and built in B1-B3 (2026-10-30). Every fixture passes at 1e-9.
- **`f64::mul_add`** without `target-feature=+fma` is a libm call (KAMA 7.39 against 3.39 ms per 1e6 rows); PyPI wheels target baseline x86-64, so fused arithmetic needs runtime CPU dispatch to be fast.
- **Cost constants:** SMA reads +29% and CCI +25% at 1M rows, STDDEV's period term was never swept, `many_wma_x100` picks parallel at 1.16x. Lesson (memory, "Cost constants near the crossover"): fit cheap kernels from the 10 x 1,000 and 100 x 100 batch rows, not by scaling 1M-row times against RSI.
- **Packaging:** PyTA builds with maturin (`pyproject.toml`); the dev `.venv` uses `maturin develop`, release only in `benchmark.sh`. No wheel has been built and installed into a clean environment yet.
- **TA-Lib:** PyPI `TA-Lib==0.8.3` installs on Python 3.15 (`tests/reference/generate_talib_fixtures.py` does so in a throwaway env). TA-Lib accepts NumPy arrays and pandas Series; it has no batch call.
- **Machine:** governor currently `performance` (2026-10-30).

### Part A: start and decide (about 30 min)

- [x] A1. Confirm the goal and acceptance criteria (tracking rule 1). *(2026-10-30, user: A2, A4, A5 as recommended; A3 changed, see below.)*
- [x] A2. **Bit-parity / fma policy.** *Recommend:* tolerance, not bits: PyTA promises agreement with TA-Lib 0.8.3 within 1e-9 (fixture tolerance, unchanged) and keeps plain multiply-adds everywhere; no `mul_add`, no runtime FMA dispatch. Bit-for-bit would need per-function fused arithmetic and CPU dispatch to stay fast, for differences ≤4e-13 relative. Implement as docs: `ARCHITECTURE.md` numerical conventions, `API.md`, memory; remove the stale "bit for bit with INT_EMA" claim in `kernels::ema` if it is wrong.
- [x] A3. **ROC/VROC on a tiny non-zero base.** *Recommended* keeping TA-Lib's exact `!= 0.0` guard and ±inf. **User's decision (2026-10-30): scaled zero test → 0.** `kernels::rate_of_change_into` returns 0 when `is_zero_scaled(earlier, |current|)` (|earlier| ≤ 1e-14·|current|, exact 0 included), so every output is finite (|ratio| < 1e14). Shared by ROC, Volume ROC and TRIX's last step.
- [x] A4. **Aroon 100 + 1 ulp.** *Recommend:* clamp `aroon_up`/`aroon_down` to [0, 100] and the oscillator to [-100, 100] (as RSI is clamped), so the documented range holds; within the A2 tolerance of TA-Lib.
- [x] A5. **Integration project location.** *Recommend:* `PyTA-Integration/` in this repository's root (as `DEVELOPMENT.md` names it), with its own `pyproject.toml`, `uv.lock` and `.venv`, not a workspace member, never imported by PyTA's tests or tooling; PyTA installed from a release wheel built by `maturin build --release` into `PyTA-Integration/dist/` (git-ignored). TA-Lib and pandas are in its optional `bench` extra / dependencies only.
- [x] A6. *Recommend (no decision needed unless you object):* AlphaVantage JSON example flattens the nested `Time Series (Daily)` object in the example with the stdlib and reverses it to oldest first (PyTA never reorders); a provider adapter stays parked. Benchmarks use TA-Lib's defaults made explicit on both sides, and the same synthetic random-walk OHLCV (seeded) for 10,000 and 1,000,000 rows, SPY for 100 rows.

### Part B: numeric decisions in PyTA (about 2 h)

- [x] B1. Implement A2: docs (`ARCHITECTURE.md`, `API.md`, wiki notes for SAR, TRIX, EMA family, KAMA), memory, parking-lot entry removed. *(2026-10-30: `ARCHITECTURE.md` numerical conventions "Agreement with TA-Lib", `API.md` §5 "Agreement with TA-Lib", notes on the EMA, DEMA, TEMA, MACD, KAMA, SAR, TRIX pages; `kernels::ema` doc no longer claims 0.8.3 bit parity. Measured against the fixtures: EMA ≤2e-16, MACD ≤2.1e-12 relative (line near zero). `tests/results/test-suite_2026-10-30_18-29-26.txt` PASSED, 609 Rust (nextest) and 2580 Python tests.)*
- [x] B2. Implement A3: scaled test in `kernels/roc.rs`, Rust and Python tests (tiny base → 0, exact 0 → 0, TA-Lib fixtures still pass), remove the ±inf exception from the wiki (ROC, VROC), `API.md`, `ARCHITECTURE.md`; close the parking-lot entry. *(2026-10-30: `is_zero_scaled(earlier, current.abs())` in `rate_of_change_into` and TRIX's inline step; Rust `kernel_roc_tests`, `roc_tests`, `vroc_tests`, Python `test_roc.py`/`test_vroc.py`; ROC/VROC/TRIX reference tests still bit for bit; TRIX proptest against the cascade still bit for bit. `tests/results/test-suite_2026-10-30_18-29-26.txt` PASSED, 609 Rust (nextest) and 2580 Python tests.)*
- [x] B3. Implement A4: clamp in `aroon.rs`, Rust test for period 11 (`aroon_up == 100.0`), proptest bound tightened, Python test, wiki/API note. *(2026-10-30: `.min(100.0)` on up/down, `.clamp(-100.0, 100.0)` on the oscillator; periods 97, 161, ... still round one ulp below 100 (not clamped, within range). `tests/results/test-suite_2026-10-30_18-29-26.txt` PASSED, 609 Rust (nextest) and 2580 Python tests.)*
- [x] B4. Cost refit (`pyta-benchmarks` skill): full `--batch --rust` run; refit SMA, CCI, STDDEV (period sweep) and WMA from the 10 x 1,000 and 100 x 100 rows; constants in `pyta-common/src/costs.rs`; confirm with a second batch run that no planner row is above 1.10x. *(Full `benchmark_2026-10-30_18-34-48.txt` (`--batch --rust`): misses at SMA 10 x 1,000 (1.15x), WMA 100 x 100 (1.32x), STOCH 10 x 100 (1.51x); STDDEV period sweep `7.55 + 0.215 * period` ms. New SMA 1.5, WMA 1.9, STOCH 13.2, STDDEV 5.1 + 0.21/period; CCI's rows all chose right, left. Confirmed `_22-06-38` (sma), `_22-36-57` (wma), `_22-42-36` (stoch), `_22-49-03` (stddev): every small-batch row picks the faster arm; only `6_sma_rsi_ds1_ds2` 1.27x remains (accepted 3,000-point miss, memory).)*
- [x] B5. `./scripts/test-suite.sh` passes. *(`test-suite_2026-10-30_18-29-26.txt`, `_23-08-29.txt`.)*

### Part C: integration project (about 4 h)

- [x] C1. `PyTA-Integration/` skeleton: `pyproject.toml` (Python 3.15, `pyta` from `dist/`, pandas, pytest; extra `bench`: `TA-Lib==0.8.3`), `README.md`, `.gitignore`; root tooling (pytest `testpaths`, ruff, pyright, coverage) does not pick it up.
- [x] C2. `PyTA-Integration/scripts/setup.sh`: builds the release wheel, creates the venv, installs the wheel (never the source tree), runs examples and tests.
- [x] C3. Examples (`examples/`): SMA and RSI on a yFinance-shaped DataFrame; AlphaVantage-shaped CSV and JSON; a batch over several datasets.
- [x] C4. Integration tests (`tests/`): examples run, expected values (SPY reference values copied as data, not read from PyTA's tree), invalid parameters and error messages, a check that `pyta.__file__` is inside the venv's site-packages.
- [x] C5. Check no use of `pyta._native` or crate paths (`grep` test in the suite). *(97093eb; `setup.sh --bench` from a deleted `.venv` and `dist/`: 52 passed, ruff clean, on the wheel with B1-B3.)*

### Part D: TA-Lib comparison (about 3 h)

- [x] D1. `PyTA-Integration/benchmarks/compare_talib.py`: every indicator both libraries have, `timeit` best of ≥5, libraries interleaved, outputs compared (largest difference).
- [x] D2. Single: NumPy arrays and a yFinance-shaped DataFrame at 100, 10,000, 1,000,000 rows.
- [x] D3. Batch: TA-Lib list-comprehension loop against one `pyta.batch.<name>` call, 10 x 1,000, 100 x 100, 100 x 10,000, 1,000 x 1,000.
- [x] D4. Report written to `PyTA-Integration/results/`; both tables in PyTA's `README.md` with machine, governor, date; indicators without a TA-Lib equivalent listed. *(`results/compare_talib_2026-10-30_23-07-35.md`, copied to `docs/benchmarks/talib_comparison_2026-10-30.md`; README "Performance against TA-Lib".)*

### Part E: close (about 1 h)

- [x] E1. Install docs in `PyTA-Integration/README.md` (setup, examples, tests, benchmark); link from PyTA's `README.md`. *(`PyTA-Integration/README.md` benchmark section; README "Development" and `CLAUDE.md` commands link it.)*
- [x] E2. `DEVELOPMENT.md`: tick tasks; retrospective and ✓ once the criteria pass; memory and `pyta-tooling` current. *(Retrospective and ✓; memory updated.)*

### Acceptance criteria for Sprint 12

- [x] The bit-parity policy and the parked numeric calls are decided, implemented and documented. *(B1-B3, 0ef7d12.)*
- [x] The integration project installs and imports PyTA independently (wheel, clean venv). *(`setup.sh --bench` from deleted `.venv` and `dist/`.)*
- [x] All example workflows run successfully. *(`setup.sh`: three examples ran.)*
- [x] Integration tests pass against the installed package. *(52 passed.)*
- [x] The public API works without access to the PyTA source tree. *(`test_install.py`: site-packages, wheel, no source on `sys.path`, no private names.)*
- [x] A package build can be tested from a clean environment. *(`setup.sh` builds the wheel and installs it in a fresh venv.)*
- [x] `README.md` has single and batch `timeit` comparisons with TA-Lib for every indicator both have, reproducible from the integration project. *(README tables, full report in `docs/benchmarks/`.)*

### Verification

- [x] `./scripts/test-suite.sh` after Part B and at close (cite the reports). *(`test-suite_2026-10-30_18-29-26.txt`, `_23-08-29.txt`: PASSED.)*
- [x] `PyTA-Integration/scripts/setup.sh` from a deleted venv and `dist/`. *(52 passed, ruff clean.)*
- [x] Benchmark reports for B4 and D cited.

Out of scope: CI for the integration project (Sprint 13), an AlphaVantage adapter, new indicators, publishing to PyPI (Sprint 14).

## Parking lot

- `bench_boundary.py` single-column rows time only NumPy input; Series, list and dict inputs are not benchmarked. Its `**params` call adds ~0.1 µs that `main`'s did not.
- A CCI batch row (100 × 1,000) read +8.7% in one implementer's A/B but +3.9% in the final one; check with `--batch --rust` if it recurs.

- Multi-column Python layer costs ~12 µs per call on 100 rows (dict of three arrays) against ~3.8 µs for SMA; the rest is per-column conversion and leading-NaN checks (Sprint 17).
- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
- CI had not run when Sprint 9 closed; check it is green after the maintainer's push.
- Chaining from a multi-output frame needs the Series (`pyta.sma(out["macd_signal"], ...)`), since `column=` takes role names only; revisit if users ask.
- Bare output names (A5) collide when two runs of one indicator (say SMA 20 and SMA 50) are joined into one frame; the caller renames. Revisit if users ask for a `name=` option.
- AlphaVantage's nested JSON time series (dates as keys, `1. open` names, numbers as strings) would need a provider adapter; decide whether one belongs in PyTA (Sprint 11, A6).
- CSV and JSON text cost 15-70x an array call at 100 rows (parsing dominates: SMA CSV 99 µs, JSON records 211 µs); a faster parser (or `np.loadtxt`-style bulk conversion) is a Sprint 17 candidate if text input matters.
- CCI on a DataFrame costs ~150 µs per call against ~13 µs for a dict of arrays: pandas column access, not PyTA work (Sprint 17).
- A nested multi-column dict column reads `column 0 expected a 1-D series ...` (the slot number as the name); reword if users meet it.
- Delete the merged agent worktrees and branches (`.claude/worktrees/agent-*`, `worktree-agent-*`) once the sprint is merged.
- `ma=` option (TA-Lib `matype`) for BBANDS and STOCH, reusing the Sprint 11.5 kernels (A5).
- VWAP session or date anchoring; needs a datetime role (A9).
- Further indicators: Stochastic RSI, PPO, Momentum, CMO, Hull MA, Supertrend, Pivot Points, ROCP/ROCR/ROCR100, ADXR, PLUS_DI/MINUS_DI alone (A14).

- The CCI 10 x 10,000 batch cell flips between ~60 and ~95 µs/dataset on `main` too; check whether it is the planner's crossover. CCI's cost constant reads +25% at 1M rows but every batch row chooses right (2026-10-30), so it stays.
- **Performance against TA-Lib (Sprint 12, 2026-10-30):** TA-Lib is faster in most single calls and small batches (`docs/benchmarks/talib_comparison_2026-10-30.md`). At 1M NumPy rows PyTA takes 1.2-5x TA-Lib's time (ATR 7.4 against 1.5 ms, EMA 3.8 against 0.9, OBV 6.6 against 3.5): profile the native call (copy into `Series`, finite/magnitude scan, kernel, output) and compare kernel loops with TA-Lib's. The Python layer costs ~3-10 µs per NumPy call and ~100-180 µs per DataFrame call against TA-Lib's 1-3 and 15-60 µs. Candidate for the next sprint.
- `pyta.sma(x, period=True)` raises `period must be an integer, not bool` while a str gives `..., got str` (`_validation.py`); `API.md` §7 shows only the "got" form. The integration tests pin the current wording.
- Aroon: for periods 97, 161, 167, 193-195, 199, 289 `(100 / period) * period` is 1 ulp below 100 (within range and tolerance); write exactly 100 when the extreme is the current row if users notice.
