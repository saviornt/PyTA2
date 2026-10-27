"""Measures the cost of the Python layer and the native boundary per indicator.

For each indicator and input size it times:
  public   pyta.<indicator>(ndarray, period=...)       the full user-facing call
  native   pyta._native.<indicator>(ndarray, period)   no validation or restore
  copy     ndarray.copy()                              a memcpy of the same input

and reports `python = public - native`, the cost of the Python layer.
Compare `native` with the Criterion `direct` result for the same size to see
the Rust boundary cost (input copy, GIL release, output array).

Build the extension in release mode first, or the numbers are meaningless:
    uv run --with maturin maturin develop --release \
        --manifest-path rust/crates/pyta-python/Cargo.toml

Run:
    uv run python benches/python/bench_boundary.py [indicator ...]

To benchmark a new indicator, add one line to INDICATORS.
"""

import sys
import timeit
from collections.abc import Callable

import numpy as np

import pyta
from pyta import _native

# indicator name -> period used for the benchmark
INDICATORS: dict[str, int] = {
    "sma": 20,
    "rsi": 14,
}

SIZES = (100, 10_000, 1_000_000)
REPEATS = 5


def format_time(seconds: float) -> str:
    if seconds >= 1e-3:
        return f"{seconds * 1e3:.3f} ms"
    if seconds >= 1e-6:
        return f"{seconds * 1e6:.3f} µs"
    return f"{seconds * 1e9:.1f} ns"


def best_time(fn: Callable[[], object]) -> float:
    """Best-of-N time per call in seconds."""
    number, _ = timeit.Timer(fn).autorange()
    return min(timeit.Timer(fn).repeat(REPEATS, number)) / number


def random_walk(size: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    return 1_000.0 + np.cumsum(rng.uniform(-1.0, 1.0, size))


def main() -> None:
    names = sys.argv[1:] or list(INDICATORS)

    unknown = [name for name in names if name not in INDICATORS]
    if unknown:
        raise SystemExit(f"unknown indicator(s) {unknown}; known: {list(INDICATORS)}")

    header = (
        f"{'Indicator':<10} {'Size':>9} | {'public':>11} {'native':>11} "
        f"{'python':>11} | {'copy':>11}"
    )
    print("\nPython boundary benchmark")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name in names:
        period = INDICATORS[name]
        public = getattr(pyta, name)
        native = getattr(_native, name)

        for size in SIZES:
            data = random_walk(size)

            t_public = best_time(lambda: public(data, period=period))
            t_native = best_time(lambda: native(data, period))
            t_copy = best_time(data.copy)

            print(
                f"{name:<10} {size:>9,} | {format_time(t_public):>11} "
                f"{format_time(t_native):>11} "
                f"{format_time(max(t_public - t_native, 0.0)):>11} | "
                f"{format_time(t_copy):>11}"
            )

        print()

    print("=" * len(header))
    print("python = public - native (validation, normalization, container restore).")


if __name__ == "__main__":
    main()