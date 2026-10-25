# PyTA Architecture and Repository Reference

**Status:** Initial architecture baseline  
**Purpose:** Keep the repository organized, clarify ownership of code, and make it easy to determine where new functionality belongs.  
**Scope:** Rust calculation crates, the Python package, the native extension, tests, benchmarks, documentation, and the external integration project.

This document describes the intended architecture, not a claim that every listed file already exists. Create files as the corresponding sprint requires them. If the implementation needs to depart from this design, update this document in the same change.

---

## 1. Architectural goals

PyTA is a Python technical-analysis library whose indicator calculations are implemented in Rust.

The design aims to:

- Keep numerical calculations in Rust and expose a clean Python API.
- Organize indicators by technical-analysis category.
- Reuse shared data validation, numerical conventions, and execution infrastructure.
- Support both individual indicator calls and mixed batches.
- Provide an explicitly asynchronous Python API backed by an appropriate Rust execution strategy.
- Test the installed package from a separate Python consumer project.
- Add caching, parallelism, and possible GPU support only when justified by requirements and benchmarks.

### Core rule

**Indicator formulas belong in their category crate. Shared infrastructure belongs in `pyta-core` or `pyta-engine`. Python-facing API and packaging belong in the Python package and `pyta-python` bridge.**

Avoid duplicating formulas, input validation, runtime setup, or packaging logic across indicator categories.

---

## 2. Repository layout

The following is the intended main repository layout. Some files and directories are added incrementally as development progresses.

```text
PyTA/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml                 # Add when release automation is needed
├── .vscode/
│   ├── settings.json
│   └── extensions.json                 # Optional, recommended extensions
├── benches/
│   ├── README.md
│   └── ...                              # Benchmark harnesses and datasets
├── docs/
│   ├── ARCHITECTURE.md                  # This document
│   ├── DEVELOPMENT.md                   # Local setup and contributor workflow
│   ├── API.md                           # Public API overview
│   └── indicators/
│       ├── trend.md
│       └── momentum.md
├── python/
│   └── src/
│       └── pyta/
│           ├── __init__.py              # Public package exports
│           ├── _api.py                  # Shared Python-facing wrappers, if needed
│           ├── _async.py                # Async API helpers, if needed
│           ├── _types.py                # Public Python types, if needed
│           ├── _validation.py            # Python-only validation, if needed
│           ├── indicators/
│           │   ├── __init__.py
│           │   ├── trend.py
│           │   └── momentum.py
│           └── py.typed                 # Include when public typing support is ready
├── rust/
│   ├── Cargo.toml                       # Rust workspace root
│   ├── Cargo.lock                       # Commit for this library/application workspace
│   └── crates/
│       ├── pyta-core/
│       │   ├── Cargo.toml
│       │   └── src/
│       │       ├── lib.rs
│       │       ├── input.rs
│       │       ├── error.rs
│       │       └── output.rs
│       ├── pyta-engine/
│       │   ├── Cargo.toml
│       │   └── src/
│       │       ├── lib.rs
│       │       ├── request.rs
│       │       ├── dispatch.rs
│       │       ├── batch.rs
│       │       └── execution.rs
│       ├── pyta-trend/
│       │   ├── Cargo.toml
│       │   └── src/
│       │       ├── lib.rs
│       │       └── sma.rs
│       ├── pyta-momentum/
│       │   ├── Cargo.toml
│       │   └── src/
│       │       ├── lib.rs
│       │       └── rsi.rs
│       └── pyta-python/
│           ├── Cargo.toml
│           └── src/
│               └── lib.rs
├── tests/
│   ├── python/
│   │   ├── test_import.py
│   │   ├── test_trend.py
│   │   ├── test_momentum.py
│   │   └── test_async_api.py
│   ├── reference/
│   │   ├── test_sma_reference.py
│   │   └── test_rsi_reference.py
│   └── fixtures/
├── .gitignore
├── .python-version                      # Optional; align with supported Python version
├── pyproject.toml                       # Python package/build/test configuration
├── rust-toolchain.toml                  # Rust toolchain policy
├── README.md
└── LICENSE

PyTA-Integration/                        # Separate sibling repository/project
├── examples/
│   ├── sma_async.py
│   ├── rsi_async.py
│   └── mixed_batch.py
├── tests/
│   ├── test_installed_package.py
│   └── test_consumer_workflows.py
├── pyproject.toml
└── README.md
```

