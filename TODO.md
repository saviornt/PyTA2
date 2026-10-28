# TODO Scratchpad — PyTA

## Sprint 8: category namespaces

Plan of record: `docs/DEVELOPMENT.md`, "Sprint 8 — Category namespaces". Goal: users call an indicator by category (`pyta.trend.sma`) or by short-hand name (`pyta.sma`), and the batch API mirrors both (`pyta.batch.trend.sma`, `pyta.batch.sma`). Every style reaches the same function object; no indicator code is duplicated or moved into the namespaces.

Where things stand: each indicator is one flat module, `python/pyta/indicators/<name>.py`, holding its single and batch functions. `pyta/__init__.py`, `pyta/indicators/__init__.py` and `pyta/batch.py` only re-export. The Rust crates (`pyta-trend`, `pyta-momentum`) and the user docs (`docs/indicators/<category>/`) are already split by category; the Python package is not. API.md §2 marks "By category" as *Planned*.

**Layout (decided 2026-10-28, option 2):** indicator modules move into category subpackages, `python/pyta/indicators/<category>/<name>.py`, mirroring `pyta-<category>` and `docs/indicators/<category>/`. Each subpackage `__init__.py` re-exports its single-call functions. A thin top-level module `python/pyta/<category>.py` re-exports the subpackage, because `import pyta.trend` needs a real `pyta/trend.py` (an attribute set in `pyta/__init__.py` is not importable). The batch side mirrors this in `python/pyta/batch/<category>.py`.

Import paths this changes: the *modules* `pyta.indicators.sma` / `pyta.indicators.rsi` become `pyta.indicators.trend.sma` / `pyta.indicators.momentum.rsi`, so `from pyta.indicators.sma import sma_batch` stops working. The *functions* `pyta.sma`, `pyta.indicators.sma`, `pyta.batch.sma` (and the RSI equivalents) keep working. In the repo only `batch.py`, `indicators/__init__.py` and `tests/python/test_import.py` import the module paths.

### Part A: start (about 15 min)

- [ ] Confirm the goal and the acceptance criteria below (tracking rule 1).
- [x] Decide the category layout: option 2, category subpackages (above).
- [x] Record the decision, dated, in `.claude/memory.md`.

### Part B: move the modules into category subpackages (about 45 min)

- [ ] `git mv python/pyta/indicators/sma.py python/pyta/indicators/trend/sma.py` and `rsi.py` to `indicators/momentum/rsi.py` (keeps history). Update their imports (absolute, Ruff `TID252`) and module docstrings.
- [ ] `python/pyta/indicators/trend/__init__.py` and `momentum/__init__.py`: docstring naming the category and its planned members; re-export the single-call function; sorted `__all__`.
- [ ] `python/pyta/indicators/__init__.py`: import the category subpackages and re-export every indicator, so `pyta.indicators.sma` and `pyta.indicators.rsi` stay the functions; sorted `__all__` with the categories and the names.
- [ ] Top-level `python/pyta/trend.py` and `python/pyta/momentum.py`: re-export from `pyta.indicators.<category>`, sorted `__all__`.
- [ ] `python/pyta/__init__.py`: import `momentum` and `trend`, add both to the sorted `__all__`; keep `indicators`, `batch`, `rsi`, `sma` as they are.
- [ ] Check in a fresh interpreter: `import pyta.trend` alone, `from pyta.momentum import rsi`, `import pyta.indicators.trend.sma`, and `import pyta` still leaves pandas unloaded.

### Part C: batch namespaces (about 30 min)

