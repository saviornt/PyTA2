# PyTA API Design

> **Status:** Proposed API contract  
> **Scope:** Public Python API and the Rust execution architecture behind it  
> **Audience:** Contributors implementing PyTA and users integrating it into Python applications

This document defines the intended public API and execution model for PyTA. It is a design contract for implementation, not a claim that every example below is already available in a released package. Names and signatures should be reconciled with the implementation as it is built.

## 1. Design goals

PyTA is a technical-analysis library with a Rust computation backend and a Python-first interface. Its API should:

1. Keep the common case concise and Pythonic.
2. Route all indicator calculations—single or batched—through the same Rust execution engine.
3. Use Tokio to coordinate asynchronous work inside Rust.
4. Keep runtime management, scheduling details, and implementation-specific async controls out of the public Python API.
5. Support Python asynchronous applications without blocking their event loop.
6. Make batch calculations ergonomic and allow the engine to apply bounded concurrency.
7. Provide predictable validation, errors, result ordering, and numerical semantics.
8. Leave room for a broad and growing catalog of technical indicators without requiring a new execution model for each indicator.

## 2. Architectural ownership

| Layer | Responsibility |
|---|---|
| Python public API | User-facing functions, indicator configuration, input normalization, type hints, documentation, and Python ecosystem integration |
| Python/Rust binding | Converts supported Python inputs and outputs; safely bridges Python awaitables and native execution |
| Rust execution engine | Owns the Tokio runtime lifecycle, request scheduling, batch orchestration, cancellation policy, and concurrency limits |
| Rust CPU execution | Runs CPU-bound numerical kernels on an appropriate bounded worker pool; scheduler choice is an implementation detail to benchmark |
| Rust indicator implementations | Indicator-specific algorithms, validation of computational parameters, and numerical behavior |

### Runtime principles

- **Rust owns internal asynchronous execution.** Python's `asyncio` is an integration surface, not the owner of PyTA's internal task scheduling.
- **Tokio coordinates work; it is not automatically the right place to run every CPU-heavy loop.** The implementation may use `spawn_blocking`, Rayon, or a dedicated bounded pool based on benchmarks.
- **One public execution model.** Single-indicator and batch calls use the same engine and lifecycle.
- **No per-call runtime creation as the default.** The runtime should be managed deliberately and reused where appropriate.
- **Do not block the Python event loop.** Awaitable APIs must yield control while native work is pending. Native execution should release the GIL when safe and useful.
- **Do not expose runtime controls unless a concrete user requirement justifies them.** Users should not have to pass `async_api`, select a runtime, or choose between sync and async calculation modes.

## 3. Public API shape

The intended public surface has three related forms:

1. **Convenience functions** for common indicators.
2. **Configured indicator objects** for composing batches.
3. **A batch function** for requesting multiple calculations in one call.

All calculation entry points are asynchronous. This keeps the interface consistent and prevents the API from splitting into separate synchronous and asynchronous calculation systems.

### 3.1 Convenience function

```python
import pyta

rsi_values = await pyta.rsi(close, period=14)
```

A convenience function should provide sensible defaults where the indicator definition supports them, accept explicit keyword arguments for meaningful parameters, and return a documented result type.

### 3.2 Indicator configuration

```python
import pyta

rsi = pyta.RSI(period=14)
macd = pyta.MACD(fast_period=12, slow_period=26, signal_period=9)
sma = pyta.SMA(period=50)
```

Configuration objects describe requested work; they should not start calculations when constructed. This makes them reusable in batches, easy to inspect, and suitable for validation before execution.

### 3.3 Batch calculation

```python
results = await pyta.calculate(
    close=close,
    indicators=[
        pyta.RSI(period=14),
        pyta.MACD(),
        pyta.SMA(period=50),
    ],
)

rsi_values = results[0]
macd_values = results[1]
sma_values = results[2]
```

This is an illustrative signature. The implementation must decide whether each indicator configuration declares its required input columns (for example, `close`, or `high`, `low`, and `close`) and whether batch results are best represented as an ordered result collection, a mapping keyed by request name, or a dedicated result object. Whichever representation is selected, result association and ordering must be deterministic and documented.

The batch API should avoid requiring users to manually create tasks or manage a separate async API. The engine may run independent calculations concurrently, subject to resource limits and dependency constraints.

### 3.4 Multiple input columns

Indicators can require different market data fields. A clear candidate interface is to accept named columns:

```python
results = await pyta.calculate(
    high=high,
    low=low,
    close=close,
    indicators=[
        pyta.RSI(period=14),
        pyta.ATR(period=14),
    ],
)
```

The exact data container and parameter binding are implementation decisions. The public contract should make required fields explicit and reject missing or incompatible inputs with useful errors.

## 4. Inputs and outputs

### Inputs

The API should document which input forms are supported. Candidate forms include:

- Python sequences and NumPy arrays.
- Pandas Series, if pandas integration is supported.
- Other columnar inputs only when explicitly implemented and tested.

Input normalization should happen at a well-defined boundary. Avoid repeatedly copying the same large input arrays when a batch can safely share normalized data. Any zero-copy or borrowed-buffer optimization must respect the source object's lifetime, memory layout, dtype, mutability, and thread-safety constraints.

### Output contract

The implementation should standardize:

- Output type and dtype.
- Output length and index alignment.
- Representation of warm-up periods (for example, `NaN` or another documented missing-value convention).
- Behavior for insufficient input length.
- Handling of non-finite values.
- Whether outputs are newly allocated or may share memory.
- How multi-output indicators (such as MACD) are represented.

