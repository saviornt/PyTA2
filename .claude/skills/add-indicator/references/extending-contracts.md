# Extending the engine contracts

Read this when the spec's shape check fails: the indicator needs more than one input column, a parameter other than `period`, or more than one output. The extension is designed in the spec and approved with it; then it is built before the indicator itself, so the indicator is the extension's first user.

Today's contract, end to end (multi-column input since Sprint 9; extra parameters and multi-output since Sprint 10):

- Rust: `IndicatorRequest { input: IndicatorInput, params: Params }` (`pyta-engine/src/requests.rs`); `Params` has one variant per indicator with its own parameters (`Sma { period }`, `Macd { fast, slow, signal }`), and the kind is derived from it (`params.kind()`). `dispatch()` destructures the variant and calls the kernel, which returns `IndicatorOutput`: one series (`new(values)`) or several in documented order (`with_outputs(vec![...])`) (`pyta-core/src/output.rs`).
- Bindings: `single::compute` / `compute_columns` and `batch::compute_batch` / `compute_columns_batch` take the input and a `Params` (`pyta-python/src/single.rs`, `batch.rs`); `output_to_python` returns one array for one output, a list of arrays for several.
- Python: each indicator module validates its own parameters with the shared validators in `_validation.py` and declares `OUTPUTS` and an `OutputNames`; `_api.run` / `run_batch` / `run_columns` / `run_columns_batch` take `(native, names, data, params, ...)`, call `native(values, *params)`, and restore one bare-named output per entry of `OUTPUTS`, cased like the input's columns (`_outputs.py`), or, with `output=`, convert them through `_export.py` (a new output count or input shape needs no export code: every target handles any number of outputs and the input's pandas index from `Prepared.index`).

## Rules for any extension

