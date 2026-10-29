# TODO Scratchpad — PyTA

## Sprint 11: data containers, CSV input and round-trip conformance ☐

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 11 — Data containers: CSV input and round-trip conformance". Goal: CSV in and out (as AlphaVantage returns it); every container imports and exports correctly for every indicator shape; an `output=` option converts the result to another container.

Where things stand:
- **Normalization** is in `_validation.py` (one series: `normalize`, `_from_json`, ...) and `_columns.py` (multi-column: `normalize_columns`). Each returns a `Prepared`/`PreparedColumns` carrying a `Restore` closure that rebuilds the input's container; the `_api` runners call it. There is no shared export layer: each container's restore is written next to its parser.
- **`str`/`bytes`/`bytearray` input is always parsed as JSON**, so CSV needs a way to tell the two apart (A2).
- **No multi-column, multi-output indicator exists** (Stochastic is Sprint 11.5); `tests/python/test_multi_output.py` already drives the runners with a fake native function of that shape.
- **AlphaVantage's own JSON is not supported today**, although `API.md` §12 says "JSON available": its time series is nested (`{"Meta Data": ..., "Time Series (Daily)": {"2024-01-02": {"1. open": "187.15", ...}}}`), keyed by date, with numbers as strings and names like `1. open` that match no role. Its CSV (`timestamp,open,high,low,close,volume`) does fit. Both come **newest first**. See A6.
- Pandas index: today a dict/JSON result never carries the input's index (a dict input has none); only pandas results keep it.

### Part A: start and decide (about 30 min)

- [x] Confirm the goal and the acceptance criteria below (tracking rule 1). *(2026-10-29, user.)*
- [x] **A1. `output=` design.** *(2026-10-29, user: as recommended.)* Adopt the recommendation in `DEVELOPMENT.md` as written (targets `list`, `tuple`, `numpy`, `pandas`, `dict`, `json`, `json_bytes`, `csv`, `csv_bytes`; one fixed shape per target; index carried to named targets, dropped for unnamed ones; pandas imported only when asked; shared in a batch). *Recommend:* yes, plus two details it leaves open: (a) a `"json"` object of arrays and a `"dict"` carry the index as a field/key placed **first**, named after the index or `index`, and a pandas `DatetimeIndex` (or `date`/`datetime` values) becomes ISO 8601 strings in JSON and CSV (`2024-01-02`, or `2024-01-02T09:30:00` with a time); (b) `output=` equal to the input's own container form gives that target's fixed shape, which may differ from the default (`output="dict"` always has NumPy values, even for a dict of lists).
- [x] **A2. Telling CSV from JSON.** *(2026-10-29, user: as recommended.)* *Recommend:* text whose first non-whitespace character is `[` or `{` is JSON; anything else is CSV. CSV **requires a header row** (AlphaVantage always sends one; a headerless file of numbers is ambiguous with a one-column file). Rejected alternatives: try JSON then fall back to CSV (a scalar such as `"5"` parses as JSON and errors confusingly; costs a failed parse on every CSV call); a separate `pyta.from_csv()` (breaks "any container in, same container out").
- [x] **A3. CSV conventions.** *(2026-10-29, user: as recommended.)* *Recommend:* stdlib `csv` (no pandas, no new dependency); delimiter `,` only (no sniffing); `str` → `str`, `bytes`/`bytearray` → `bytes` (UTF-8, a BOM is skipped), as for JSON. Column selection and aliases exactly as for a dict. Empty field → `NaN` (a gap); `NaN`/`nan` text also → `NaN` (pandas writes it); any other non-numeric text in a used column → `TypeError` naming the column and row; unused columns (`timestamp`) are never parsed. Output follows the **JSON-records convention**: a header of the output names and one row per input row, the input's other columns not repeated; `NaN` → empty field; numbers written as Python's shortest round-trip `repr`; `\n` line endings. One-column CSV in gives one-column CSV out (it chains). Multi-column indicators take CSV like a dict.
- [x] **A4. Numbers as strings are accepted everywhere.** *(2026-10-29, user's decision, against the recommendation to reject.)* A string holding a number (`"187.15"`, `" 1e3 "`) becomes that float in every container: JSON, lists, tuples, dict values, and pandas `object`/`string` columns (so a DataFrame built from AlphaVantage's JSON works). One parser for strings everywhere, the same as CSV fields: surrounding whitespace ignored; empty or `NaN`/`nan` → a gap; anything else (`"abc"`, bools) → `TypeError` naming the column and row. Numeric dtypes keep today's fast path.
- [x] **A7. Numbered column names.** *(2026-10-29, user's decision.)* A leading number and dot (`1. open`, `5. adjusted close`, AlphaVantage's style) is ignored when matching names, in every container and in `column=`/`columns=`, in the Python layer (`squash`). Only digits then `.` then optional space, before a letter; output casing still reads the name as written. `"1. open"` and `"open"` in one input are ambiguous (the existing duplicate-name error).
- [x] **A5. Multi-column, multi-output shape in the matrix.** *(2026-10-29, user: as recommended.)* *Recommend:* cover it with the fake native function from `test_multi_output.py` (through `run_columns` / `run_columns_batch`, and `output=`); Stochastic adds its real row in Sprint 11.5 via the `add-indicator` skill.
- [x] **A6. AlphaVantage specifics.** *(2026-10-29, user: as recommended.)* *Recommend:* (a) **no reordering**: positions are never reordered (output conventions), so newest-first data must be reversed by the caller; document it in §12 with a one-line example, and do not try to detect it; (b) AlphaVantage's **nested JSON stays unsupported** and §12 is corrected to say so (CSV is the supported AlphaVantage format; flattening its JSON would need a provider-specific adapter, which conflicts with "no provider dependency"; parking lot).
- [x] Record the decisions, dated, in `.claude/memory.md`, and update the Sprint 11 "decide" tasks in `DEVELOPMENT.md`. *(2026-10-29: memory "Sprint 11 design".)*

