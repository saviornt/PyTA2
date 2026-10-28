# TODO Scratchpad — PyTA

## Sprint 9: multi-column input (OHLCV)

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 9 — Multi-column input (OHLCV)". Goal: a user passes full OHLCV data in any supported container and PyTA finds the columns each indicator needs, by role, ignoring the rest. The binding decisions are in `.claude/memory.md` ("Multi-column indicators", "Default column"); the user-facing design is already written in `docs/API.md` §10 (marked *planned*); `.claude/skills/add-indicator/references/extending-contracts.md` has the extension rules.

Where things stand:
- **Rust:** `IndicatorRequest { kind, input: Series, period }` (`pyta-engine/src/requests.rs`); every kernel is `fn(&Series, usize)`. `pyta-core` has an `Ohlcv` struct (five fixed `Series`, `LengthMismatch` check) that nothing uses yet.
- **Bindings:** `single::compute` and `batch.rs` take one 1-D array per dataset.
- **Python:** `_validation.py` has the six roles and their aliases (`_ROLE_ALIASES`, matched via `_squash`) and picks one column (`_pick`); `normalize` returns one `Prepared` series; `_api.run`/`run_batch` trim leading NaN from that one series.
- **No multi-column indicator exists**, so the sprint needs one to prove the work end to end (see Part A).

### Part A: start and decide (about 30 min)

