"""Measures `pyta.batch` end to end against a loop of single calls.

For each indicator, dataset count, and points per dataset it times:
  loop    [pyta.<indicator>(d, period=...) for d in datasets]   one call per dataset
  batch   pyta.batch.<indicator>(datasets, period=...)          one call for all

and reports the time per dataset for each, plus `speedup = loop / batch`.
Both include the Python layer (validation and container restore), so this is
what a user sees. Speedup below 1.0 means the batch call is slower; expect that
for many tiny datasets, where per-dataset Python cost dominates the kernel.

Build the extension in release mode first, or the numbers are meaningless:
    uv run --with maturin maturin develop --release \
        --manifest-path rust/crates/pyta-python/Cargo.toml

Run:
    uv run python benches/python/bench_batch.py [--quick] [indicator ...]

To benchmark a new indicator, add one line to INDICATORS.
"""

import sys
import timeit
from collections.abc import Callable

import numpy as np
import pyta

# indicator name -> period used for the benchmark
INDICATORS: dict[str, int] = {
    "sma": 20,
    "rsi": 14,
}

COUNTS = (10, 100, 1_000)
SIZES = (100, 1_000, 10_000)
REPEATS = 5
QUICK_REPEATS = 2


def format_time(seconds: float) -> str:
    if seconds >= 1e-3:
        return f"{seconds * 1e3:.3f} ms"
    if seconds >= 1e-6:
        return f"{seconds * 1e6:.3f} µs"
    return f"{seconds * 1e9:.1f} ns"


def best_time(fn: Callable[[], object], repeats: int) -> float:
    """Best-of-N time per call in seconds."""
    number, _ = timeit.Timer(fn).autorange()
    return min(timeit.Timer(fn).repeat(repeats, number)) / number


def datasets(count: int, size: int) -> list[np.ndarray]:
    """Distinct, deterministic random walks."""
    return [
        1_000.0 + np.cumsum(np.random.default_rng(seed).uniform(-1.0, 1.0, size))
        for seed in range(count)
    ]


def main() -> None:
    args = sys.argv[1:]
    quick = "--quick" in args
    names = [arg for arg in args if arg != "--quick"] or list(INDICATORS)
    repeats = QUICK_REPEATS if quick else REPEATS

    unknown = [name for name in names if name not in INDICATORS]
    if unknown:
        raise SystemExit(f"unknown indicator(s) {unknown}; known: {list(INDICATORS)}")

    header = (
        f"{'Indicator':<10} {'Datasets':>8} {'Size':>7} | {'loop/ds':>11} {'batch/ds':>11} "
        f"| {'speedup':>8}"
    )
    print("\nPython batch benchmark" + (" (quick)" if quick else ""))
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name in names:
        period = INDICATORS[name]
        single = getattr(pyta, name)
        batch = getattr(pyta.batch, name)

        for count in COUNTS:
            for size in SIZES:
                data = datasets(count, size)

                t_loop = best_time(lambda: [single(d, period=period) for d in data], repeats)
                t_batch = best_time(lambda: batch(data, period=period), repeats)

                print(
                    f"{name:<10} {count:>8,} {size:>7,} | {format_time(t_loop / count):>11} "
                    f"{format_time(t_batch / count):>11} | {t_loop / t_batch:>7.2f}x"
                )

            print()

    print("=" * len(header))
    print("loop/ds, batch/ds: time per dataset. speedup = loop / batch.")


if __name__ == "__main__":
    main()
