# Extending the engine contracts

Read this when the spec's shape check fails: the indicator needs more than one input column, a parameter other than `period`, or more than one output. The extension is designed in the spec and approved with it; then it is built before the indicator itself, so the indicator is the extension's first user.

Today's contract, end to end:

- Rust: `IndicatorRequest { kind, input: Series, period: usize }` (`pyta-engine/src/requests.rs`) → `dispatch()` → kernel `fn(&Series, usize) -> PytaResult<IndicatorOutput>`; `IndicatorOutput` wraps one `Vec<f64>` (`pyta-core/src/output.rs`).
- Bindings: `single::compute` and `batch::compute_batch` take one array and one `period` (`pyta-python/src/single.rs`, `batch.rs`).
- Python: `_api.run` / `_api.run_batch` validate one `period` (`_validation.py`, Pydantic), pick one column, and restore one result named `<label>_<period>`.

## Rules for any extension

- **Generic, never indicator-specific.** Sprint 16's acceptance criterion: "The engine does not accumulate category-specific special cases." Design for the class of indicators (every multi-output indicator), not for this one.
- **Existing indicators keep working unchanged**: same Python signatures, same output names, same errors. Their tests must pass untouched.
- **No performance regression.** Rerun `./scripts/benchmark.sh --single --python` and `--batch --python` before and after; single-call cost must stay within the ~5% run-to-run noise.
- **Docs in the same change.** `docs/ARCHITECTURE.md` (the contract), `docs/API.md` (the planned sections 10 and 11 become real), and the matching tasks in `docs/DEVELOPMENT.md` ticked. Record the design decision in `.claude/memory.md`.
- **Keep the division of validation.** Python validates containers, columns and parameter types and ranges; Rust rejects empty and non-finite input and impossible parameters.
- **Keep the exhaustive matches.** A new `IndicatorKind` must still fail to compile without a dispatch arm and a cost.

## Extra parameters (Bollinger's `k`, MACD's three periods, Stochastic's smoothing)

No sprint covers this yet, so the spec must propose it.

- Give `IndicatorRequest` a parameter set that each indicator interprets, rather than more positional fields. For example a typed `Params` enum with one variant per parameter shape (`Period(usize)`, `PeriodMultiplier { period, k }`, `Fast/Slow/Signal`), which the dispatch arm destructures; a mismatched variant is a bug, so make it unrepresentable where possible.
- Python: each new parameter gets a Pydantic validator next to `_PERIOD` in `_validation.py`, with a range and a one-sentence error like the existing ones. Keyword names stay consistent across indicators (`period`, `fast_period`, `slow_period`, `signal_period`, `k`).
- Output names include the parameters that distinguish results (`bbands_20_2`), decided in the spec.
- Batch: parameters stay shared across the batch, like `period` today.

## Multi-column input (ATR, Stochastic, OBV, VWAP, ...): built in Sprint 9

Multi-column input exists (CCI was its first user), so a new multi-column indicator needs no contract work: declare its slots and copy CCI. The decisions in `.claude/memory.md` ("Multi-column indicators", "Default column") still bind.

- **Rust.** The kernel takes one `&Series` per input, in slot order: `pub fn atr(high: &Series, low: &Series, close: &Series, period: usize)`. It checks the lengths match (`LengthMismatch`) but not relations between columns (high below low); Python does that. The dispatch arm destructures the input: `let [high, low, close] = input.columns()?;` (`IndicatorInput::columns::<N>()`; the wrong count is a `ColumnCount` error). Requests are built with `IndicatorRequest::with_columns(kind, Columns::new(vec![...])?, period)`. The cost constant is per row, not per row and column.
- **Bindings.** `<name>` calls `single::compute_columns(py, columns, period, kind)` with `columns: Vec<PyReadonlyArray1<f64>>`; `<name>_batch` calls `batch::compute_columns_batch`. Stubs take `list[NDArray]` and `list[list[NDArray]]` (see `cci` in `_native.pyi`).
- **Slots.** In `indicators/<category>/<name>.py`, `SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))`: one `Slot(name, roles)` per input, in the native order (which is also the documented order for unnamed input), each slot's roles in preference order. The functions take `columns: Sequence[str] | None = None` and `column: None = None` (which raises), and call `_api.run_columns(_native.<name>, "<name>", data, period, columns, SLOTS, column)` and `run_columns_batch(...)`.
- **A new role** (for example `volume` exists; a fundamental such as `eps` does not) is one `register_role("eps", "earnings per share", ...)` line in `_validation.py`, beside the OHLCV ones. Nothing else changes.
- **A rule between columns on every row** (like high not below low) is an entry in `ORDERED_ROLES` in `_columns.py`, checked for any indicator that has both roles.
- **Tests and docs.** The reference fixture names its input columns by role (`label,high,low,close,expected`); `reference.columns` (Rust, in file order) and `reference.columns` (Python, a dict by name) read them. `tests/python/test_batch.py` feeds one series per dataset, so a multi-column indicator's batch tests go in `test_<name>.py`; add it to `MULTI_COLUMN` in `test_namespaces.py`. The wiki page gets a "Required columns" table (slot, accepted roles, order for unnamed input), as `docs/indicators/momentum/cci.md` has.

## Multi-output (MACD, Bollinger Bands, Stochastic %K/%D, Aroon): Sprint 10

From the Sprint 10 plan in `docs/DEVELOPMENT.md` and `docs/API.md` section 11:

- `IndicatorOutput` (or a sibling type) carries several named series, all the same length as the input, each with its own warm-up.
- Results come back in the caller's container: extra columns for DataFrames, extra keys for dicts and JSON objects. A NumPy or list input needs a documented shape (for example a dict of arrays, or a 2-D array in documented order); decide it in the spec.
- Output names follow the pattern `macd`, `macd_signal`, `macd_hist`, and match the casing of the input's columns.
- Batch returns one multi-output result per dataset, failures still in place.
