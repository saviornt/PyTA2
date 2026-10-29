"""Smoke test: a year of real daily OHLCV, as a dict of columns, through the public API.

Runs under pytest and as a script (`python tests/smoke/test_smoke.py`), so it
needs nothing beyond the installed package and the standard library.
"""

import csv
from pathlib import Path

import numpy as np
import pyta

OHLCV = Path(__file__).resolve().parents[1] / "fixtures" / "ohlcv_daily.csv"


def load_ohlcv() -> dict[str, list[str] | list[float]]:
    """Reads the OHLCV fixture into a dict of columns: date, open, high, low, close, volume."""
    lines = [line for line in OHLCV.read_text().splitlines() if not line.startswith("#")]
    rows = list(csv.DictReader(lines))
    data: dict[str, list[str] | list[float]] = {"date": [row["date"] for row in rows]}

    for column in ("open", "high", "low", "close", "volume"):
        data[column] = [float(row[column]) for row in rows]

    return data


def test_smoke() -> None:
    data = load_ohlcv()
    length = len(data["close"])
    assert length == 300, "fixture should hold 300 sessions"

    # The longest planned lookback: the 200-day SMA behind the Mayer Multiple.
    sma = pyta.sma(data, period=200)
    rsi = pyta.rsi(data, period=14)
    volume_sma = pyta.sma(data, period=20, column="volume")

    assert list(sma) == ["sma"], "a dict input returns a dict with one column"
    assert list(rsi) == ["rsi"]
    assert list(volume_sma) == ["sma"]

    sma_values = np.array(sma["sma"])
    rsi_values = np.array(rsi["rsi"])
    assert sma_values.shape == (length,), "SMA output length mismatch"
    assert rsi_values.shape == (length,), "RSI output length mismatch"

    assert np.isnan(sma_values[:199]).all(), "SMA warm-up alignment is incorrect"
    assert np.isnan(rsi_values[:14]).all(), "RSI warm-up alignment is incorrect"
    assert np.isfinite(sma_values[199:]).all()
    assert np.isfinite(rsi_values[14:]).all()

    close = np.array(data["close"])
    assert np.isclose(sma_values[-1], close[-200:].mean(), rtol=1e-12), (
        "SMA does not match the mean of the last 200 closes"
    )
    assert ((rsi_values[14:] >= 0.0) & (rsi_values[14:] <= 100.0)).all()
    assert np.all(np.array(volume_sma["sma"][19:]) > 0.0)

    # Multi-column: the full dict, date column included; high, low and close found by name.
    cci_values = np.array(pyta.cci(data, period=20)["cci"])
    assert cci_values.shape == (length,), "CCI output length mismatch"
    assert np.isnan(cci_values[:19]).all(), "CCI warm-up alignment is incorrect"
    assert np.isfinite(cci_values[19:]).all()

    ema_values = np.array(pyta.ema(data, period=30)["ema"])
    assert ema_values.shape == (length,), "EMA output length mismatch"
    assert np.isnan(ema_values[:29]).all(), "EMA warm-up alignment is incorrect"
    assert np.isfinite(ema_values[29:]).all()

    # Multi-output: one key per output, in documented order, each with its own warm-up.
    macd = pyta.macd(data)
    assert list(macd) == ["macd", "macd_signal", "macd_hist"]
    macd_values, signal_values = np.array(macd["macd"]), np.array(macd["macd_signal"])
    assert macd_values.shape == signal_values.shape == (length,), "MACD output length mismatch"
    assert np.isnan(macd_values[:25]).all()
    assert np.isfinite(macd_values[25:]).all()
    assert np.isnan(signal_values[:33]).all()
    assert np.isfinite(signal_values[33:]).all()

    batch = pyta.batch.sma({"SPY": data, "SPY open": data["open"]}, period=50)
    assert set(batch) == {"SPY", "SPY open"}
    assert not any(isinstance(result, Exception) for result in batch.values())

    try:
        pyta.sma(data, period=0)
    except ValueError:
        pass
    else:
        raise AssertionError("SMA should reject period=0")

    try:
        pyta.rsi(data, period=length)
    except ValueError:
        pass
    else:
        raise AssertionError("RSI should reject insufficient data")


if __name__ == "__main__":
    test_smoke()
    print("Python API smoke tests completed.")