### Layout notes

- `python/src/pyta/` is the Python `src` layout. The import package is named `pyta`; `src` is only the source container and is not part of the import name.
- `rust/` is the Rust workspace. Its `Cargo.toml` lists the workspace members and shared dependency configuration.
- The root `pyproject.toml` configures Python packaging and Maturin to use the Rust extension crate at `rust/crates/pyta-python/Cargo.toml` and the Python source directory `python/src`.
- `pyta-python` builds the native extension module. The intended extension import path is `pyta._core`; keep the Rust library name, PyO3 module initializer, and Maturin `module-name` setting consistent.
- `PyTA-Integration/` is intentionally separate from the main repository. It should install a built or locally installed PyTA package and must not import the main repository's source files by reaching into its directories.

Directories may be created when first needed rather than all at once.

---

## 3. Ownership and dependency direction

The main components have different responsibilities.

```text
Python user
    |
    v
Python public API: python/src/pyta/
    |
    v
Native bridge: rust/crates/pyta-python/
    |
    v
Execution engine: rust/crates/pyta-engine/
    |
    +------> Shared contracts: rust/crates/pyta-core/
    |
    +------> Category crates: pyta-trend, pyta-momentum, ...
```

This diagram shows logical ownership rather than a requirement that every function call pass through every layer. The engine can depend on category crates; category crates should not depend on the Python bridge.

### Dependency rules

1. `pyta-core` must not depend on indicator-category crates, the Python bridge, or the engine.
2. Category crates may depend on `pyta-core`, but not on `pyta-engine` or `pyta-python`.
3. `pyta-engine` may depend on `pyta-core` and the category crates it dispatches to.
4. `pyta-python` is the boundary between Python/PyO3 and Rust APIs. It may depend on the engine and the required async/runtime integration.
5. The Python package may wrap and organize native calls, but it must not reimplement indicator formulas.
6. Tests may depend on the public API or on the crate being tested. Production crates must not depend on test-only code.
7. Avoid circular dependencies. If two components need the same contract, move that contract to the lowest appropriate shared layer.

---

## 4. Rust crate responsibilities

### `pyta-core` — shared types and numerical contracts

**Owns:**

- Common input and output types.
- Shared validation rules that are relevant across indicators.
- Error types and consistent numerical conventions.
- Shared handling of warm-up periods and missing values, where a common policy is appropriate.

**Does not own:**

- Indicator formulas.
- Python-specific wrappers or PyO3 module registration.
- Batch scheduling, caching policy, or runtime orchestration.

Suggested files:

| File | Responsibility |
|---|---|
| `src/lib.rs` | Public exports for the core crate |
| `src/input.rs` | Shared input representations and validation helpers |
| `src/output.rs` | Shared output structures and metadata |
| `src/error.rs` | Core error types |

Only introduce a separate file when it has a clear responsibility. The initial crate can be smaller.

### `pyta-engine` — requests, dispatch, and execution

**Owns:**

- Indicator request and result models.
- Dispatch from an indicator request to the correct category implementation.
- Batch planning and deterministic result association.
- Execution policy, including where independent work can be scheduled concurrently.
- Engine-level error and partial-batch-failure policy.

**Does not own:**

- The formulas themselves.
- PyO3 module initialization.
- Python-only convenience functions.

Suggested files:

| File | Responsibility |
|---|---|
| `src/lib.rs` | Engine public API |
| `src/request.rs` | Indicator request types and parameters |
| `src/dispatch.rs` | Routes supported requests to implementations |
| `src/batch.rs` | Batch requests and result ordering |
| `src/execution.rs` | Execution policy and orchestration |