- [ ] Confirm the goal and the acceptance criteria below (tracking rule 1).
- [x] Choose the indicator that validates the design. *(2026-10-28: **CCI**: high, low, close; one output; `period` only; Momentum, already a category; first on Sprint 15's priority list. Not ATR, which needs the Volatility category from Sprint 16, nor Williams %R.)*
- [x] Choose the Rust input shape. *(2026-10-28: a generic `Columns` type in `pyta-core`, equal-length validated `Series` in the indicator's slot order, and `IndicatorRequest.input` as an enum of `Series` or `Columns`, so fundamentals need no new type. The unused `Ohlcv` struct is removed in Part B.)*
- [x] Record both decisions, dated, in `.claude/memory.md`, and reword the first Sprint 9 task in `DEVELOPMENT.md`.

### Part B: Rust contract (about 1 h)

- [ ] `pyta-core`: `Columns`, validated per column like `Series`, rejecting unequal lengths (`LengthMismatch`) and zero columns; unit tests. Remove `Ohlcv` and any error variant only it used (check `PytaError::InvalidOhlcv` and its Python mapping and tests).
- [ ] `pyta-engine`: `IndicatorRequest` carries single or multi-column input; constructors for both; a kernel receives only the slices it needs. Existing `new(kind, Series, period)` callers and SMA/RSI tests unchanged.
- [ ] `dispatch` and `estimated_cost_ns` stay exhaustive; cost scales with rows (not rows × columns unless measured otherwise).
- [ ] Planner and both execution paths work unchanged for multi-column requests; test `execute_parallel` = `execute_sequential` on them.

### Part C: role registry (about 45 min)

- [ ] Turn `_ROLE_ALIASES` into a registry where a role is one entry (name plus aliases), so a fundamental role (`eps`, `book_value`, ...) is a one-line addition with no other change. Do not add fundamental roles yet.
- [ ] A slot type: a slot name plus the roles it accepts, in preference order (CCI's `close` slot accepts `close` or `adj_close`).
- [ ] Tests guarding the registry: no alias belongs to two roles; every alias is already squashed; a test-only role can be registered and found by name.

### Part D: Python multi-column normalization (about 2 h)

- [ ] A multi-column `normalize` that returns one aligned float64 array per slot plus the restore function, for every named container: DataFrame, dict of columns, JSON records, JSON object of arrays.
- [ ] Automatic matching by role; columns no slot needs are ignored, including non-numeric ones (a `date` or `symbol` column must not raise).
- [ ] `columns=[...]` override in any order: each name goes to the slot for its role. Unrecognized name, two names for one slot, an empty slot, or a name not present raises `ValueError` naming the indicator's slots and the available columns.
- [ ] Unnamed inputs (2-D NumPy array `(rows, columns)`, tuple of arrays) take the indicator's documented column order; the column count must match. 1-D inputs (list, 1-D array, Series) raise `TypeError` saying the indicator needs several columns.
- [ ] `column=` on a multi-column indicator and `columns=` on a single-column one raise `ValueError`.
- [ ] A missing role raises `ValueError` naming the required columns (with accepted roles) and the available columns.
- [ ] Leading NaN: trim the longest leading-NaN run across the slots, so chained outputs still work; NaN after that in any slot is rejected, with the column named. Same magnitude check as single-column input.
- [ ] `_api`: single and batch runners for multi-column indicators, sharing the existing helpers; the batch keeps failures in place and logs them as today. Result container and naming unchanged (`<label>_<period>`).

### Part E: bindings (about 45 min)

- [ ] `pyta-python`: single and batch entry points that take a list of arrays per dataset, copy-and-validate each column (`Series::from_slice`), and release the GIL as `single.rs` does.
- [ ] `_native.pyi` updated; stubtest passes.

### Part F: the validating indicator (about 2 h, via the `add-indicator` skill)

- [ ] Spec per the skill (formula, TA-Lib convention, warm-up, reference source), agreed with the user.
- [ ] Kernel in its category crate, dispatch arm, cost constant (quick benchmark scaled against RSI).
- [ ] Bindings, `indicators/<category>/<name>.py`, category and batch exports, short-hand name.
- [ ] Reference test from a cited published example in `tests/fixtures/`, read by Rust and Python; edge cases; property tests.
- [ ] `docs/indicators/<category>/<name>.md` listing its required columns and their order for unnamed input; README catalog.

### Part G: tests (about 1.5 h)

- [ ] Every container for the validating indicator, with extra columns (including non-numeric ones) and with exactly the needed columns.
- [ ] Overrides: any order gives the same result; each error case of Part D.
- [ ] Error messages name the required and the available columns.
- [ ] Unnamed 2-D array and tuple in documented order; wrong column count.
- [ ] Leading-NaN alignment across columns, and NaN or too-large values inside a column.
- [ ] Batch with a mix of good and bad datasets: failures in place, others complete.
- [ ] Hypothesis: any permutation of `columns=` gives the same result.
- [ ] Single-column indicators unaffected: SMA and RSI tests pass untouched.

### Part H: docs and close (about 45 min)

- [ ] `docs/API.md` §10: Available, with CCI in the examples in place of `pyta.atr`.
- [ ] `docs/ARCHITECTURE.md`: the multi-column contract end to end, the role registry and how to add a role, and the division of validation for columns.
- [ ] `extending-contracts.md` and the `add-indicator` skill: multi-column is now built; describe how to declare an indicator's slots.
- [ ] `.claude/CLAUDE.md`: the data-flow line mentions multi-column input.
- [ ] `docs/DEVELOPMENT.md`: tick Sprint 9 tasks only as each is verified.

### Acceptance criteria for Sprint 9

- [ ] A full OHLCV DataFrame (the `ohlcv` fixture, with its date column) passed to the validating indicator works without naming columns, and the same holds for every named container.
- [ ] A call missing a needed column raises `ValueError` naming the required and the available columns.
- [ ] SMA and RSI are unaffected: their tests pass untouched, and single-call cost stays within ~5% of the latest baseline.
- [ ] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included), and CI is green after the push.

### Verification

- [ ] `./scripts/test-suite.sh` after Part E and at the end (cite the report in `tests/results/`).
- [ ] `./scripts/benchmark.sh --single --python` and `--batch --python` against the latest baseline in `benches/results/`.
- [ ] Manual: `uv run python -c "import pandas as pd, pyta; df = pd.read_csv('tests/fixtures/ohlcv_daily.csv', comment='#'); print(pyta.cci(df, period=20).tail())"`.

Out of scope: multi-output indicators (Sprint 10), CSV input (Sprint 11), parameters other than `period`, the fundamental roles themselves (only the room for them), and indicators beyond the one that validates the design.

## Parking lot

- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
