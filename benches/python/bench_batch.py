"""Measures `pyta.batch` end to end against a loop of single calls.

For each indicator, dataset count, and points per dataset it times:
  loop    [pyta.<indicator>(d, period=...) for d in datasets]   one call per dataset
  batch   pyta.batch.<indicator>(datasets, period=...)          one call for all

(MACD takes fast=, slow=, signal= instead of period=), and reports the time per
dataset for each, plus `speedup = loop / batch`.
Both include the Python layer (validation and container restore), so this is
what a user sees. Speedup below 1.0 means the batch call is slower; expect that
for many tiny datasets, where per-dataset Python cost dominates the kernel.

Build the extension in release mode first, or the numbers are meaningless:
    uv run maturin develop --release \
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

# indicator name -> (keyword parameters for the benchmark, TA-Lib's defaults where it has
# them; number of input columns, taken in the order high, low, close, volume, or the
# input roles when they are not a prefix of that order).
INDICATORS: dict[str, tuple[dict[str, int | float], int | tuple[str, ...]]] = {
    "sma": ({"period": 20}, 1),
    "rsi": ({"period": 14}, 1),
    "cci": ({"period": 14}, 3),
    "stoch": ({"k": 14, "k_smooth": 3, "d": 3}, 3),
    "willr": ({"period": 14}, 3),
    "roc": ({"period": 10}, 1),
    "mfi": ({"period": 14}, 4),
    "trix": ({"period": 30}, 1),
    "ultosc": ({"short": 7, "medium": 14, "long": 28}, 3),
    "ema": ({"period": 30}, 1),
    "wma": ({"period": 30}, 1),
    "dema": ({"period": 30}, 1),
    "tema": ({"period": 30}, 1),
    "kama": ({"period": 30}, 1),
    "adx": ({"period": 14}, 3),
    "sar": ({"acceleration": 0.02, "maximum": 0.2}, 2),
    "aroon": ({"period": 14}, 2),
    "ichimoku": ({"tenkan": 9, "kijun": 26, "senkou": 52}, 3),
    "macd": ({"fast": 12, "slow": 26, "signal": 9}, 1),
    "atr": ({"period": 14}, 3),
    "stddev": ({"period": 5, "k": 1.0}, 1),
    "bbands": ({"period": 20, "k": 2.0}, 1),
    "donchian": ({"period": 20}, 2),
    "keltner": ({"period": 20, "atr_period": 10, "k": 2.0}, 3),
    "obv": ({}, ("close", "volume")),
    "ad": ({}, 4),
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


def datasets(count: int, size: int, width: int | tuple[str, ...]) -> list[object]:
    """Distinct, deterministic random walks; a dict of high, low and close (and
    volume for four columns, or exactly the roles given) for a multi-column
    indicator."""
    walks = [
        1_000.0 + np.cumsum(np.random.default_rng(seed).uniform(-1.0, 1.0, size))
        for seed in range(count)
    ]

    if width == 1:
        return list(walks)

    if isinstance(width, tuple):
        every = [
            {"high": walk + 0.5, "low": walk - 0.5, "close": walk, "volume": 1_000.0 * walk}
            for walk in walks
        ]
        return [{role: columns[role] for role in width} for columns in every]

    if width == 4:
        return [
            {"high": walk + 0.5, "low": walk - 0.5, "close": walk, "volume": 1_000.0 * walk}
            for walk in walks
        ]

    return [{"high": walk + 0.5, "low": walk - 0.5, "close": walk} for walk in walks]


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
        params, width = INDICATORS[name]
        single = getattr(pyta, name)
        batch = getattr(pyta.batch, name)

        for count in COUNTS:
            for size in SIZES:
                data = datasets(count, size, width)

                t_loop = best_time(lambda: [single(d, **params) for d in data], repeats)
                t_batch = best_time(lambda: batch(data, **params), repeats)

                print(
                    f"{name:<10} {count:>8,} {size:>7,} | {format_time(t_loop / count):>11} "
                    f"{format_time(t_batch / count):>11} | {t_loop / t_batch:>7.2f}x"
                )

            print()

    print("=" * len(header))
    print("loop/ds, batch/ds: time per dataset. speedup = loop / batch.")


if __name__ == "__main__":
    main()