### Part B: container matrix (about 45 min)

- [ ] Write the matrix in `API.md` §4: rows = input forms (list, tuple, NumPy 1-D / 2-D / masked, pandas Series / DataFrame with each index kind, dict with each value type, JSON array / records / object as `str`/`bytes`/`bytearray`, CSV `str`/`bytes`, tuple of arrays); columns = indicator shape (one column × one output, one column × several outputs, several columns × one output, several × several); each cell supported (result form), raising (which exception), or out of scope.
- [ ] Probe each cell against the current code (a scratch script) and list the gaps found; each gap becomes a box in Part E or a documented limitation.

### Part C: CSV input and output (about 2.5 h)

- [ ] Shared string-to-number parser (A4) used by CSV and every other container, and numbered-name stripping in `squash` (A7); unit tests, including `bool` still rejected and the duplicate `1. open`/`open` error.
- [ ] `_validation.py`: CSV detection (A2) and `_from_csv` for one series: header, column pick, values per A3, restore per A3. Unit tests: header only, one column, missing values, `NaN` text, bad text (error names column and row), mixed-case and title-case headers (casing rule), `\r\n` input, BOM, quoted fields, ragged rows (`ValueError`).
- [ ] `_columns.py`: CSV for multi-column indicators (CCI), sharing the parser; tests incl. high below low naming the row.
- [ ] Batch: a list/mapping of CSV datasets; a bad one in place.
- [ ] A real-shape fixture: `tests/fixtures/ohlcv_daily.csv` re-emitted in AlphaVantage's layout (`timestamp,open,high,low,close,volume`, oldest first after the caller's reverse) as a test input, not a new file if a test can build it.

### Part D: shared export layer and `output=` (about 3 h)

- [ ] `_export.py`: one module that turns `(names, results, index)` into each target per A1; the existing restores stay as the default path (`output=None` unchanged and no slower). No indicator has conversion code of its own.
- [ ] `Prepared` / `PreparedColumns` carry the input's index (pandas only; `None` otherwise) so a named target can use it.
- [ ] `_api.run*`: an `output` argument; an invalid name raises `ValueError` listing the valid ones before any work; `"pandas"` without pandas raises `ModuleNotFoundError` naming the `pandas` extra (`import pyta` still never imports pandas: `test_import.py`).
- [ ] `output=` on every single and batch function (SMA, EMA, MACD, RSI, CCI), `_native.pyi` unaffected, docstrings; the `add-indicator` skill and its templates name `output=`.

