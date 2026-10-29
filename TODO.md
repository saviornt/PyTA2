# TODO Scratchpad — PyTA

## Sprint 10: multi-output indicators ✓ (closed 2026-10-28)

All parts and acceptance criteria verified; open follow-ups are in the parking lot. The plan below is the record until the next sprint is planned.

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 10 — Multi-output indicators". Goal: an indicator can return several named series (MACD: `macd`, signal, histogram) in the caller's container. The user-facing design so far is `docs/API.md` §11 (marked *planned*); `.claude/skills/add-indicator/references/extending-contracts.md` has the extension rules for multi-output **and** extra parameters.

Where things stand:
- **Rust:** `IndicatorOutput` wraps one `Vec<f64>` (`pyta-core/src/output.rs`). `IndicatorRequest { kind, input: IndicatorInput, period: usize }` (`pyta-engine/src/requests.rs`); every kernel takes one `period`. `dispatch` and `estimated_cost_ns` are exhaustive over `IndicatorKind` (`Cci`, `Rsi`, `Sma`).
- **Bindings:** `single.rs`/`batch.rs` return one array per dataset; `compute_columns`/`compute_columns_batch` likewise.
- **Python:** `Prepared.restore(out, name)` / `PreparedColumns.restore` rebuild one series; every runner names it `f"{label}_{period}"`, always lower case whatever the input's casing. `_api.run*` trim and re-pad one result. `validate_period` is the only parameter validator.
- **Not in any sprint task, but MACD needs it:** parameters other than `period` (fast, slow, signal). The extension rules exist in `extending-contracts.md` ("Extra parameters"), so this sprint builds them.
- **EMA does not exist.** MACD is built from EMAs; EMA is first on Sprint 15's list.
- `benches/results/` has no `--single --python` / `--batch --python` baseline in this checkout (Sprint 9's retrospective asked for one), so the performance gate is a same-session A/B against `main` (memory "A/B beats old baselines").

### Part A: start and decide (about 30 min)

- [x] Confirm the goal and the acceptance criteria below (tracking rule 1), and add Sprint 10 tasks to `DEVELOPMENT.md` for the per-indicator parameters (A1), EMA (A2) and the renamed outputs (A5). *(2026-10-28: confirmed by the user merging the plan into `main` (e2dbe89); the tasks are in `DEVELOPMENT.md`. Spec answers the same day: EMA allows `period=1` (identity), default 30 as TA-Lib; MACD's minimum input is `slow + signal - 1`, so every output has a value.)*
- [x] **A1. Parameters are per indicator.** *(2026-10-28, user's decision.)* Each indicator owns its parameter set and keyword names: SMA, RSI, CCI and EMA take `period=`; MACD takes `fast=`, `slow=`, `signal=`. Rust: `IndicatorRequest.period` becomes a `Params` enum with **one variant per indicator** (`Sma { period }`, `Macd { fast, slow, signal }`, ...), each destructured by its own dispatch arm, so `IndicatorKind` and its parameters cannot disagree (the kind may then be derived from the variant). Python: each indicator module declares its own validated parameters (Pydantic), reusing shared range validators; shared across a batch, like `period` today.
- [x] **A2. EMA is a full indicator.** *(2026-10-28, user's decision.)* `pyta.ema` / `pyta.trend.ema` / `pyta.batch.ema`, built with the `add-indicator` skill; TA-Lib seeding (SMA of the first `period` values, `k = 2 / (period + 1)`); its kernel also serves MACD.
- [x] **A3. MACD spec (TA-Lib `TA_MACD`).** *(2026-10-28, user's decision: swap like TA-Lib; TA-Lib's ranges, so `fast`/`slow` ≥ 2, `signal` ≥ 1; `fast == slow` computes all 0. Document the swap in the docstring and wiki page.)* `macd(data, fast=12, slow=26, signal=9, *, column=None)`, Trend category, default column `close`; both EMAs start at index `slow - 1` (TA-Lib seeds the fast EMA with the SMA of the `fast` values ending there); signal = EMA(`signal`) of the MACD line; hist = macd − signal. **Open: `fast >= slow`.** No industry standard: TA-Lib (`ta_MACD.c`) and pandas-ta swap silently when `slow < fast`, and `fast == slow` gives all 0; Tulip rejects `long < short`; bukosabino `ta` computes the negated line. TA-Lib ranges: fast and slow 2..100000, signal 1..100000. *Recommend:* swap like TA-Lib (same result the caller meant; PyTA is a TA-Lib replacement) and keep TA-Lib's ranges. **Also open:** allow `fast`/`slow` of 1 as CCI allows `period=1`?
- [x] **A4. Warm-up per output.** *(2026-10-28, agreed.)* `macd` valid from row `slow - 1`; `macd_signal` and `macd_hist` from `slow + signal - 2`. Where TA-Lib has a value, ours is identical; TA-Lib blanks `macd` until the signal exists.
- [x] **A5. Output names are the indicator's name, without parameters.** *(2026-10-28, user's decision.)* `sma`, `rsi`, `cci`, `ema`; multi-output `macd`, `macd_signal`, `macd_hist`, and later indicators follow the pattern (`<indicator>` for the main output, `<indicator>_<part>` for the rest). This **changes SMA, RSI and CCI** (`sma_14` → `sma`) in every container, batch included; their tests change accordingly.
- [x] **A6. Output casing follows the input's OHLCV columns.** *(2026-10-28, user's decision; every indicator, past and future.)* Lower-case columns → all lower (`sma`, `macd_signal`). Upper-case → all upper (`SMA`, `MACD_SIGNAL`). Title case (`Close`, `Adj Close`, as yfinance) → abbreviations upper, full words title (`SMA`, `MACD_Signal`; a future unabbreviated indicator such as `mayer_multiple` → `Mayer_Multiple`). Each indicator declares which name parts are abbreviations. *Assumed until told otherwise:* the separator is always `_`; mixed casing and unnamed input give lower case; `hist` (a shortened word, not an acronym) counts as a word, so title case gives `MACD_Hist`. *Orchestrator's call (to confirm):* a word in capitals is title-compatible (`SPY Close`, `MACD_Signal`), so title-case outputs chain as title case.
- [x] **A7. One-series input returns a tuple of outputs.** *(2026-10-28, agreed.)* List, tuple, 1-D array or pandas Series → a tuple in documented order, each output in the input's own single-output form (`macd, signal, hist = pyta.macd(close)`); a JSON array of numbers → a JSON object keyed by output name.
- [x] **A8. Reference data.** *(2026-10-28, user's decision: TA-Lib-generated fixtures in a throwaway env, exact comparison.)* No published worked example was verified (StockCharts was unreachable), and libraries seed EMAs differently (Tulip and `ta` from the first value, pandas-ta's own MACD likely at `fast - 1`), so TA-Lib's output is the only de facto standard. PyPI `TA-Lib` 0.8.3 has manylinux wheels up to cp315 with the C library bundled. *Recommend:* generate EMA and MACD reference values with TA-Lib in a throwaway env from `tests/fixtures/ohlcv_daily.csv` (as yfinance was used), commit them as fixtures citing the version, and compare exactly (1e-9); TA-Lib stays out of the dependencies. This partly settles memory's open "TA-Lib differential testing" item.
- [x] Record the decisions, dated, in `.claude/memory.md`, and update the Sprint 10 tasks in `DEVELOPMENT.md`. *(2026-10-28: memory "Sprint 10 design" and "TA-Lib differential testing"; the skills' `<name>_<period>` wording is updated in Part H with the code.)*

### Part B: Rust output and parameter contracts (about 1.5 h)

- [x] `pyta-core`: `IndicatorOutput` carries one or more equal-length series in the indicator's documented output order (names live in Python, like slots); `new(values)` and `values()`/`into_values()` unchanged for single output; `with_outputs(Vec<Vec<f64>>)`, `outputs()`, `into_outputs()`, `output_count()`. Unit tests, including unequal lengths rejected. *(`with_outputs` rejects zero or unequal outputs with `LengthMismatch`; `output_tests.rs`; `tests/results/test-suite_2026-10-28_21-53-03.txt`.)*
- [x] `pyta-engine`: per-indicator `Params` per A1; `IndicatorRequest` carries it; each dispatch arm destructures its own variant. Constructors for SMA/RSI/CCI requests stay as simple as today; their kernel tests unchanged. *(`Params::{Cci, Ema, Macd, Rsi, Sma}`, kind derived by `Params::kind()`; `IndicatorRequest::new(series, Params::Rsi { period: 14 })`; `sma_tests.rs`, `rsi_tests.rs`, `cci_tests.rs` unchanged.)*
- [x] `estimated_cost_ns` takes the request's params (MACD's and EMA's cost per row is independent of their periods; confirm with the quick benchmark). *(Quick run `benches/results/benchmark_2026-10-28_21-51-12.txt`, governor performance: kernels at 1M rows EMA-20 2.888 ms, MACD 12/26/9 12.007 ms, RSI-14 2.405 ms → `EMA_NS_PER_ELEMENT` 3.6, `MACD_NS_PER_ELEMENT` 15.0; period-independent by construction (one pass per EMA).)*
- [x] Planner and both execution paths unchanged; test `execute_parallel` = `execute_sequential` on multi-output requests mixed with single-output ones. *(`sequential_tests.rs`: MACD mixed with single-output requests; `assert_same` compares every output.)*

### Part C: EMA, end to end (about 2 h, via the `add-indicator` skill)

EMA is single-output and uses `period=`, so it needs only Part B's `Params`; doing it first proves the parameter change on the simplest indicator before MACD.

- [x] Spec per the skill (TA-Lib `TA_EMA`, warm-up `period - 1`, cited reference per A8), agreed with the user. *(2026-10-28: TA-Lib `TA_EMA`, default 30, `period=1` allowed and an exact copy (user's answer); reference TA-Lib 0.8.3 fixtures.)*
- [x] `pyta-trend/src/ema.rs`: TA-Lib seeding, with a start offset so MACD can seed the fast EMA at `slow - 1`; unit and property tests. *(`ema_tests.rs`, EMA proptests; MACD now uses its own fused pass, so `ema_into`'s start offset is used only by `ema`.)*
- [x] Engine kind, dispatch arm, cost constant; bindings `pyta-python/src/ema.rs`; `_native.pyi`; `indicators/trend/ema.py` and every export (category, `indicators/__init__.py`, `pyta/trend.py`, `pyta/batch/`, `test_namespaces.py`). *(`EMA_NS_PER_ELEMENT` 3.6 from the quick run `benches/results/benchmark_2026-10-28_21-51-12.txt`; confirm with a full `--single --rust --indicator ema`; `tests/results/test-suite_2026-10-28_23-47-18.txt`.)*
- [x] Reference test (Rust and Python, `tests/fixtures/` + `tests/reference/`), edge cases, `docs/indicators/trend/ema.md`, README catalog. *(`ema_10_talib.csv`, `ema_30_talib.csv` at 1e-9 in `reference_tests.rs` and `test_ema_reference.py`; `docs/indicators/trend/ema.md`; README.)*

### Part C2: MACD kernel (about 1 h)

- [x] Spec per the skill, settling A3 and A8; agreed with the user. *(2026-10-28: A3 as recorded; minimum input `slow + signal - 1`, user's answer.)*
- [x] `pyta-trend/src/macd.rs`: three outputs per A3/A4; `fast >= slow` per A3; too-short input is `InsufficientData`; unit tests; proptests (hist = macd − signal exactly where both exist; warm-up lengths; constant input gives 0). *(`macd_tests.rs`, MACD proptests in `property_tests.rs`, TA-Lib references 12/26/9 and 5/35/5 at 1e-9 in `reference_tests.rs`; new `PytaError::InvalidParameter` for fast/slow < 2, signal < 1; reviewed, fixes in fac7b8a.)*
- [x] Engine `IndicatorKind::Macd`, dispatch arm, cost constant in `pyta-common/src/costs.rs` from a quick benchmark scaled against RSI (confirm with a full `--single --rust --indicator macd`). *(Provisional 15.0 ns/row from the quick run above; confirm with a full `--single --rust --indicator macd`.)*

### Part D: bindings (about 45 min)

- [x] `single.rs`/`batch.rs`: a multi-output result comes back as a list of arrays per dataset; the single-output entry points and their return types are unchanged. Shared helpers, no per-indicator copy. GIL released as today. *(Shared `output_to_python`: one array for one output, a list for several; `sma`/`rsi`/`cci` unchanged from Python, 281 Python tests pass untouched.)*
- [x] `pyta-python/src/macd.rs` (`macd`, `macd_batch` taking the three periods) and registration in `lib.rs`.
- [x] `_native.pyi` updated; stubtest passes. *(`tests/results/test-suite_2026-10-28_21-53-03.txt`, PASSED.)*

### Part E: Python multi-output and parameters (about 2.5 h)

- [x] Per-indicator parameters (A1): each indicator module declares its parameters; shared range validators in `_validation.py` (`period`, and MACD's `fast`, `slow`, `signal` per A3), each with a one-sentence error like `validate_period`'s; the runners take the validated parameter set instead of one `period`. *(`validate_period`, `validate_fast`, `validate_slow`, `validate_signal`; plain in-range ints skip Pydantic (same value, ~1 µs saved per CCI call).)*
- [x] Output names: one helper building the names (A5) and applying the casing rule (A6) from the input column(s) the call used, for every indicator; each indicator declares its output names and which parts are abbreviations. SMA, RSI and CCI switch to `sma`, `rsi`, `cci`. *(`_outputs.py`: `OutputNames` per indicator, casing memo keyed on the names' strings; all-capitals words count as title so `MACD_Signal` chains as title (orchestrator's call, to confirm).)*
- [x] `Restore` grows to take several outputs (`restore(names, results)`, two sequences in output order): DataFrame → one column per output; dict / JSON records / JSON object → one key per output (dict values keep the input column's container type); one-series inputs per A7. Single-output restore results unchanged. *(`test_macd.py`, `test_multi_output.py`; single-output results unchanged but for the name.)*
- [x] `_api`: single and batch runners accept the output names (or a count) and the params; leading-NaN trim and re-pad apply to each output; batch keeps failures in place and logs as today. Multi-column runners get the same, so a future multi-column, multi-output indicator (Stochastic) needs no more plumbing; cover that with a unit test that passes a fake native function. *(`test_multi_output.py`: a fake multi-column, three-output native function.)*
- [x] `indicators/trend/macd.py` (`OUTPUTS` beside the function, documented order), exports in `indicators/trend/__init__.py`, `indicators/__init__.py`, `pyta/trend.py`, `pyta/batch/trend.py`, `pyta/batch/__init__.py`, `test_namespaces.py`.

### Part F: tests (about 2 h)

- [x] MACD in every supported container: names, order, container type per output, index kept for pandas, `null` for NaN in JSON. *(`test_macd.py`.)*
- [x] Casing (A6), for SMA, RSI, CCI, EMA and MACD: lower, upper, title (yfinance-style, with `Adj Close`) and mixed input columns; unnamed input; JSON records and dicts. *(`test_casing.py`, including chaining from `MACD_Signal` and the `True`/`1` name collision.)*
- [x] Renamed outputs (A5): every existing test that asserted `sma_<n>`, `rsi_<n>`, `cci_<n>` updated, and nothing else in those tests changed (list each change in the review). *(Listed in the Python implementer's report: `test_batch.py`, `test_cci.py`, `test_columns.py`, `test_inputs.py`, `test_multi_column.py` (one test calls `run_columns` directly, so its call changed too), `test_namespaces.py`, `test_cci_reference.py`, smoke; title-case frames now expect `SMA`/`RSI`/`CCI`; reviewed.)*
- [x] Warm-up per output (A4), and leading-NaN input (chained) shifts every output the same way. *(`test_macd.py`; reviewer checked 5 leading NaN shift warm-ups 25/33/33 → 30/38/38.)*
- [x] Parameter errors: each validator's range, `fast >= slow`, wrong types, a series too short; messages name the parameter. *(`fast > slow` is swapped, not an error (A3): `macd(x, 26, 12) == macd(x, 12, 26)` exactly.)*
- [x] Reference test from a cited published example in `tests/fixtures/` (+ `tests/reference/`), read by Rust and Python, per A8; hand-checked exact cases. *(TA-Lib-generated per A8: `macd_12_26_9_talib.csv`, `macd_5_35_5_talib.csv` at 1e-9, read by both readers; `macd_tests.rs` hand cases.)*
- [x] Batch with good and bad datasets: failures in place, others complete; shared parameters raise for the whole call.
- [x] Hypothesis: hist = macd − signal; output lengths equal input length; results invariant to container type. *(`test_properties.py`; Rust proptests incl. the fused kernel bit for bit against one pass per EMA.)*
- [x] Single-output indicators otherwise unaffected: SMA, RSI, CCI values, containers and errors unchanged. *(Their kernel tests unchanged; Python tests changed only output names; `tests/results/test-suite_2026-10-28_23-47-18.txt`.)*

### Part G: benchmarks (about 45 min, via the `pyta-benchmarks` skill)

- [x] Before Part B: `./scripts/benchmark.sh --single --python` and `--batch --python` on `main` in a scratch worktree, kept as the baseline for this sprint (Sprint 9 asked for a current one). *(2026-10-28, governor `performance`, `main` at 3721679 in `.claude/worktrees/bench-base`: `benches/results/base-3721679_benchmark_2026-10-28_21-39-13.txt` (single) and `_21-40-08` (batch), after a discarded quick warm-up run.)*
- [x] MACD workloads in the Criterion and Python benchmarks; check the kernel (one pass per EMA, no extra allocations beyond the three outputs) and record the numbers. *(MACD in `single_call.rs`, `workloads.rs`, `bench_boundary.py`, `bench_batch.py`. The five-pass kernel was fused into one pass, bit-identical: kernel at 1M rows 11.85 → 5.65 ms (2.1-2.3x at every size, same-session A/B, `benches/results/base-398e5d2_benchmark_2026-10-28_22-17-44.txt`, `_22-18-38` vs `benchmark_2026-10-28_22-18-11.txt`, `_22-19-05`); `MACD_NS_PER_ELEMENT` 15.0 → 6.7, provisional until a full `--single --rust --indicator macd`.)*
- [x] A/B against `main`, alternating, twice each: SMA, RSI and CCI single and batch calls within ~5%. *(A/B 2026-10-28, governor `performance`, `main` 3721679 in `.claude/worktrees/bench-base` vs 38edd45, alternating, two full runs each after a quick warm-up: single `benches/results/base-3721679_benchmark_2026-10-28_23-32-29.txt`, `_23-34-59` vs `benchmark_2026-10-28_23-33-26.txt`, `_23-35-56`; batch `base-3721679_..._23-37-29`, `_23-42-25` vs `_23-39-20`, `_23-44-13`. Public single call, mean of 2, base → branch: SMA 100 4.675 → 4.046 µs (0.87), 10k 27.70 → 27.48 (0.99); RSI 100 4.704 → 4.089 (0.87), 10k 33.37 → 31.38 (0.94); CCI 100 14.37 → 13.60 (0.95), 10k 107.7 → 106.3 (0.99); at 1M points the native call dominates (SMA 1.05, RSI 1.00, CCI 0.97). Batch per dataset: every SMA/RSI/CCI row within ±5% but SMA 100 × 1,000 (4.54 → 4.80 µs, +5.8%, at the noise edge) and CCI 10 × 10,000 (0.65, faster). A first round on 7da3ba4 failed the gate (+8-16% at 100 rows); 38edd45 fixed it in Python. The branch's `bench_boundary.py` passes parameters as `**params`, which costs it ~0.1 µs per call against `main`'s, so the comparison is conservative.)*

### Part H: docs and close (about 1 h)

- [x] `docs/API.md` §11: Available, with the final names, casing rule, one-series shape and per-indicator parameters; every `<indicator>_<period>` name in §5, §9, §10 and the examples changed to the bare name; §13 catalog. Same sweep in `README.md` and `docs/indicators/` (SMA, RSI, CCI pages).
- [x] `docs/ARCHITECTURE.md`: the output and parameter contracts end to end; how an indicator declares its outputs and parameters.
- [x] `docs/indicators/trend/macd.md` (what, why, usage, outputs and their warm-ups, differences from Appel and from TA-Lib's common warm-up); README catalog. *(Also `ema.md`.)*
- [x] `extending-contracts.md` and the `add-indicator` skill: multi-output and extra parameters are built; describe how to declare them. *(Also `spec-template.md` and `pyta-testing`'s fixture naming.)*
- [x] `.claude/CLAUDE.md` architecture lines (params, outputs) and `.claude/memory.md`.
- [x] `docs/DEVELOPMENT.md`: tick Sprint 10 tasks only as each is verified; retrospective and ✓ once the criteria pass.

### Acceptance criteria for Sprint 10

- [x] MACD returns three named outputs in every supported container. *(`test_macd.py` containers; manual check below.)*
- [x] EMA is available as a full indicator (single, batch, namespaces, docs). *(`test_ema.py`, `test_namespaces.py`, `test_batch.py`, `docs/indicators/trend/ema.md`.)*
- [x] Output names are the bare indicator names and their casing follows the input's columns (A5, A6), for every indicator. *(`test_casing.py` over all five indicators.)*
- [x] Single-output indicators are otherwise unchanged (values, containers, errors), and their single-call cost stays within ~5% of `main` in a same-session A/B. *(Gate in Part G above.)*
- [x] EMA and MACD match their references (A8) within the stated tolerance, and the TA-Lib convention cases exactly. *(Four TA-Lib fixtures at 1e-9, Rust and Python; swap, `fast == slow` and `signal = 1` cases.)*
- [x] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included). *(`tests/results/test-suite_2026-10-28_23-47-18.txt`: PASSED, Rust 145, Python 470, branch coverage 99%, Pyright strict and stubtest pass.)*

### Verification

- [x] `./scripts/test-suite.sh` after Part D and at the end (cite the report in `tests/results/`). *(After Part D: `tests/results/test-suite_2026-10-28_21-53-03.txt`; at the end: `tests/results/test-suite_2026-10-28_23-47-18.txt`.)*
- [x] `./scripts/benchmark.sh --single --python` and `--batch --python`, A/B against `main` (Part G). *(Part G.)*
- [x] Manual: `uv run python -c "import pandas as pd, pyta; df = pd.read_csv('tests/fixtures/ohlcv_daily.csv', comment='#'); print(pyta.macd(df).tail())"`. *(2026-10-28: a `macd, macd_signal, macd_hist` frame; last row 2.693378, 2.748233, −0.054854.)*

Out of scope: other multi-output indicators (Bollinger Bands, Stochastic, Aroon: Sprint 15/16), CSV input (Sprint 11), mixed-indicator batches, per-dataset parameters in a batch, selecting a non-role column by name (`column="macd_signal"` stays an error; pass the Series).

## Parking lot

- Confirm two calls made during Sprint 10: all-capitals words count as title case (so `MACD_Signal` chains as title), and plain in-range ints skip Pydantic in the parameter validators.
- Confirm the provisional cost constants with full runs: `--single --rust --indicator ema` (3.6) and `--indicator macd` (6.7).
- `bench_boundary.py` single-column rows time only NumPy input; Series, list and dict inputs are not benchmarked. Its `**params` call adds ~0.1 µs that `main`'s did not.
- A CCI batch row (100 × 1,000) read +8.7% in one implementer's A/B but +3.9% in the final one; check with `--batch --rust` if it recurs.

- Multi-column Python layer costs ~12 µs per call on 100 rows (dict of three arrays) against ~3.8 µs for SMA; the rest is per-column conversion and leading-NaN checks (Sprint 17).
- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
- CI had not run when Sprint 9 closed; check it is green after the maintainer's push.
- Chaining from a multi-output frame needs the Series (`pyta.sma(out["macd_signal"], ...)`), since `column=` takes role names only; revisit if users ask.
- Bare output names (A5) collide when two runs of one indicator (say SMA 20 and SMA 50) are joined into one frame; the caller renames. Revisit if users ask for a `name=` option.
