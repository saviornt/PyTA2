# TODO Scratchpad — PyTA

## Sprint 12: independent integration project (planned 2026-10-30)

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 12 — Independent integration project". Goal: validate PyTA as an external consumer sees it (installed wheel, public API only), settle the numeric calls parked at Sprint 11.5's close, and measure PyTA against TA-Lib the way each is used in production, single calls and batches.

Where things stand:
- **Parked numeric calls** (Sprint 11.5 close): fma policy (SAR and TRIX are bit-exact with TA-Lib 0.8.3 only with `mul_add`, KAMA only without; the EMA family differs by ≤4e-16 relative), ROC's ±inf on a tiny non-zero base (Volume ROC inherits it), Aroon's `(100 / period) * period` = 100 + 1 ulp for some periods (`aroon.rs:69`). Every fixture passes at 1e-9 today.
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

- [ ] B1. Implement A2: docs (`ARCHITECTURE.md`, `API.md`, wiki notes for SAR, TRIX, EMA family, KAMA), memory, parking-lot entry removed.
- [ ] B2. Implement A3: scaled test in `kernels/roc.rs`, Rust and Python tests (tiny base → 0, exact 0 → 0, TA-Lib fixtures still pass), remove the ±inf exception from the wiki (ROC, VROC), `API.md`, `ARCHITECTURE.md`; close the parking-lot entry.
- [ ] B3. Implement A4: clamp in `aroon.rs`, Rust test for period 11 (`aroon_up == 100.0`), proptest bound tightened, Python test, wiki/API note.
- [ ] B4. Cost refit (`pyta-benchmarks` skill): full `--batch --rust` run; refit SMA, CCI, STDDEV (period sweep) and WMA from the 10 x 1,000 and 100 x 100 rows; constants in `pyta-common/src/costs.rs`; confirm with a second batch run that no planner row is above 1.10x.
- [ ] B5. `./scripts/test-suite.sh` passes.

### Part C: integration project (about 4 h)

- [ ] C1. `PyTA-Integration/` skeleton: `pyproject.toml` (Python 3.15, `pyta` from `dist/`, pandas, pytest; extra `bench`: `TA-Lib==0.8.3`), `README.md`, `.gitignore`; root tooling (pytest `testpaths`, ruff, pyright, coverage) does not pick it up.
- [ ] C2. `PyTA-Integration/scripts/setup.sh`: builds the release wheel, creates the venv, installs the wheel (never the source tree), runs examples and tests.
- [ ] C3. Examples (`examples/`): SMA and RSI on a yFinance-shaped DataFrame; AlphaVantage-shaped CSV and JSON; a batch over several datasets.
- [ ] C4. Integration tests (`tests/`): examples run, expected values (SPY reference values copied as data, not read from PyTA's tree), invalid parameters and error messages, a check that `pyta.__file__` is inside the venv's site-packages.
- [ ] C5. Check no use of `pyta._native` or crate paths (`grep` test in the suite).

### Part D: TA-Lib comparison (about 3 h)

- [ ] D1. `PyTA-Integration/benchmarks/compare_talib.py`: every indicator both libraries have, `timeit` best of ≥5, libraries interleaved, outputs compared (largest difference).
- [ ] D2. Single: NumPy arrays and a yFinance-shaped DataFrame at 100, 10,000, 1,000,000 rows.
- [ ] D3. Batch: TA-Lib list-comprehension loop against one `pyta.batch.<name>` call, 10 x 1,000, 100 x 100, 100 x 10,000, 1,000 x 1,000.
- [ ] D4. Report written to `PyTA-Integration/results/`; both tables in PyTA's `README.md` with machine, governor, date; indicators without a TA-Lib equivalent listed.

### Part E: close (about 1 h)

- [ ] E1. Install docs in `PyTA-Integration/README.md` (setup, examples, tests, benchmark); link from PyTA's `README.md`.
- [ ] E2. `DEVELOPMENT.md`: tick tasks; retrospective and ✓ once the criteria pass; memory and `pyta-tooling` current.

### Acceptance criteria for Sprint 12

- [ ] The bit-parity policy and the parked numeric calls are decided, implemented and documented.
- [ ] The integration project installs and imports PyTA independently (wheel, clean venv).
- [ ] All example workflows run successfully.
- [ ] Integration tests pass against the installed package.
- [ ] The public API works without access to the PyTA source tree.
- [ ] A package build can be tested from a clean environment.
- [ ] `README.md` has single and batch `timeit` comparisons with TA-Lib for every indicator both have, reproducible from the integration project.

### Verification

- [ ] `./scripts/test-suite.sh` after Part B and at close (cite the reports).
- [ ] `PyTA-Integration/scripts/setup.sh` from a deleted venv and `dist/`.
- [ ] Benchmark reports for B4 and D cited.

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
- TA-Lib 0.8.3 updates EMAs as `fma(beta, prev, k*x)`; `kernels::ema_step` uses `(x - prev)*k + prev`, so EMA/DEMA/TEMA differ from TA-Lib by ~1e-15 (inside 1e-9). Check whether the `kernels::ema` doc claim "bit for bit with INT_EMA" still holds for 0.8.3, and decide whether to switch to `mul_add` (would change EMA/MACD bits). *Evidence against switching (KAMA, 9d06811): KAMA written with plain multiply-adds matches the 0.8.3 wheel bit for bit although the source says `fma`, so the wheel likely does not fuse; and `f64::mul_add` without `target-feature=+fma` is a libm call (KAMA 7.39 vs 3.39 ms per 1e6 rows).* *But SAR (e33cbb8) is bit-exact only with `mul_add`: `ta_SAR.c` is built with `TA_FMA_MULTIVERSION`, so the wheel fuses per function. Plain SAR is within one ulp (2.1e-16) and 16% faster than fused; kept plain. Decide one policy at QA: within-1e-9 everywhere (current) or fused where TA-Lib multiversions.*
- Aroon (22f0ab5) writes `(100/period)*period`, which is 100 + 1 ulp for some periods (11, 22, 39, ...), as TA-Lib does; kept for bit parity. Clamp to 100 like RSI if users notice.
- ROC (e9502ac) copies TA-Lib's exact `earlier != 0.0` guard, so a tiny nonzero base gives ±inf (documented exception to "outputs are finite"). Decide: keep parity, or a scaled zero test / NaN. Volume ROC inherits it.

- Cost constants left at close (2026-10-30, `benchmark_2026-10-30_10-57-29.txt`): SMA reads +29% and CCI +25% at 1M rows, but their planner rows are fine; refit only with batch-row evidence (memory, "Cost constants near the crossover"). STDDEV's two terms need a period sweep (only the per-row term was refit).
- Planner: `many_wma_x100` at 100 rows picks parallel, 1.16x the sequential arm (~3 µs; WMA's small-batch cost ~2.1 ns/row against 2.7). The CCI 10 x 10,000 batch cell flips between ~60 and ~95 µs/dataset on `main` too; check whether it is the planner's crossover.