The same indicator and input should have consistent numerical semantics whether invoked alone or as part of a batch.

## 5. Async and execution semantics

### 5.1 One calculation

```python
values = await pyta.sma(close, period=20)
```

The request enters the Rust execution engine even when it contains only one indicator. The engine chooses the appropriate execution path; a small calculation does not have to create multiple tasks or threads merely to be considered asynchronous.

### 5.2 A batch

```python
results = await pyta.calculate(
    close=close,
    indicators=[
        pyta.SMA(period=20),
        pyta.EMA(period=20),
        pyta.RSI(period=14),
    ],
)
```

The engine can schedule independent indicators concurrently. It should apply bounded concurrency rather than spawning an unbounded number of tasks for a large request. Where one requested computation depends on another, the engine must preserve that dependency.

### 5.3 Calling from an async application

```python
async def analyze_market(close):
    return await pyta.rsi(close, period=14)
```

Awaiting PyTA should integrate with the caller's event loop without requiring the caller to initialize or manage Tokio. Internal runtime details remain private.

### 5.4 Calling from ordinary synchronous code

Because the proposed calculation API is async, ordinary synchronous scripts need an event loop boundary:

```python
import asyncio
import pyta

async def main():
    values = await pyta.rsi(close, period=14)
    print(values)

asyncio.run(main())
```

PyTA should not quietly create nested event loops or block an already-running Python event loop to make an async calculation appear synchronous. If a synchronous convenience wrapper is ever added, it should be a separately designed interface with explicit behavior and limitations—not an `async_api` switch on every calculation.

## 6. Error handling and validation

Errors should be clear, stable, and actionable. The public layer should distinguish at least:

- Invalid indicator parameters (for example, a period outside the supported range).
- Missing required input columns.
- Unsupported input types, dtypes, or memory layouts.
- Input length or shape mismatches.
- Insufficient data for a requested calculation.
- Numerical or computation failures.
- Runtime shutdown or internal execution failures.
- Cancellation, if cancellation is exposed as part of the supported contract.

Expected user-input errors should be translated into appropriate Python exceptions. Internal Rust details should not leak as opaque panics. Panics must not cross the FFI boundary; the binding should convert failures into a controlled error representation.

Validation should occur as early as practical, but the engine must still protect its own invariants. Batch errors need a documented policy: either fail the entire batch atomically or report per-indicator successes and failures. Do not leave this behavior implicit.

## 7. Cancellation, concurrency, and resource limits

The first implementation should define these policies even if some are introduced incrementally:

- How cancelling the Python awaitable maps to Rust work.
- Whether already-running CPU kernels can be interrupted or only allowed to finish.
- Maximum concurrent CPU-bound jobs.
- How large batches are queued and back-pressured.
- Whether duplicate requests may share work (not required initially).
- How shutdown behaves when requests are in flight.
- Whether results are returned in request order regardless of completion order.

Cancellation must not imply that a CPU kernel has stopped unless the implementation can guarantee it. Document the actual semantics.

## 8. Indicator API conventions

Every indicator should follow consistent conventions:

- Use descriptive, documented parameter names.
- Use keyword arguments for optional parameters.
- Provide defaults only when the indicator definition has an established conventional default.
- Define input fields explicitly.
- Document output shape, warm-up behavior, and numerical semantics.
- Validate periods and other parameters consistently.
- Keep indicator configuration separate from execution.
- Use one implementation of the algorithm regardless of whether it is called alone or in a batch.

Potential initial indicators include SMA, EMA, RSI, and MACD. Their inclusion here describes the intended API examples, not a guarantee that they have already been implemented.

## 9. Performance principles

Performance should be measured rather than inferred from the use of async alone.

Benchmarks should cover:

1. One small indicator on a small input.
2. One indicator on a large input.
3. Several independent indicators in a batch.
4. A large batch with concurrency limits.
5. Input conversion and output conversion overhead.
6. Warm runtime versus first-call initialization.
7. Memory allocation and data-copy costs.
8. Comparison with a clear reference implementation.

Tokio is an architectural choice for async coordination, not a promise that every calculation will become faster. For CPU-bound indicator kernels, algorithm efficiency, memory locality, vectorization, allocation behavior, and parallel scheduling may matter more than async task count. Avoid parallelizing tiny workloads when scheduling overhead exceeds the benefit.

## 10. API stability and implementation status

This document defines the **intended design**. Before treating the examples as a stable public contract, implementation work must settle:

- Exact module and function names.
- Exact indicator configuration types.
- Accepted input types and conversion rules.
- Batch input binding and result container.
- Output representation for single-output and multi-output indicators.
- Error classes and batch failure policy.
- Cancellation behavior.
- Runtime lifecycle and shutdown behavior.
- Supported Python and Rust versions.
- Dependency and packaging strategy for the native extension.

When these are finalized, update this document alongside the implementation and tests. Do not document an example as supported until a test exercises it.

## 11. Decision summary

- **Backend language:** Rust.
- **Internal async runtime:** Tokio.
- **Execution ownership:** Rust owns internal scheduling and orchestration.
- **CPU-bound work:** A bounded CPU execution mechanism selected through benchmarks.
- **Python's role:** Public API, input/output integration, and compatibility with Python async applications.
- **Calculation interface:** Async-only calculation entry points; no `async_api` toggle.
- **Single and batch calls:** Both use the same Rust execution engine.
- **Runtime management:** Managed internally, not created ad hoc for each calculation.
- **Core requirement:** Awaiting a calculation must not block the Python event loop.

These decisions establish a consistent base for expanding PyTA's indicator catalog without repeatedly revisiting the fundamental execution model.
