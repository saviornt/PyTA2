"""Summarize Criterion results per workload and input size.

Reads only the latest run (`new/estimates.json`) and compares the
sequential, batch, and auto strategies side by side.
"""

import json
from collections import defaultdict
from pathlib import Path

CRITERION_DIR = Path("target/criterion")
STRATEGIES = ("sequential", "batch", "auto")

# Flag rows where the planner's choice is this much slower than the best arm.
AUTO_TOLERANCE = 1.10


def format_time(ns: float | None) -> str:
    if ns is None:
        return "-"
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.3f} ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.3f} µs"
    return f"{ns:.1f} ns"


def load_results() -> dict[tuple[str, int], dict[str, float]]:
    """Maps (workload, input size) to {strategy: time in ns}."""
    results: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)

    # Layout: <workload>/<strategy>/<size>/new/estimates.json. The sibling
    # `base` and `change` directories hold the previous run and the relative
    # change, so they must not be read as timings.
    for path in CRITERION_DIR.rglob("estimates.json"):
        parts = path.relative_to(CRITERION_DIR).parts

        if len(parts) != 5 or parts[3] != "new":
            continue

        workload, strategy, size, _, _ = parts

        if strategy not in STRATEGIES or not size.isdigit():
            continue

        try:
            estimates = json.loads(path.read_text())
            # Criterion prints the slope estimate when it has one.
            entry = estimates.get("slope") or estimates["mean"]
            results[(workload, int(size))][strategy] = entry["point_estimate"]
        except (OSError, ValueError, KeyError, TypeError):
            continue

    return results


def main() -> None:
    results = load_results()

    if not results:
        print("No Criterion estimates found.")
        print(f"Expected results beneath: {CRITERION_DIR.resolve()}")
        return

    header = (
        f"{'Workload':<20} {'Size':>9} | {'sequential':>12} {'batch':>12} "
        f"{'auto':>12} | {'best':<10} {'auto/best':>9}"
    )
    print("\nCriterion Summary — latest run, per workload")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    previous_workload = None

    for (workload, size), times in sorted(results.items()):
        if previous_workload not in (None, workload):
            print()
        previous_workload = workload

        sequential = times.get("sequential")
        batch = times.get("batch")
        auto = times.get("auto")

        candidates = {
            name: value
            for name, value in (("sequential", sequential), ("batch", batch))
            if value is not None
        }

        best_name, ratio_text, flag = "-", "-", ""

        if candidates:
            best_name = min(candidates, key=candidates.__getitem__)

            if auto is not None:
                ratio = auto / candidates[best_name]
                ratio_text = f"{ratio:.2f}x"
                flag = "  <-- check" if ratio > AUTO_TOLERANCE else ""

        print(
            f"{workload:<20} {size:>9,} | {format_time(sequential):>12} "
            f"{format_time(batch):>12} {format_time(auto):>12} | "
            f"{best_name:<10} {ratio_text:>9}{flag}"
        )

    print("=" * len(header))
    print("auto/best: planner's time divided by the faster of sequential/batch.")


if __name__ == "__main__":
    main()