Keep the initial engine minimal. Do not create a complex scheduler until the first indicators demonstrate what the engine needs.

### Indicator-category crates

Each category crate owns formulas in that technical-analysis category.

Initial crates:

- `pyta-trend`: trend indicators, beginning with SMA.
- `pyta-momentum`: momentum indicators, beginning with RSI.

Potential future crates include `pyta-volatility`, `pyta-volume`, and `pyta-valuation`. Add them when there is a concrete indicator to implement, rather than creating empty abstractions for every possible category up front.

**Suggested naming pattern:**

- Crate: `pyta-<category>`
- Public Rust function: descriptive `snake_case`, e.g. `sma(...)` or `rsi(...)`
- Implementation file: one indicator per file when practical, e.g. `sma.rs`, `rsi.rs`
- Unit tests: close to the implementation using Rust `#[cfg(test)]` modules, with larger integration tests in the crate's `tests/` directory if needed.

Example:

```text
pyta-trend/
├── Cargo.toml
└── src/
    ├── lib.rs
    └── sma.rs
```

When the crate grows, group related implementations into submodules. Avoid one giant `lib.rs`.

### `pyta-python` — native Python extension

**Owns:**

- PyO3 module initialization.
- Python/Rust type conversion at the native boundary.
- Mapping Rust errors to suitable Python exceptions.
- The native functions or async integration exposed to the Python package.
- Runtime integration needed to provide the promised async behavior.

**Does not own:**

- Indicator formulas.
- The complete public Python API's documentation and convenience organization, where those fit better in the Python package.
- A second copy of core validation logic.

The crate's Rust library name and PyO3 initializer must match the configured extension module name. For the planned import path `pyta._core`, verify that the Cargo library target, `#[pymodule]` name, and Maturin `module-name` are aligned before the first build.

---

## 5. Python package responsibilities

The Python package provides the stable, ergonomic API that users import.

### `python/src/pyta/__init__.py`

- Exposes the supported top-level API.
- Keeps public exports deliberate and documented.
- Avoids exposing internal implementation details unintentionally.

### `python/src/pyta/indicators/`

- Groups user-facing indicator functions by category.
- Provides clear Python names, parameters, docstrings, and typing where useful.
- Delegates calculations to the native extension or engine-backed API.
- Does not reimplement the formulas in Python.

### Optional private modules

Only add these when they solve a real need:

| File | Use it for |
|---|---|
| `_api.py` | Shared private wrappers around native or engine functions |
| `_async.py` | Async convenience wrappers or common async-facing behavior |
| `_types.py` | Public or internal Python type aliases and result models |
| `_validation.py` | Python-specific validation that improves usability; Rust remains authoritative for native safety and numerical contracts |

Prefix private implementation modules with `_`. Do not use an underscore for a supported public module merely to make the directory look tidy.

### Public API shape

The exact signatures should be finalized during implementation. The intended usage should be straightforward and consistent, for example:

```python
import asyncio
import pyta

async def main():
    moving_average = await pyta.async_api.sma(close, window=20)
    relative_strength = await pyta.async_api.rsi(close, window=14)

asyncio.run(main())
```

This is an illustrative API sketch, not a promise that these exact names or signatures already exist. Choose one coherent public API before exposing it in the first release, and cover it with tests.

If synchronous and asynchronous APIs are both provided, they must share the same Rust calculation implementations.

---

## 6. Asynchronous execution model

Asynchrony is an explicit architectural feature, not a side effect of using Python's `async def`.

