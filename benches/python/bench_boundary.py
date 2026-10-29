"""Measures the cost of the Python layer and the native boundary per indicator.

For each indicator and input size it times:
  public   pyta.<indicator>(ndarray, period=...)       the full user-facing call
  native   pyta._native.<indicator>(ndarray, period)   no validation or restore
  copy     ndarray.copy()                              a memcpy of the same input

(MACD takes fast=, slow=, signal= instead of period=, and returns three outputs.)

A multi-column indicator gets a dict of high, low and close arrays (found by
role) in the public call, the list of arrays in the native call, and `copy`
copies every column.

and reports `python = public - native`, the cost of the Python layer.
Compare `native` with the Criterion `direct` result for the same size to see
the Rust boundary cost (input copy, GIL release, output array).

Build the extension in release mode first, or the numbers are meaningless:
    uv run maturin develop --release \
        --manifest-path rust/crates/pyta-python/Cargo.toml

Run:
    uv run python benches/python/bench_boundary.py [--quick] [indicator ...]

To benchmark a new indicator, add one line to INDICATORS.
"""

import sys
import timeit
from collections.abc import Callable

import numpy as np
import pyta
from pyta import _native

# indicator name -> (keyword parameters for the benchmark, TA-Lib's defaults where it has
# them; number of input columns). The native call takes the same values positionally.
INDICATORS: dict[str, tuple[dict[str, int | float], int]] = {
    "sma": ({"period": 20}, 1),
    "rsi": ({"period": 14}, 1),
    "cci": ({"period": 14}, 3),
    "ema": ({"period": 30}, 1),
    "macd": ({"fast": 12, "slow": 26, "signal": 9}, 1),
    "atr": ({"period": 14}, 3),
    "stddev": ({"period": 5, "k": 1.0}, 1),
    "bbands": ({"period": 20, "k": 2.0}, 1),
    "donchian": ({"period": 20}, 2),
}

SIZES = (100, 10_000, 1_000_000)
REPEATS = 5
QUICK_REPEATS = 2


def format_time(seconds: float) -> str:
    if seconds >= 1e-3:
        return f"{seconds * 1e3:.3f} ms"
    if seconds >= 1e-6:
        return f"{seconds * 1e6:.3f} µs"
    return f"{seconds * 1e9:.1f} ns"


def best_time(fn: Callable[[], object], repeats: int = REPEATS) -> float:
    """Best-of-N time per call in seconds."""
    number, _ = timeit.Timer(fn).autorange()
    return min(timeit.Timer(fn).repeat(repeats, number)) / number


def random_walk(size: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    return 1_000.0 + np.cumsum(rng.uniform(-1.0, 1.0, size))


def inputs(size: int, width: int) -> tuple[object, object, Callable[[], object]]:
    """Public input, native input, and a copy of the same data."""
    close = random_walk(size)

    if width == 1:
        return close, close, close.copy

    columns = {"high": close + 0.5, "low": close - 0.5, "close": close}
    arrays = list(columns.values())
    return columns, arrays, lambda: [array.copy() for array in arrays]


def main() -> None:
    args = sys.argv[1:]
    quick = "--quick" in args
    names = [arg for arg in args if arg != "--quick"] or list(INDICATORS)
    repeats = QUICK_REPEATS if quick else REPEATS

    unknown = [name for name in names if name not in INDICATORS]
    if unknown:
        raise SystemExit(f"unknown indicator(s) {unknown}; known: {list(INDICATORS)}")

    header = (
        f"{'Indicator':<10} {'Size':>9} | {'public':>11} {'native':>11} "
        f"{'python':>11} | {'copy':>11}"
    )
    print("\nPython boundary benchmark" + (" (quick)" if quick else ""))
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name in names:
        params, width = INDICATORS[name]
        public = getattr(pyta, name)
        native = getattr(_native, name)

        for size in SIZES:
            data, native_data, copy = inputs(size, width)

            t_public = best_time(lambda: public(data, **params), repeats)
            t_native = best_time(lambda: native(native_data, *params.values()), repeats)
            t_copy = best_time(copy, repeats)

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
