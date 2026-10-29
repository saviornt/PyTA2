# TODO Scratchpad — PyTA

## Sprint 9: multi-column input (OHLCV)

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 9 — Multi-column input (OHLCV)". Goal: a user passes full OHLCV data in any supported container and PyTA finds the columns each indicator needs, by role, ignoring the rest. The binding decisions are in `.claude/memory.md` ("Multi-column indicators", "Default column"); the user-facing design is already written in `docs/API.md` §10 (marked *planned*); `.claude/skills/add-indicator/references/extending-contracts.md` has the extension rules.

Where things stand:
- **Rust:** `IndicatorRequest { kind, input: Series, period }` (`pyta-engine/src/requests.rs`); every kernel is `fn(&Series, usize)`. `pyta-core` has an `Ohlcv` struct (five fixed `Series`, `LengthMismatch` check) that nothing uses yet.
- **Bindings:** `single::compute` and `batch.rs` take one 1-D array per dataset.
- **Python:** `_validation.py` has the six roles and their aliases (`_ROLE_ALIASES`, matched via `_squash`) and picks one column (`_pick`); `normalize` returns one `Prepared` series; `_api.run`/`run_batch` trim leading NaN from that one series.
- **No multi-column indicator exists**, so the sprint needs one to prove the work end to end (see Part A).

### Part A: start and decide (about 30 min)