- [ ] Turn `python/pyta/batch.py` into a package: `git mv` it to `python/pyta/batch/__init__.py`, importing from the new module paths (`pyta.indicators.trend.sma`). `pyta.batch.sma` and `pyta.batch.rsi` stay.
- [ ] `python/pyta/batch/trend.py` and `python/pyta/batch/momentum.py`: `from pyta.indicators.<category>.<name> import <name>_batch as <name>`, sorted `__all__`.
- [ ] `pyta/batch/__init__.py` imports both categories and lists them in `__all__`.
- [ ] Build a wheel (`uv run maturin build`) and confirm it contains every new file: `pyta/indicators/trend/`, `pyta/indicators/momentum/`, `pyta/trend.py`, `pyta/momentum.py`, `pyta/batch/` (maturin's `python-source` packaging, not only the editable install).

### Part D: tests (about 45 min)

New `tests/python/test_namespaces.py`:
- [ ] Identity: `pyta.trend.sma is pyta.indicators.trend.sma is pyta.indicators.sma is pyta.sma`, the same for `rsi`, and `pyta.batch.<category>.<name> is pyta.batch.<name>`.
- [ ] Same results through both styles on the `ohlcv` fixture, single and batch (required by the sprint, even though identity implies it).
- [ ] Guard the convention: every name in `pyta.indicators.__all__` (minus the category names) lives in exactly one `pyta/indicators/<category>/<name>.py`; the top-level and batch category namespaces list exactly the subpackage's names; and each indicator has its user doc at `docs/indicators/<category>/<name>.md`.
- [ ] Fresh-interpreter imports (subprocess, like `test_import.py`): `import pyta.trend`, `from pyta.batch.momentum import rsi`, `import pyta.indicators.momentum.rsi`.
- [ ] Stability: a list of the documented function paths (`pyta.sma`, `pyta.rsi`, `pyta.indicators.sma`, `pyta.batch.sma`, the category forms, ...) all resolve, so adding a category cannot remove one.
- [ ] `tests/python/test_import.py`: import `sma_batch`/`rsi_batch` from the new module paths; the expected top-level `__all__` gains `momentum` and `trend`; `pyta.indicators.__all__` and `pyta.batch.__all__` gain their categories.

### Part E: convention and docs (about 45 min)

- [ ] Convention for a new category, written in `ARCHITECTURE.md` §5: the subpackage `pyta/indicators/<category>/` (one module per indicator, `__init__.py` re-exports), the thin `pyta/<category>.py` and `pyta/batch/<category>.py`, each added to its parent's sorted `__all__`; the Rust crate `pyta-<category>` and `docs/indicators/<category>/` use the same name. Adding one never changes an existing import.
- [ ] `docs/API.md` §2: "By category" becomes Available, with single and batch examples, and the paragraph describes the subpackages; §9 (batch) mentions `pyta.batch.<category>.<name>`.
- [ ] `docs/ARCHITECTURE.md`: package tree (subpackages, top-level category modules, `batch/` package) and "Where should a change go?".
- [ ] `.claude/CLAUDE.md`: the "Per-indicator modules" rule and the "Adding an indicator touches" path (`python/pyta/indicators/<category>/<name>.py`, `pyta/batch/`).
- [ ] `README.md`: one usage line in the category style.
- [ ] `docs/indicators/trend/sma.md` and `momentum/rsi.md`: Usage shows both styles.
- [ ] `.claude/skills/add-indicator/SKILL.md`: the module path `indicators/<category>/<name>.py`, the export steps (category `__init__.py`, `pyta/indicators/__init__.py`, `pyta/<category>.py`, `pyta/batch/<category>.py`, `pyta/batch/__init__.py`), and a new category per the convention; drop "If Sprint 8's category namespaces exist".
- [ ] `docs/DEVELOPMENT.md`: tick Sprint 8 tasks only as each is verified; mark API.md updated.

### Acceptance criteria for Sprint 8

- [ ] `pyta.trend.sma is pyta.sma` (and the same for every indicator, single and batch), with identical results through both styles.
- [ ] `import pyta`, `import pyta.trend`, `import pyta.indicators.trend.sma` and `from pyta.batch.momentum import rsi` each work in a fresh interpreter, and `import pyta` still does not import pandas.
- [ ] Adding a category does not change existing imports: guarded by the stability and convention tests.
- [ ] `./scripts/test-suite.sh` passes (Pyright strict and stubtest included), and CI is green.

### Verification

- [ ] `./scripts/test-suite.sh` after Part D and at the end (reports in `tests/results/`).
- [ ] The wheel check in Part C.
- [ ] `git log --follow python/pyta/indicators/trend/sma.py` still shows the history from before the move.
- [ ] Manual: `uv run python -c "import pyta; print(pyta.trend.sma([1.0, 2.0, 3.0], 2), pyta.batch.momentum.rsi([[1.0, 2.0, 3.0]], 1))"`.
- No benchmark: the namespaces are re-exports and touch no call path. If import time is a concern, compare `uv run python -X importtime -c "import pyta"` before and after.

Out of scope: Sprint 9 (multi-column OHLCV input), new indicators, lazy imports, deprecating `pyta.indicators` or the short-hand names, and namespaces for categories with no indicator yet (volatility, volume, valuation get theirs with their first indicator).

## Parking lot

- `cargo deny` CI job: `docs/DEVELOPMENT.md` Sprint 7.5 still has it unticked. Tick it once a CI run shows the "cargo deny" job green.
- RSI reference tolerance (0.1) comes from StockCharts' rounded image; the unrounded `cs-rsi.xls` would allow a tight check (needs a download).
- TA-Lib differential testing: still open (`.claude/memory.md`).
- `tests/fixtures/ohlcv_daily.csv` is Yahoo data (personal use); revisit before a public release.
