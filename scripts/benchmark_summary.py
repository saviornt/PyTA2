
"""Summarize Criterion results by request count, strategy, and input size."""

import json
import re
from collections import defaultdict
from pathlib import Path

CRITERION_DIR = Path("target/criterion")

WORKLOAD_REQUESTS = {
    "1_sma_ds1": 1,
    "2_rsi_ds1": 1,
    "3_sma_rsi_ds1": 2,
    "4_sma_sma_ds1_ds2": 2,
    "5_rsi_rsi_ds1_ds2": 2,
    "6_sma_rsi_ds1_ds2": 4,
}

STRATEGIES = {"sequential", "batch", "auto"}


def format_time(ns):
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.3f} ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.3f} µs"
    return f"{ns:.2f} ns"


def main():
    # (request count, strategy, input size) -> timing estimates in ns
    results = defaultdict(list)

    for path in CRITERION_DIR.rglob("estimates.json"):
        parts = path.parts

        workload = next(
            (part for part in parts if part in WORKLOAD_REQUESTS),
            None,
        )
        strategy = next(
            (part for part in parts if part in STRATEGIES),
            None,
        )
        size = next(
            (
                int(part)
                for part in parts
                if re.fullmatch(r"\d+", part)
                and int(part) in {100, 10_000, 1_000_000}
            ),
            None,
        )

        if workload is None or strategy is None or size is None:
            continue

        try:
            estimate = json.loads(path.read_text())
            mean_ns = estimate["mean"]["point_estimate"]
        except (OSError, ValueError, KeyError, TypeError):
            continue

        results[
            (WORKLOAD_REQUESTS[workload], strategy, size)
        ].append(mean_ns)

    if not results:
        print("No Criterion estimates found.")
        print(f"Expected results beneath: {CRITERION_DIR.resolve()}")
        return

    print("\nCriterion Summary — Average Time per Workload")
    print("=" * 78)
    print(
        f"{'Requests':>8} | {'Input size':>10} | "
        f"{'Strategy':<10} | {'Avg time':>12} | {'Workloads':>9}"
    )
    print("-" * 78)

    for requests in (1, 2, 4):
        for size in (100, 10_000, 1_000_000):
            for strategy in ("sequential", "batch", "auto"):
                samples = results.get((requests, strategy, size), [])
                if not samples:
                    continue

                average_ns = sum(samples) / len(samples)
                print(
                    f"{requests:>8} | {size:>10,} | "
                    f"{strategy:<10} | {format_time(average_ns):>12} | "
                    f"{len(samples):>9}"
                )

    print("=" * 78)
    print("Times are arithmetic means of Criterion workload estimates.")


if __name__ == "__main__":
    main()
