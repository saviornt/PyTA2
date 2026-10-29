"""Reads the reference examples in `tests/fixtures/`.

Each fixture is a CSV file whose `#` comment lines cite the source and give
the parameters as `name: value` (`period:`, or `fast:`, `slow:` and `signal:`
for MACD; a float such as STDDEV's `k: 2.0`) and `tolerance:`. Its columns
are `label`, one or more input columns, and one or more output columns:
`expected` for a single-output indicator, or `expected_<output>` for each
output in documented order. An empty output value is warm-up (NaN). A
single-column example names its input `input`; a multi-column one names each
column by role (`high,low,close`), in the indicator's slot order. The Rust
tests read the same files (`rust/test-support/reference.rs`, same rules).
"""

import contextlib
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _is_output(column: str) -> bool:
    return column == "expected" or column.startswith("expected_")


def _parameters(meta: dict[str, str]) -> dict[str, int | float]:
    """The numeric `name: value` comments other than `tolerance`.

    Whole numbers (`period: 14`) are ints; numbers with a point or exponent
    (`k: 2.0`) are floats. Text (`source:`, `retrieved:`) is not a parameter.
    """
    parameters: dict[str, int | float] = {}
    for key, value in meta.items():
        if key == "tolerance":
            continue
        if value.isdigit():
            parameters[key] = int(value)
            continue
        with contextlib.suppress(ValueError):
            parameters[key] = float(value)
    return parameters


@dataclass(frozen=True, slots=True)
class Reference:
    """One reference example: inputs, expected outputs, parameters and tolerance.

    `outputs` maps each output name (`macd_signal` for `expected_macd_signal`,
    `expected` for a single-output example) to its values in file order;
    `expected` is the first of them.
    """

    source: str
    tolerance: float
    input: NDArray[np.float64]
    columns: dict[str, NDArray[np.float64]]
    outputs: dict[str, NDArray[np.float64]]
    parameters: dict[str, int | float]

    @property
    def expected(self) -> NDArray[np.float64]:
        """The first (for a single-output example, the only) expected output."""
        return next(iter(self.outputs.values()))

    @property
    def period(self) -> int:
        """The `period:` parameter."""
        return int(self.parameters["period"])


def load(name: str) -> Reference:
    """Loads `tests/fixtures/<name>`."""
    meta: dict[str, str] = {}
    rows: list[str] = []

    for line in (FIXTURES / name).read_text().splitlines():
        if line.startswith("#"):
            key, sep, value = line[1:].strip().partition(": ")
            if sep:
                meta[key] = value.strip()
        elif line:
            rows.append(line)

    table = list(csv.DictReader(rows))
    header = [column for column in table[0] if column != "label"]
    inputs = [column for column in header if not _is_output(column)]
    outputs = [column for column in header if _is_output(column)]
    assert inputs, f"{name}: has no input column"
    assert outputs, f"{name}: has no expected column"

    columns = {column: np.array([float(row[column]) for row in table]) for column in inputs}

    return Reference(
        source=meta["source"],
        tolerance=float(meta["tolerance"]),
        input=columns[inputs[0]],
        columns=columns,
        outputs={
            column.removeprefix("expected_"): np.array(
                [float(row[column] or "nan") for row in table]
            )
            for column in outputs
        },
        parameters=_parameters(meta),
    )