- [x] Confirm the goal and the acceptance criteria below (tracking rule 1). *(2026-10-28: confirmed with one change from the user: a high below its low on any row is rejected, in Python, not Rust; so `InvalidOhlcv` is removed as planned. CCI spec agreed, with `period=1` allowed.)*
- [x] Choose the indicator that validates the design. *(2026-10-28: **CCI**: high, low, close; one output; `period` only; Momentum, already a category; first on Sprint 15's priority list. Not ATR, which needs the Volatility category from Sprint 16, nor Williams %R.)*
- [x] Choose the Rust input shape. *(2026-10-28: a generic `Columns` type in `pyta-core`, equal-length validated `Series` in the indicator's slot order, and `IndicatorRequest.input` as an enum of `Series` or `Columns`, so fundamentals need no new type. The unused `Ohlcv` struct is removed in Part B.)*
- [x] Record both decisions, dated, in `.claude/memory.md`, and reword the first Sprint 9 task in `DEVELOPMENT.md`.

### Part B: Rust contract (about 1 h)

- [x] `pyta-core`: `Columns`, validated per column like `Series`, rejecting unequal lengths (`LengthMismatch`) and zero columns; unit tests. Remove `Ohlcv` and any error variant only it used (check `PytaError::InvalidOhlcv` and its Python mapping and tests). *(`input_tests.rs`, `error_tests.rs`; `PytaError::InvalidOhlcv` had no Python mapping or test beyond its message; `ColumnCount` added for a request of the wrong shape.)*
- [x] `pyta-engine`: `IndicatorRequest` carries single or multi-column input; constructors for both; a kernel receives only the slices it needs. Existing `new(kind, Series, period)` callers and SMA/RSI tests unchanged. *(`IndicatorInput::{Series, Columns}`, `with_columns`; `series()`/`columns::<N>()`; SMA/RSI callers and tests unchanged.)*
- [x] `dispatch` and `estimated_cost_ns` stay exhaustive; cost scales with rows (not rows × columns unless measured otherwise). *(CCI: per row plus per row × period, since its kernel is O(rows · period).)*
- [x] Planner and both execution paths work unchanged for multi-column requests; test `execute_parallel` = `execute_sequential` on them. *(`parallel_matches_sequential_on_multi_column_requests`, `multi_column_requests_run_beside_single_column_ones`.)*

### Part C: role registry (about 45 min)

- [x] Turn `_ROLE_ALIASES` into a registry where a role is one entry (name plus aliases), so a fundamental role (`eps`, `book_value`, ...) is a one-line addition with no other change. Do not add fundamental roles yet. *(`register_role(name, *aliases)` in `_validation.py`.)*
- [x] A slot type: a slot name plus the roles it accepts, in preference order (CCI's `close` slot accepts `close` or `adj_close`). *(`Slot(name, roles)`.)*
- [x] Tests guarding the registry: no alias belongs to two roles; every alias is already squashed; a test-only role can be registered and found by name. *(`test_multi_column.py`, "role registry" tests.)*

### Part D: Python multi-column normalization (about 2 h)

- [x] A multi-column `normalize` that returns one aligned float64 array per slot plus the restore function, for every named container: DataFrame, dict of columns, JSON records, JSON object of arrays. *(`_columns.normalize_columns`.)*
- [x] Automatic matching by role; columns no slot needs are ignored, including non-numeric ones (a `date` or `symbol` column must not raise).
- [x] `columns=[...]` override in any order: each name goes to the slot for its role. Unrecognized name, two names for one slot, an empty slot, or a name not present raises `ValueError` naming the indicator's slots and the available columns.
- [x] Unnamed inputs (2-D NumPy array `(rows, columns)`, tuple of arrays) take the indicator's documented column order; the column count must match. 1-D inputs (list, 1-D array, Series) raise `TypeError` saying the indicator needs several columns.
- [x] `column=` on a multi-column indicator and `columns=` on a single-column one raise `ValueError`.
- [x] A missing role raises `ValueError` naming the required columns (with accepted roles) and the available columns.
- [x] Leading NaN: trim the longest leading-NaN run across the slots, so chained outputs still work; NaN after that in any slot is rejected, with the column named. Same magnitude check as single-column input. *(Values are checked by Rust; Python names the column and row only after a native `ValueError`, see memory "Multi-column value checks are lazy".)*
- [x] `_api`: single and batch runners for multi-column indicators, sharing the existing helpers; the batch keeps failures in place and logs them as today. Result container and naming unchanged (`<label>_<period>`). *(`run_columns`, `run_columns_batch`.)*

### Part E: bindings (about 45 min)

- [x] `pyta-python`: single and batch entry points that take a list of arrays per dataset, copy-and-validate each column (`Series::from_slice`), and release the GIL as `single.rs` does. *(`compute_columns`, `compute_columns_batch`; single and batch share `series_from`/`run_datasets`.)*
- [x] `_native.pyi` updated; stubtest passes. *(`tests/results/test-suite_2026-10-28_16-46-19.txt`.)*

### Part F: the validating indicator (about 2 h, via the `add-indicator` skill)

- [x] Spec per the skill (formula, TA-Lib convention, warm-up, reference source), agreed with the user. *(Agreed 2026-10-28; TA-Lib `TA_CCI`, default 14, `period=1` allowed.)*
- [x] Kernel in its category crate, dispatch arm, cost constant (quick benchmark scaled against RSI). *(Provisional constants from a quick run, `benches/results/benchmark_2026-10-28_16-43-02.txt` plus native timings at periods 1-100; confirm with a full `--single --rust --indicator cci`.)*
- [x] Bindings, `indicators/<category>/<name>.py`, category and batch exports, short-hand name.
- [x] Reference test from a cited published example in `tests/fixtures/`, read by Rust and Python; edge cases; property tests. *(StockCharts MSFT 20-day, `tests/fixtures/cci_20_stockcharts.csv`, tolerance 0.25 from the published rounding; Rust `cci_tests.rs`, `property_tests.rs`; Python `test_cci.py`, `test_cci_reference.py`.)*
- [x] `docs/indicators/<category>/<name>.md` listing its required columns and their order for unnamed input; README catalog.

### Part G: tests (about 1.5 h)

- [x] Every container for the validating indicator, with extra columns (including non-numeric ones) and with exactly the needed columns.
- [x] Overrides: any order gives the same result; each error case of Part D.
- [x] Error messages name the required and the available columns.
- [x] Unnamed 2-D array and tuple in documented order; wrong column count.
- [x] Leading-NaN alignment across columns, and NaN or too-large values inside a column.
- [x] Batch with a mix of good and bad datasets: failures in place, others complete.
- [x] Hypothesis: any permutation of `columns=` gives the same result.
- [x] Single-column indicators unaffected: SMA and RSI tests pass untouched. *(`test_sma.py`, `test_rsi.py`, `test_columns.py`, `test_batch.py`, `sma_tests.rs`, `rsi_tests.rs` unchanged against `main`; `tests/results/test-suite_2026-10-28_16-46-19.txt`.)*

### Part H: docs and close (about 45 min)

- [x] `docs/API.md` §10: Available, with CCI in the examples in place of `pyta.atr`.
- [x] `docs/ARCHITECTURE.md`: the multi-column contract end to end, the role registry and how to add a role, and the division of validation for columns.
- [x] `extending-contracts.md` and the `add-indicator` skill: multi-column is now built; describe how to declare an indicator's slots.
- [x] `.claude/CLAUDE.md`: the data-flow line mentions multi-column input.
- [x] `docs/DEVELOPMENT.md`: tick Sprint 9 tasks only as each is verified.

### Acceptance criteria for Sprint 9

- [x] A full OHLCV DataFrame (the `ohlcv` fixture, with its date column) passed to the validating indicator works without naming columns, and the same holds for every named container. *(`test_full_dataframe_with_its_date_column_needs_no_names` and the dict, Series-dict, JSON records/columns tests in `test_multi_column.py`.)*
- [x] A call missing a needed column raises `ValueError` naming the required and the available columns. *(`test_a_missing_column_names_the_required_and_the_available_columns`.)*
- [x] SMA and RSI are unaffected: their tests pass untouched, and single-call cost stays within ~5% of the latest baseline. *(A/B in one session, alternating `main` (fc9f15e, scratch worktree) and this branch, twice each, release builds, governor powersave. Single call, public `pyta.<name>`, mean of 2: SMA 100 pts 4.448 → 4.328 µs (−2.7%), RSI 100 pts 4.576 → 4.336 µs (−5.2%), SMA 10k 26.81 → 26.90 µs (+0.3%), RSI 10k 32.48 → 32.38 µs (−0.3%); at 1M points both arms vary by ±7% between rounds. Batch per dataset: every SMA/RSI row within ±5% (largest: SMA 1,000 × 100 batch 3.04 → 3.15 µs, +3.8%). Branch reports: `benches/results/benchmark_2026-10-28_16-48-12.txt`, `_16-49-48`, `_16-51-58`, `_16-55-10` in this worktree; the `main` reports were in the removed scratch worktree.)*
- [ ] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included), and CI is green after the push. *(Suite PASSED: `tests/results/test-suite_2026-10-28_16-46-19.txt`. Left unticked: CI runs only after the maintainer pushes.)*

### Verification

- [x] `./scripts/test-suite.sh` after Part E and at the end (cite the report in `tests/results/`). *(At the end: `tests/results/test-suite_2026-10-28_16-46-19.txt`, PASSED. After Part E only its steps were run one by one: cargo test/clippy, pytest, Ruff, Pyright, stubtest.)*
- [x] `./scripts/benchmark.sh --single --python` and `--batch --python` against the latest baseline in `benches/results/`. *(See the SMA/RSI criterion above; no `--single --python` baseline existed in `benches/results/`, so `main` was benchmarked alongside, per memory "A/B beats old baselines".)*
- [x] Manual: `uv run python -c "import pandas as pd, pyta; df = pd.read_csv('tests/fixtures/ohlcv_daily.csv', comment='#'); print(pyta.cci(df, period=20).tail())"`. *(2026-10-28: prints a `cci_20` DataFrame; last five 169.22, 164.87, 92.61, 77.92, −3.99.)*

Out of scope: multi-output indicators (Sprint 10), CSV input (Sprint 11), parameters other than `period`, the fundamental roles themselves (only the room for them), and indicators beyond the one that validates the design.

## Parking lot

- Multi-column Python layer costs ~12 µs per call on 100 rows (dict of three arrays) against ~3.8 µs for SMA; the rest is per-column conversion and leading-NaN checks.
- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
