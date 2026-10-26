import numpy as np
import pyta


def test_smoke() -> None:
    prices = np.array([10.0, 11.0, 12.0, 13.0, 12.0, 14.0])

    sma = pyta.sma(prices, period=3)
    rsi = pyta.rsi(prices, period=3)

    assert sma.dtype == np.float64 and rsi.dtype == np.float64
    assert len(sma) == len(prices), "SMA output length mismatch"
    assert len(rsi) == len(prices), "RSI output length mismatch"

    assert np.isnan(sma[:2]).all(), "SMA warm-up alignment is incorrect"
    assert np.isnan(rsi[:3]).all(), "RSI warm-up alignment is incorrect"
    assert np.isfinite(sma[2:]).all()
    assert np.isfinite(rsi[3:]).all()

    try:
        pyta.sma(prices, period=0)
    except ValueError:
        pass
    else:
        raise AssertionError("SMA should reject period=0")

    try:
        pyta.rsi(prices, period=len(prices))
    except ValueError:
        pass
    else:
        raise AssertionError("RSI should reject insufficient data")


if __name__ == "__main__":
    test_smoke()
    print("Python API smoke tests completed.")
