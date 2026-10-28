"""Summarize Criterion results for the engine benchmarks.

Reads only the latest run (`new/estimates.json`) and prints two tables:

  Engine workloads   the batch strategies side by side, per workload and size
  Single calls       the cost of each stage of one call, per indicator and size

Usage:
    python3 scripts/benchmark_summary.py [--since EPOCH_SECONDS]

`--since` ignores results older than the given time, so a filtered run
(for example `--single`) never reports stale numbers from an earlier run.
Exits non-zero if there is nothing to report.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

CRITERION_DIR = Path("target/criterion")

# Batch strategies in display order. `auto` is the planner's own choice and is
# compared against the best of the others.
STRATEGIES = ("sequential", "parallel", "batch", "auto")

# Single-call stages in display order, from raw copy to the full engine path.
STAGES = ("clone", "series_new", "series_from_slice", "kernel", "direct", "engine")

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


def parse_since(argv: list[str]) -> float:
    if "--since" not in argv:
        return 0.0

    try:
        return float(argv[argv.index("--since") + 1])
    except IndexError, ValueError:
        raise SystemExit("--since needs a time in seconds since the epoch") from None


def load_results(since: float) -> tuple[dict, dict]:
    """Returns (workloads, singles): {(group, size): {arm: time in ns}}."""
    workloads: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    singles: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)

    # Layout: <group>/<arm>/<size>/new/estimates.json. The sibling `base` and
    # `change` directories hold the previous run and the relative change, so
    # they must not be read as timings.
    for path in CRITERION_DIR.rglob("estimates.json"):
        parts = path.relative_to(CRITERION_DIR).parts

        if len(parts) != 5 or parts[3] != "new" or not parts[2].isdigit():
            continue

        group, arm, size, _, _ = parts

        try:
            if path.stat().st_mtime < since:
                continue

            estimates = json.loads(path.read_text())
            # Criterion prints the slope estimate when it has one.
            entry = estimates.get("slope") or estimates["mean"]
            time_ns = entry["point_estimate"]
        except OSError, ValueError, KeyError, TypeError:
            continue

        if group.endswith("_single") and arm in STAGES:
            singles[(group, int(size))][arm] = time_ns
        elif arm in STRATEGIES:
            workloads[(group, int(size))][arm] = time_ns

    return workloads, singles


def print_table(title: str, header: str, rows: list[str], footer: str) -> None:
    print(f"\n{title}")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for row in rows:
        print(row)

    print("=" * len(header))
    print(footer)


def workload_table(results: dict) -> None:
    arms = [arm for arm in STRATEGIES if any(arm in times for times in results.values())]
    others = [arm for arm in arms if arm != "auto"]

    header = f"{'Workload':<22} {'Size':>9} | " + " ".join(f"{arm:>17}" for arm in arms)
    header += f" | {'best':<17} {'auto/best':>9}"
    rows = []
    previous = None

    for (group, size), times in sorted(results.items(), key=lambda item: _sort_key(*item)):
        if previous not in (None, group):
            rows.append("")
        previous = group

        candidates = {arm: times[arm] for arm in others if arm in times}
        best, ratio_text, flag = "-", "-", ""

        if candidates:
            best = min(candidates, key=candidates.__getitem__)

            if "auto" in times:
                ratio = times["auto"] / candidates[best]
                ratio_text = f"{ratio:.2f}x"
                flag = "  <-- check" if ratio > AUTO_TOLERANCE else ""

        cells = " ".join(f"{format_time(times.get(arm)):>17}" for arm in arms)
        rows.append(f"{group:<22} {size:>9,} | {cells} | {best:<17} {ratio_text:>9}{flag}")

    print_table(
        "Criterion Summary: engine workloads (latest run)",
        header,
        rows,
        "best: fastest arm other than auto. auto/best: the planner's time divided by that.",
    )


def single_table(results: dict) -> None:
    stages = [stage for stage in STAGES if any(stage in times for times in results.values())]

    header = f"{'Indicator':<12} {'Size':>9} | " + " ".join(f"{stage:>17}" for stage in stages)
    rows = []
    previous = None

    for (group, size), times in sorted(results.items(), key=lambda item: _sort_key(*item)):
        if previous not in (None, group):
            rows.append("")
        previous = group

        cells = " ".join(f"{format_time(times.get(stage)):>17}" for stage in stages)
        rows.append(f"{group.removesuffix('_single'):<12} {size:>9,} | {cells}")

    print_table(
        "Criterion Summary: single calls (latest run)",
        header,
        rows,
        "clone: allocation + copy. series_*: copy + validation. kernel: the formula alone.\n"
        "direct: engine direct path. engine: Tokio + Rayon path with one request.",
    )


def _sort_key(key: tuple[str, int], _times: dict) -> tuple:
    """Orders groups naturally (x10 before x100), then by size."""
    group, size = key
    head, _, tail = group.rpartition("_x")
    return (head, int(tail) if tail.isdigit() else 0, group, size)


def main() -> int:
    workloads, singles = load_results(parse_since(sys.argv[1:]))

    if not workloads and not singles:
        print("No Criterion estimates found.")
        print(f"Expected results beneath: {CRITERION_DIR.resolve()}")
        return 1

    if workloads:
        workload_table(workloads)

    if singles:
        single_table(singles)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
