"""Real daily OHLCV for tests: `tests/fixtures/ohlcv_daily.csv` (300 SPY sessions).

Realistic input, not reference values: expected results are computed
independently (for example with `rolling_mean`) or come from another call.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ohlcv_daily.csv"
COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True, slots=True)
class Ohlcv:
    """The fixture's columns as read-only float64 arrays, plus the ISO dates."""

    dates: list[str]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    volume: NDArray[np.float64]

    def columns(self) -> dict[str, NDArray[np.float64]]:
        """The five numeric columns by role name."""
        return {name: getattr(self, name) for name in COLUMNS}

    def lists(self) -> dict[str, list[float]]:
        """The five numeric columns as lists of floats (a fresh copy)."""
        return {name: values.tolist() for name, values in self.columns().items()}


def load() -> Ohlcv:
    """Reads the fixture, skipping its `#` comment lines."""
    lines = [line for line in FIXTURE.read_text().splitlines() if not line.startswith("#")]
    rows = list(csv.DictReader(lines))

    def column(name: str) -> NDArray[np.float64]:
        values = np.array([float(row[name]) for row in rows])
        values.flags.writeable = False
        return values

    return Ohlcv(
        dates=[row["date"] for row in rows],
        open=column("open"),
        high=column("high"),
        low=column("low"),
        close=column("close"),
        volume=column("volume"),
    )


def rolling_mean(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """SMA computed independently of PyTA: NaN warm-up, then window means."""
    out = np.full(values.shape[0], np.nan)
    out[period - 1 :] = np.convolve(values, np.ones(period) / period, mode="valid")
    return out