- An `async def` wrapper alone does not make CPU-heavy Rust work nonblocking.
- The native bridge must use a deliberate integration strategy so that CPU-bound work does not block the Python event loop.
- A runtime such as Tokio can manage asynchronous orchestration; CPU-heavy calculations should use a suitable blocking-worker mechanism or dedicated CPU pool.
- One indicator call and a batch of indicators should use the same core execution path.
- Independent calculations may be scheduled concurrently when that improves throughput.
- Avoid creating one runtime or unbounded task per indicator call.
- Define cancellation, panic/error conversion, batch failure behavior, and shutdown semantics as the async integration is implemented.
- Do not assume that asynchronous scheduling makes one calculation faster. Measure CPU parallelism and scheduling overhead separately.

Keep three concerns distinct:

1. **Public async API:** how Python callers use `await`.
2. **Execution strategy:** where and how Rust work runs.
3. **Batch orchestration:** how multiple requested calculations are dispatched and collected.

---

## 7. Tests and quality checks

Tests should be placed according to what they verify.

### Rust unit tests

Place close to the implementation using Rust `#[cfg(test)]` modules.

Use them for:

- Formula behavior.
- Boundary conditions.
- Parameter validation.
- Warm-up behavior.
- Non-finite values and missing-value conventions.
- Deterministic, hand-calculated cases.

### Rust integration tests

Use a crate-local `tests/` directory when a test needs to exercise that crate through its public Rust API.

### Main repository Python tests

`tests/python/` verifies the installed Python-facing package and its behavior.

`tests/reference/` contains comparisons against independent, trusted reference results. Reference settings must match PyTA's documented formula conventions; two libraries can legitimately differ if they use different smoothing or warm-up conventions.

`tests/fixtures/` contains small, deterministic input and expected-output fixtures. Avoid committing huge market-data files unless there is a clear reason and license to do so.

### External integration tests

`PyTA-Integration/tests/` tests the consumer experience:

- Install the package.
- Import it without source-tree path hacks.
- Call public synchronous or asynchronous functions as supported.
- Validate values, errors, and mixed-batch workflows.

### Baseline quality commands

