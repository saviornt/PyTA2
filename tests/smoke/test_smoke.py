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

    atr_values = np.array(pyta.atr(data, period=14)["atr"])
    assert atr_values.dtype == np.float64
    assert atr_values.shape == (length,), "ATR output length mismatch"
    assert np.isnan(atr_values[:14]).all(), "ATR warm-up alignment is incorrect"
    assert (atr_values[14:] > 0.0).all()

    donchian = pyta.donchian(data, period=20)
    assert list(donchian) == ["donchian_upper", "donchian_middle", "donchian_lower"]
    upper, middle, lower = (np.array(donchian[name]) for name in donchian)
    assert middle.dtype == np.float64
    assert upper.shape == middle.shape == lower.shape == (length,), (
        "Donchian output length mismatch"
    )
    assert np.isnan(upper[:19]).all(), "Donchian warm-up alignment is incorrect"
    assert np.isnan(lower[:19]).all(), "Donchian warm-up alignment is incorrect"
    assert upper[-1] == max(data["high"][-20:])
    assert lower[-1] == min(data["low"][-20:])
    assert (lower[19:] <= middle[19:]).all()
    assert (middle[19:] <= upper[19:]).all()

    keltner = pyta.keltner(data, period=20, atr_period=10, k=2.0)
    assert list(keltner) == ["keltner_upper", "keltner_middle", "keltner_lower"]
    upper, middle, lower = (np.array(keltner[name]) for name in keltner)
    assert middle.dtype == np.float64
    assert upper.shape == middle.shape == lower.shape == (length,), "Keltner output length mismatch"
    assert np.isnan(middle[:19]).all(), "Keltner warm-up alignment is incorrect"
    assert np.isnan(upper[:19]).all(), "Keltner warm-up alignment is incorrect"
    assert np.array_equal(middle, np.array(pyta.ema(data["close"], period=20)), equal_nan=True)
    assert (lower[19:] < middle[19:]).all()
    assert (middle[19:] < upper[19:]).all()

    adx = pyta.adx(data, period=14)
    assert list(adx) == ["adx", "adx_plus_di", "adx_minus_di"]
    adx_values, plus_di, minus_di = (np.array(adx[name]) for name in adx)
    assert adx_values.dtype == np.float64
    assert adx_values.shape == plus_di.shape == minus_di.shape == (length,), "ADX length mismatch"
    assert np.isnan(adx_values[:27]).all(), "ADX warm-up alignment is incorrect"
    assert np.isnan(plus_di[:14]).all(), "+DI warm-up alignment is incorrect"
    assert np.isnan(minus_di[:14]).all(), "-DI warm-up alignment is incorrect"
    for line in (adx_values[27:], plus_di[14:], minus_di[14:]):
        assert ((line >= 0.0) & (line <= 100.0)).all()

    sar_values = np.array(pyta.sar(data, acceleration=0.02, maximum=0.2)["sar"])
    assert sar_values.dtype == np.float64
    assert sar_values.shape == (length,), "SAR output length mismatch"
    assert np.isnan(sar_values[0]), "SAR warm-up alignment is incorrect"
    assert np.isfinite(sar_values[1:]).all()
    high, low = np.array(data["high"]), np.array(data["low"])
    assert ((sar_values[1:] <= low[1:]) | (sar_values[1:] >= high[1:])).all()

    aroon_result = pyta.aroon(data, period=14)
    up, down, osc = (
        np.array(aroon_result[name]) for name in ("aroon_up", "aroon_down", "aroon_osc")
    )
    for line in (up, down, osc):
        assert line.dtype == np.float64
        assert line.shape == (length,), "Aroon output length mismatch"
        assert np.isnan(line[:14]).all(), "Aroon warm-up alignment is incorrect"
        assert np.isfinite(line[14:]).all()
    assert ((up[14:] >= 0.0) & (up[14:] <= 100.0) & (down[14:] >= 0.0) & (down[14:] <= 100.0)).all()

    ichimoku_result = pyta.ichimoku(data, tenkan=9, kijun=26, senkou=52)
    assert list(ichimoku_result) == [
        "ichimoku_tenkan",
        "ichimoku_kijun",
        "ichimoku_senkou_a",
        "ichimoku_senkou_b",
        "ichimoku_chikou",
    ]
    lines = [np.array(values) for values in ichimoku_result.values()]
    for line, first in zip(lines, (8, 25, 25, 51, 0), strict=True):
        assert line.dtype == np.float64
        assert line.shape == (length,), "Ichimoku output length mismatch"
        assert np.isnan(line[:first]).all(), "Ichimoku warm-up alignment is incorrect"
        assert np.isfinite(line[first:]).all()
    donchian_middle = np.array(pyta.donchian(data, period=26)["donchian_middle"])
    assert np.array_equal(lines[1], donchian_middle, equal_nan=True)
    assert np.array_equal(lines[4], close)

    stddev_values = np.array(pyta.stddev(data, period=20, k=2.0)["stddev"])
    assert stddev_values.dtype == np.float64
    assert stddev_values.shape == (length,), "STDDEV output length mismatch"
    assert np.isnan(stddev_values[:19]).all(), "STDDEV warm-up alignment is incorrect"
    assert np.isclose(stddev_values[-1], 2.0 * close[-20:].std(), rtol=1e-12)

    ema_values = np.array(pyta.ema(data, period=30)["ema"])
    assert ema_values.shape == (length,), "EMA output length mismatch"
    assert np.isnan(ema_values[:29]).all(), "EMA warm-up alignment is incorrect"
    assert np.isfinite(ema_values[29:]).all()

    wma_values = np.array(pyta.wma(data, period=30)["wma"])
    assert wma_values.dtype == np.float64
    assert wma_values.shape == (length,), "WMA output length mismatch"
    assert np.isnan(wma_values[:29]).all(), "WMA warm-up alignment is incorrect"
    weights = np.arange(1.0, 31.0)
    assert np.isclose(wma_values[-1], close[-30:] @ weights / weights.sum(), rtol=1e-12)

    dema_values = np.array(pyta.dema(data, period=30)["dema"])
    assert dema_values.dtype == np.float64
    assert dema_values.shape == (length,), "DEMA output length mismatch"
    assert np.isnan(dema_values[:58]).all(), "DEMA warm-up alignment is incorrect"
    assert np.isfinite(dema_values[58:]).all()

    tema_values = np.array(pyta.tema(data, period=30)["tema"])
    assert tema_values.dtype == np.float64
    assert tema_values.shape == (length,), "TEMA output length mismatch"
    assert np.isnan(tema_values[:87]).all(), "TEMA warm-up alignment is incorrect"
    assert np.isfinite(tema_values[87:]).all()

    kama_values = np.array(pyta.kama(data, period=30)["kama"])
    assert kama_values.dtype == np.float64
    assert kama_values.shape == (length,), "KAMA output length mismatch"
    assert np.isnan(kama_values[:30]).all(), "KAMA warm-up alignment is incorrect"
    assert np.isfinite(kama_values[30:]).all()

    # Multi-output: one key per output, in documented order, each with its own warm-up.
    macd = pyta.macd(data)
    assert list(macd) == ["macd", "macd_signal", "macd_hist"]
    macd_values, signal_values = np.array(macd["macd"]), np.array(macd["macd_signal"])
    assert macd_values.shape == signal_values.shape == (length,), "MACD output length mismatch"
    assert np.isnan(macd_values[:25]).all()
    assert np.isfinite(macd_values[25:]).all()
    assert np.isnan(signal_values[:33]).all()
    assert np.isfinite(signal_values[33:]).all()

    bbands = pyta.bbands(data)
    assert list(bbands) == ["bbands_upper", "bbands_middle", "bbands_lower"]
    upper, middle, lower = (np.array(bbands[name]) for name in bbands)
    assert middle.dtype == np.float64
    assert upper.shape == middle.shape == lower.shape == (length,), "BBANDS output length mismatch"
    assert np.isnan(upper[:19]).all(), "BBANDS warm-up alignment is incorrect"
    assert np.isnan(lower[:19]).all(), "BBANDS warm-up alignment is incorrect"
    assert (lower[19:] <= middle[19:]).all()
    assert (middle[19:] <= upper[19:]).all()
    assert np.isclose(middle[-1], close[-20:].mean(), rtol=1e-12)

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