### Part E: round-trip conformance (about 3 h)

- [ ] pandas: default, date, datetime and non-unique index; nullable `Float64`/`Int64` with `pd.NA`; int and float columns; extra non-numeric columns; title and upper case names. Output keeps index, its name and order, and the casing rule.
- [ ] dict: list/tuple/array/Series values, mixed in one dict; non-string keys; extra keys; each output keeps its column's type.
- [ ] tuple: a tuple of numbers; a tuple of arrays or lists (documented order); multi-output as a tuple of outputs.
- [ ] JSON (`str`, `bytes`, `bytearray`): array, records, object; `null` gaps; numbers as strings per A4 (and in lists, dicts, pandas `object`/`string` columns); numbered names per A7; same shape and type out, `null` for `NaN`.
- [ ] One parametrized round-trip matrix: container × shape (SMA, CCI, MACD, fake multi-column multi-output per A5), checking type, length, names and casing, index, and values equal to the NumPy call exactly.
- [ ] `output=` matrix: every input container × every target × shape: type, names, casing, index carried or dropped, `null` in JSON, empty CSV field for `NaN`, invalid target, `"pandas"` without pandas (simulated via `sys.modules`).
- [ ] Hypothesis: random valid data gives the same values in every container (CSV included) as the plain NumPy call.
- [ ] Fix every gap from Part B, or document it as a limitation in `API.md`.

### Part F: benchmarks (about 45 min, `pyta-benchmarks` skill)

- [ ] Before Part C: `main` baselines in a scratch worktree, `--single --python` and `--batch --python`.
- [ ] Same-session A/B against `main`, alternating, twice each: existing containers within ~5% (single and batch), `output=None`.
- [ ] Record CSV's per-call cost at 100 and 10,000 rows next to JSON's (information, no gate).

### Part G: docs and close (about 1 h)

- [ ] `API.md`: §4 matrix and limitations, `output=` (new section), §12 Data sources (CSV available, AlphaVantage notes per A6), §9 batch `output=`.
- [ ] `ARCHITECTURE.md`: the export layer and where `output=` is applied; CSV in normalization.
- [ ] README, `docs/indicators/` pages (an `output=` line), `.claude/CLAUDE.md` architecture lines, `.claude/memory.md`.
- [ ] `DEVELOPMENT.md`: tick Sprint 11 tasks as verified; retrospective and ✓ once the criteria pass.

### Acceptance criteria for Sprint 11

- [ ] CSV in produces CSV out, with the same conventions as JSON.
- [ ] Every container in the matrix imports and exports correctly for every indicator shape (round-trip and Hypothesis tests); every unsupported form raises a clear error.
- [ ] `output=` converts any supported input to every target for every indicator, single and batch; `output=None` behaves exactly as before.
- [ ] `API.md` documents the full container matrix and its limitations.
- [ ] No provider dependency is added, and existing containers are no slower than on `main` (same-session A/B).
- [ ] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included).

### Verification

- [ ] `./scripts/test-suite.sh` after Part C, after Part D and at the end (cite the reports).
- [ ] `./scripts/benchmark.sh --single --python` and `--batch --python`, A/B against `main` (Part F).
- [ ] Manual: an AlphaVantage-shaped CSV string through `pyta.macd(text)` and `pyta.sma(text, 20, output="pandas")`.

Out of scope: AlphaVantage's nested JSON (A6), reordering newest-first data, CSV delimiters other than `,`, headerless CSV, new indicators (Sprint 11.5), mixed-indicator batches, per-dataset `output=` in a batch.

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
- AlphaVantage's nested JSON time series (dates as keys, `1. open` names, numbers as strings) would need a provider adapter; decide whether one belongs in PyTA (Sprint 11, A6).
