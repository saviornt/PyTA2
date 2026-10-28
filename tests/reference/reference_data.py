"""Reads the published reference examples in `tests/fixtures/`.

Each fixture is a CSV file whose `#` comment lines cite the source and give
`period:` and `tolerance:`; its columns are `label,input,expected`, with an
empty `expected` for warm-up rows (NaN). The Rust tests read the same files.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@dataclass(frozen=True, slots=True)
class Reference:
    """One published example: input, expected output, period and tolerance."""

    source: str
    period: int
    tolerance: float
    input: NDArray[np.float64]
    expected: NDArray[np.float64]


def load(name: str) -> Reference:
    """Loads `tests/fixtures/<name>`."""
    meta: dict[str, str] = {}
    rows: list[str] = []

    for line in (FIXTURES / name).read_text().splitlines():
        if line.startswith("#"):
            key, sep, value = line[1:].strip().partition(": ")
            if sep and key in ("source", "period", "tolerance"):
                meta[key] = value
        elif line:
            rows.append(line)

    table = list(csv.DictReader(rows))

    return Reference(
        source=meta["source"],
        period=int(meta["period"]),
        tolerance=float(meta["tolerance"]),
        input=np.array([float(row["input"]) for row in table]),
        expected=np.array([float(row["expected"] or "nan") for row in table]),
    )
