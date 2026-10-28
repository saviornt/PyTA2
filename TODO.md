# TODO Scratchpad — PyTA

## Sprint 8: category namespaces

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 8 — Category namespaces". Goal: users call an indicator by category (`pyta.trend.sma`) or by short-hand name (`pyta.sma`), and the batch API mirrors both (`pyta.batch.trend.sma`, `pyta.batch.sma`). Every style reaches the same function object; no indicator code is duplicated or moved into the namespaces.

Where things stand: each indicator is one flat module, `python/pyta/indicators/<name>.py`, holding its single and batch functions. `pyta/__init__.py`, `pyta/indicators/__init__.py` and `pyta/batch.py` only re-export. The Rust crates (`pyta-trend`, `pyta-momentum`) and the user docs (`docs/indicators/<category>/`) are already split by category; the Python package is not. API.md §2 marks "By category" as *Planned*.

### Part A: start (about 15 min)

- [ ] Confirm the goal and the acceptance criteria below (tracking rule 1).
- [ ] Decide the category layout. Recommended, **option 1**: keep the flat `pyta/indicators/<name>.py` modules as the only implementation, and add thin re-export modules `pyta/trend.py`, `pyta/momentum.py`, ... (and `pyta/batch/<category>.py`). Least churn, one place per indicator, and the `add-indicator` steps barely change. Option 2 moves the modules into `pyta/indicators/<category>/<name>.py` to mirror the Rust crates and `docs/indicators/`; more churn, and every existing `pyta.indicators.<name>` import path changes.
- [ ] Record the decision, dated, in `.claude/memory.md`.

### Part B: single-call category namespaces (about 30 min; option 1 assumed)

- [ ] `python/pyta/trend.py`: docstring naming the category and its planned members; `from pyta.indicators.sma import sma`; sorted `__all__ = ["sma"]`.
- [ ] `python/pyta/momentum.py`: the same for `rsi`.
- [ ] `python/pyta/__init__.py`: import `momentum` and `trend`, add both to the sorted `__all__`; keep `indicators`, `batch`, `rsi`, `sma` exactly as they are.
- [ ] Check in a fresh interpreter: `import pyta.trend` alone, `from pyta.momentum import rsi`, and `import pyta` still leaves pandas unloaded.

### Part C: batch namespaces (about 30 min)

- [ ] Turn `python/pyta/batch.py` into a package: `git mv` it to `python/pyta/batch/__init__.py`, with absolute imports (Ruff `TID252`). `pyta.batch.sma` and `pyta.batch.rsi` stay.
- [ ] `python/pyta/batch/trend.py` and `python/pyta/batch/momentum.py`: `from pyta.indicators.<name> import <name>_batch as <name>`, sorted `__all__`.
- [ ] `pyta/batch/__init__.py` imports both categories and lists them in `__all__`.
- [ ] Build a wheel (`uv run maturin build`) and confirm it contains `pyta/batch/__init__.py`, `trend.py`, `momentum.py` and the new `pyta/trend.py`, `pyta/momentum.py` (maturin's `python-source` packaging, not only the editable install).

### Part D: tests (about 45 min)

New `tests/python/test_namespaces.py`:
- [ ] Identity: `pyta.trend.sma is pyta.sma is pyta.indicators.sma`, `pyta.momentum.rsi is pyta.rsi`, and the same for `pyta.batch.<category>.<name> is pyta.batch.<name>`.
- [ ] Same results through both styles on the `ohlcv` fixture, single and batch (required by the sprint, even though identity implies it).
- [ ] Guard the convention: every name in `pyta.indicators.__all__` is in exactly one category namespace; the batch category namespaces list exactly the same names as the single ones; and each indicator's category matches its user doc, `docs/indicators/<category>/<name>.md`.
- [ ] Fresh-interpreter imports (subprocess, like `test_import.py`): `import pyta.trend`, `from pyta.batch.momentum import rsi`, `import pyta.momentum as m; m.rsi(...)`.
- [ ] Stability: a list of today's documented import paths (`pyta.sma`, `pyta.rsi`, `pyta.indicators.sma`, `pyta.batch.sma`, ...) all still resolve, so adding a category cannot remove one.
- [ ] `tests/python/test_import.py`: expected top-level `__all__` gains `momentum` and `trend`; `pyta.batch.__all__` gains its categories.

### Part E: convention and docs (about 30 min)

- [ ] Convention for a new category, written in `ARCHITECTURE.md` §5: `pyta/<category>.py` and `pyta/batch/<category>.py` (re-exports only, sorted `__all__`), both added to their parent `__all__`; the Rust crate `pyta-<category>` and `docs/indicators/<category>/` use the same name. Adding one never changes an existing import.
- [ ] `docs/API.md` §2: "By category" becomes Available, with single and batch examples; §9 (batch) mentions `pyta.batch.<category>.<name>`.
- [ ] `docs/ARCHITECTURE.md`: package tree (new modules, `batch/` package) and "Where should a change go?".
- [ ] `README.md`: one usage line in the category style.
- [ ] `docs/indicators/trend/sma.md` and `momentum/rsi.md`: Usage shows both styles.
- [ ] `.claude/skills/add-indicator/SKILL.md`: replace "If Sprint 8's category namespaces exist" with the concrete steps (add to `pyta/<category>.py` and `pyta/batch/<category>.py`; new category per the convention) and the `batch.py` path with `batch/__init__.py`.
- [ ] `docs/DEVELOPMENT.md`: tick Sprint 8 tasks only as each is verified; mark API.md updated.

### Acceptance criteria for Sprint 8

- [ ] `pyta.trend.sma is pyta.sma` (and the same for every indicator, single and batch), with identical results through both styles.
- [ ] `import pyta`, `import pyta.trend` and `from pyta.batch.momentum import rsi` each work in a fresh interpreter, and `import pyta` still does not import pandas.
- [ ] Adding a category does not change existing imports: guarded by the stability and convention tests.
- [ ] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included), and CI is green.

### Verification

- [ ] `./scripts/test-suite.sh` after Part D and at the end (reports in `tests/results/`).
- [ ] The wheel check in Part C.
- [ ] Manual: `uv run python -c "import pyta; print(pyta.trend.sma([1.0, 2.0, 3.0], 2), pyta.batch.momentum.rsi([[1.0, 2.0, 3.0]], 1))"`.
- No benchmark: the namespaces are re-exports and touch no call path. If import time is a concern, compare `uv run python -X importtime -c "import pyta"` before and after.

Out of scope: Sprint 9 (multi-column OHLCV input), new indicators, lazy imports, deprecating `pyta.indicators` or the short-hand names, and namespaces for categories with no indicator yet (volatility, volume, valuation get theirs with their first indicator).

## Parking lot

- `cargo deny` CI job: `docs/DEVELOPMENT.md` Sprint 7.5 still has it unticked. Tick it once a CI run shows the "cargo deny" job green.
- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- TA-Lib differential testing: still open (`.claude/memory.md`).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