- **Generic, never indicator-specific.** Sprint 16's acceptance criterion: "The engine does not accumulate category-specific special cases." Design for the class of indicators (every multi-output indicator), not for this one.
- **Existing indicators keep working unchanged**: same Python signatures, same output names, same errors. Their tests must pass untouched (Sprint 10's renaming to bare names was a user decision, not an exception to this rule).
- **No performance regression.** Rerun `./scripts/benchmark.sh --single --python` and `--batch --python` before and after; single-call cost must stay within the ~5% run-to-run noise.
- **Docs in the same change.** `docs/ARCHITECTURE.md` (the contract), `docs/API.md`, and the matching tasks in `docs/DEVELOPMENT.md` ticked. Record the design decision in `.claude/memory.md`.
- **Keep the division of validation.** Python validates containers, columns and parameter types and ranges; Rust rejects empty and non-finite input and impossible parameters.
- **Keep the exhaustive matches.** A new `Params` variant (and its `IndicatorKind`) must still fail to compile without a dispatch arm, a cost and a `kind()` arm.

## Extra parameters (Bollinger's `k`, Stochastic's smoothing): built in Sprint 10

MACD was the first user. A new indicator with its own parameters needs no contract work:

- **Rust.** Add a `Params` variant with the indicator's parameters as named fields (`Bbands { period, k }`), its `kind()` arm, a dispatch arm that destructures it, and an `estimated_cost_ns` arm that reads only the parameters the cost depends on. The kernel takes the parameters as arguments and checks them first: `InvalidPeriod` for a zero `period`, `InvalidParameter { name, minimum, value }` for any other parameter below its minimum. Requests are built as `IndicatorRequest::new(series, Params::Macd { fast: 12, slow: 26, signal: 9 })`.
- **Bindings.** `<name>(values, <params...>)` builds the `Params` and calls `single::compute` (or `compute_columns`); `<name>_batch` likewise. Stubs list the parameters by name.
- **Python.** Keyword names follow the indicator's usual definition (MACD: `fast`, `slow`, `signal`; not `fast_period`), decided in the spec. Each parameter gets a validator in `_validation.py` beside `validate_period` (same type rules and upper bound, a one-sentence error naming the parameter; `validate_fast`, `validate_slow`, `validate_signal` are the models). The module validates its parameters into a tuple in its native function's order (see `_params` in `indicators/trend/macd.py`) and passes it to the runner. A batch shares the parameters across datasets, so an invalid one raises for the whole call.
- **Output names never include parameters** (`sma`, not `sma_20`): the caller renames when joining two runs.

### Float parameters (Bollinger's `k`, SAR's `acceleration`): ready since Sprint 11.5

- **Rust.** Give the field the type `f64`: `Bbands { period: usize, k: f64 }`. `Params` derives `PartialEq` but not `Eq` or `Hash` for exactly this reason; nothing in the engine, planner or bindings compares or hashes `Params`, so keep it that way (compare requests field by field in tests, or with `==`, which `PartialEq` gives). A cost arm reads only what the cost depends on, so a float multiplier is normally `Params::Bbands { .. }`. The kernel still rejects a non-finite or non-positive float (Python checks first, but a Rust caller may not); `PytaError::InvalidParameter` holds `usize` values, so a float check needs its own `pyta-core` error variant, added with the first indicator that needs it.
- **Bindings.** Take the parameter as `f64` (`k: f64`); PyO3 converts a Python `int` or `float`. Stub it as `float` in `_native.pyi`.
- **Python.** `validate_positive_float(name, value)` returns a finite float above 0 (an int is accepted and converted; a bool raises `TypeError`); `maximum=` adds an inclusive upper bound. Relations between parameters use `validate_ascending(*named, strict=...)` after each value is validated: `validate_ascending(("acceleration", acceleration), ("maximum", maximum), strict=False)` for SAR's `0 < acceleration <= maximum`, `validate_ascending(("short", short), ("medium", medium), ("long", long), strict=True)` for ULTOSC. Integer parameters other than `period` use `validate_int(name, value, minimum)` (the same rules as `validate_period`). Never reorder or clamp what the caller passed (TA-Lib does both; PyTA raises).

### Parameterless indicators (OBV, A/D, VWAP): ready since Sprint 11.5

- **Rust.** A unit variant, `Params::Obv`, with `Self::Obv => IndicatorKind::Obv` in `kind()`, `Params::Obv => obv(close, volume)` in dispatch and `Params::Obv => OBV_NS_PER_ELEMENT` in the cost. The exhaustive matches still force all three.
- **Bindings.** `obv(py, columns)` and `obv_batch(py, datasets)` with no parameter arguments, passing `Params::Obv`.
- **Python.** Pass an empty tuple as the parameters: `run_columns(_native.obv, _NAMES, data, (), columns, SLOTS, column, output)`; the runners call `native(values, *())`, so the native function gets only the input. The public function has no parameter arguments.

## Multi-column input (ATR, Stochastic, OBV, VWAP, ...): built in Sprint 9

Multi-column input exists (CCI was its first user), so a new multi-column indicator needs no contract work: declare its slots and copy CCI. The decisions in `.claude/memory.md` ("Multi-column indicators", "Default column") still bind.

- **Rust.** The kernel takes one `&Series` per input, in slot order: `pub fn atr(high: &Series, low: &Series, close: &Series, period: usize)`. It checks the lengths match (`LengthMismatch`) but not relations between columns (high below low); Python does that. The dispatch arm destructures the input: `let [high, low, close] = input.columns()?;` (`IndicatorInput::columns::<N>()`; the wrong count is a `ColumnCount` error). Requests are built with `IndicatorRequest::with_columns(Columns::new(vec![...])?, Params::Atr { period })`. The cost constant is per row, not per row and column.
- **Bindings.** `<name>` calls `single::compute_columns(py, columns, Params::Atr { period })` with `columns: Vec<PyReadonlyArray1<f64>>`; `<name>_batch` calls `batch::compute_columns_batch`. Stubs take `list[NDArray]` and `list[list[NDArray]]` (see `cci` in `_native.pyi`).
- **Slots.** In `indicators/<category>/<name>.py`, `SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))`: one `Slot(name, roles)` per input, in the native order (which is also the documented order for unnamed input), each slot's roles in preference order. The functions take `columns: Sequence[str] | None = None`, `column: None = None` (which raises) and `output: Output | None = None`, and call `_api.run_columns(_native.<name>, _NAMES, data, params, columns, SLOTS, column, output)` and `run_columns_batch(...)` with the same arguments.
- **A new role** (for example `volume` exists; a fundamental such as `eps` does not) is one `register_role("eps", "earnings per share", ...)` line in `_validation.py`, beside the OHLCV ones. Nothing else changes.
- **A rule between columns on every row** (like high not below low) is an entry in `ORDERED_ROLES` in `_columns.py`, checked for any indicator that has both roles. **A role that must not be negative** (volume; zero is valid) is an entry in `NONNEGATIVE_ROLES`, checked for any multi-column indicator with that role. Both run in `_api._trim_columns` on every call, so an indicator without those roles pays only a membership test; keep it that way (a shared check function called on every call cost ~0.2 µs there).
- **Tests and docs.** The reference fixture names its input columns by role (`label,high,low,close,expected`); `reference.columns` (Rust, in file order) and `reference.columns` (Python, a dict by name) read them. `tests/python/test_batch.py` feeds one series per dataset, so a multi-column indicator's batch tests go in `test_<name>.py`; add it to `MULTI_COLUMN` in `test_namespaces.py`. The wiki page gets a "Required columns" table (slot, accepted roles, order for unnamed input), as `docs/indicators/momentum/cci.md` has.

## Multi-output (Bollinger Bands, Stochastic %K/%D, Aroon): built in Sprint 10

MACD was the first user and Stochastic the first with several columns (its tests and `test_output.py`'s `fake` shape, now `pyta.stoch`); `tests/python/test_multi_output.py` still runs a fake native function through `_api.run_columns` to test the plumbing without Rust. Sprint 11.5 added BBANDS, Keltner, Donchian, ADX, Aroon and Ichimoku the same way.

- **Rust.** The kernel returns `IndicatorOutput::with_outputs(vec![main, ...])`, all as long as the input, in documented order, each with its own `NaN` warm-up. Allocate only the outputs. The cost constant is per row, not per output.
- **Python.** Declare `OUTPUTS` beside the function, lower case, in documented order: `<indicator>` for the main output and `<indicator>_<part>` for the rest (`("macd", "macd_signal", "macd_hist")`), and `_NAMES = OutputNames("<name>", OUTPUTS, abbreviations=(...))` listing the parts that are abbreviations (written upper case in title-case output: `MACD_Signal`). Nothing else: the runners restore every output and apply the casing rule.
- **Containers** (decided, `docs/API.md` §11): a DataFrame gains one column per output; a dict, JSON records and a JSON object one key per output; a one-series input (list, tuple, 1-D array, Series) returns a tuple of outputs in documented order, each in the input's own form; a JSON array of numbers returns a JSON object keyed by output name.
- **Tests and docs.** The reference fixture has one `expected_<output>` column per output (`expected_macd,expected_macd_signal,expected_macd_hist`) and its parameters as comment lines (`# fast: 12`); both readers handle it. The wiki page lists the outputs and each one's warm-up, as `docs/indicators/trend/macd.md` does. Batch tests of a multi-output indicator go in `test_<name>.py`.
