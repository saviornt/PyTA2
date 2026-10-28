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

## Multi-column input (ATR, Stochastic, CCI, OBV, VWAP): Sprint 9

The decisions in `.claude/memory.md` ("Multi-column indicators", "Default column") are binding:

- Roles (`OPEN`, `HIGH`, `LOW`, `CLOSE`, `ADJ_CLOSE`, `VOLUME` in `_validation.py`) are found by name automatically; columns the indicator does not need are ignored.
- The override is `columns=[...]` in any order; each name is assigned to the indicator's slot for its role, and a slot may accept several roles (`close` or `adj_close`). Unrecognized names, duplicate roles and missing slots raise. `column=` is single-column only, `columns=` multi-column only.
- Unnamed 2-D arrays and tuples use the indicator's documented column order.
- A missing role raises `ValueError` naming the required and the available columns.
- Keep the role registry open-ended for fundamentals (`eps`, `book_value`, ...).
- Rust side: build on `pyta-core`'s `Ohlcv` (`pyta-core/src/input.rs`, with `PytaError::InvalidOhlcv`) or a named-columns input; the kernel takes only the slices it needs.

Follow the Sprint 9 task list in `docs/DEVELOPMENT.md` and tick what the extension completes.

## Multi-output (MACD, Bollinger Bands, Stochastic %K/%D, Aroon): Sprint 10

From the Sprint 10 plan in `docs/DEVELOPMENT.md` and `docs/API.md` section 11:

- `IndicatorOutput` (or a sibling type) carries several named series, all the same length as the input, each with its own warm-up.
- Results come back in the caller's container: extra columns for DataFrames, extra keys for dicts and JSON objects. A NumPy or list input needs a documented shape (for example a dict of arrays, or a 2-D array in documented order); decide it in the spec.
- Output names follow the pattern `macd`, `macd_signal`, `macd_hist`, and match the casing of the input's columns.
- Batch returns one multi-output result per dataset, failures still in place.