The exact commands may evolve with configuration, but the core checks should include:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets
cargo test --workspace
maturin develop
pytest
```

Run Cargo commands from `rust/` where appropriate, or use `--manifest-path rust/Cargo.toml` from the repository root. Run Maturin and pytest inside the activated Python environment. Add `--all-features` to checks only when the feature set and CI policy call for it.

---

## 8. Benchmarks and performance work

`benches/` contains reproducible benchmark harnesses, not ordinary correctness tests.

- Record input size, data type, hardware/software context, and invocation method.
- Separate native calculation time from Python/Rust conversion and scheduling overhead where possible.
- Benchmark single-indicator and mixed-batch workloads.
- Use benchmarks to guide decisions about parallelism, caching, and GPU acceleration.
- Keep benchmark data small or generate it deterministically when practical.

Do not add a cache, Rayon, or GPU dependencies solely because they may be useful later. First establish representative workloads and a baseline.

---

## 9. Naming conventions

### Directories and files

- Use lowercase `snake_case` for Python modules and Rust source files: `moving_average.py`, `sma.rs`.
- Use kebab-case for Rust crate/package directory names: `pyta-core`, `pyta-trend`.
- Use descriptive, category-based names rather than generic names such as `misc.rs`, `helpers2.py`, or `stuff/`.
- Prefix private Python modules with `_` when they are not part of the public API.
- Use `test_<subject>.py` for pytest modules and descriptive test names such as `test_rsi_returns_expected_values`.
- Keep one main responsibility per module; split files when they become difficult to navigate, not merely when they reach an arbitrary line count.

### Indicator identifiers

- Use standard indicator names in documentation and public API references.
- Use conventional acronyms where users expect them, such as SMA and RSI.
- Keep Python function names in `snake_case`: `sma`, `rsi`.
- Use consistent parameter naming across indicators where the concepts are the same, such as `window`, `close`, and `volume`.
- Document any non-default formula variants or smoothing methods explicitly.

### Public versus internal interfaces

- Treat functions re-exported from `pyta/__init__.py` as intentional public API.
- Keep internal Rust modules private unless downstream Rust users are deliberately supported.
- Avoid promising stability for internal extension functions or request representations.
- Update API documentation and integration tests whenever a public signature changes.

---

## 10. Configuration and root files

| File | Responsibility |
|---|---|
| `pyproject.toml` | Python packaging metadata, Maturin build backend, Python source layout, and Python tool configuration |
| `rust/Cargo.toml` | Rust workspace members, shared dependency versions, and workspace-wide Rust settings |
| `rust/Cargo.lock` | Locked dependency resolution for reproducible workspace builds; commit it for this project |
| `rust-toolchain.toml` | Rust toolchain channel and any required components/targets |
| `.python-version` | Optional Python-version hint for tools that support it; not a substitute for declared supported versions |
| `.gitignore` | Excludes build output, virtual environments, caches, and local-only files |
| `.vscode/settings.json` | Recommended workspace editor settings |
| `.vscode/extensions.json` | Optional recommendations for Python, Rust Analyzer, and TOML support |
| `README.md` | Project introduction, installation entry point, and short usage example |
| `docs/DEVELOPMENT.md` | Environment setup, local build/test workflow, and contributor instructions |
| `docs/API.md` | Public API reference or index |
| `.github/workflows/ci.yml` | Automated quality checks |
| `.github/workflows/release.yml` | Release automation, once publishing is established |

Keep package metadata in one authoritative place where possible. Do not maintain duplicate version numbers or dependency lists without a clear reason.

---

## 11. Dependency and implementation guardrails

- Keep shared dependencies in `[workspace.dependencies]` when that improves consistency.
- Each crate should declare only the dependencies it actually uses.
- Keep PyO3 and async-runtime details near the native bridge unless another crate genuinely needs them.
- Do not let category crates depend on the Python extension crate.
- Avoid putting every future feature into the first implementation.
- Do not introduce caching until cache keys, data identity, invalidation, memory limits, and concurrency semantics are understood.
- Do not introduce GPU support until benchmarks show that representative workloads justify it.
- Avoid multiple public ways to express the same request unless the difference is useful and documented.
- Keep formula references and test fixtures traceable to their sources.

---

## 12. Where should a change go?

| If you are changing… | Start here |
|---|---|
| A shared input or output contract | `rust/crates/pyta-core/` |
| A technical-analysis formula | Its category crate, e.g. `pyta-trend/src/sma.rs` |
| How indicator requests are routed | `rust/crates/pyta-engine/src/dispatch.rs` |
| Batch result ordering or batch errors | `rust/crates/pyta-engine/src/batch.rs` |
| CPU scheduling or execution policy | `rust/crates/pyta-engine/src/execution.rs` |
| PyO3 registration or native conversion | `rust/crates/pyta-python/src/lib.rs` |
| A public Python convenience wrapper | `python/src/pyta/` |
| Public Python exports | `python/src/pyta/__init__.py` |
| A formula correctness test | Near the Rust implementation and/or `tests/reference/` |
| A Python API regression test | `tests/python/` |
| An installed-package consumer workflow | `PyTA-Integration/tests/` |
| A performance measurement | `benches/` |
| Setup or contributor instructions | `docs/DEVELOPMENT.md` |
| A public API explanation | `docs/API.md` and the relevant docstrings |
| Package/build configuration | Root `pyproject.toml` |
| Rust workspace membership/dependencies | `rust/Cargo.toml` |

---

## 13. How this document stays current

1. Check this document before adding a new directory or module.
2. Prefer the existing ownership boundaries over creating a new abstraction.
3. If a new component is necessary, document its purpose and dependency direction.
4. Update the repository tree and relevant responsibility table in the same pull request.
5. Keep examples consistent with the actual public API. Label sketches as illustrative until implemented.
6. At the end of each sprint, update the development documentation if the setup or workflow changed.

**Architecture acceptance rule:** A change is not complete if it introduces a new permanent architectural component without making its purpose, ownership, and relationship to existing components clear.
