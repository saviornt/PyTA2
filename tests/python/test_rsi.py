"""RSI numerics through the public API."""

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv


def test_known_values() -> None:
    # Changes +1, -1, +2: average gain 1, loss 1/3 over 3 changes.
    result = pyta.rsi(np.array([10.0, 11.0, 10.0, 12.0]), period=3)

    assert np.isnan(result[:3]).all()
    assert result[3] == pytest.approx(75.0)


def test_rising_prices_give_one_hundred_and_falling_give_zero() -> None:
    rising = pyta.rsi(np.arange(1.0, 30.0), period=14)
    falling = pyta.rsi(np.arange(30.0, 1.0, -1.0), period=14)

    assert (rising[14:] == 100.0).all()
    assert (falling[14:] == 0.0).all()


def test_flat_prices_give_zero() -> None:
    assert (pyta.rsi(np.full(20, 5.0), period=5)[5:] == 0.0).all()


@pytest.mark.parametrize("period", [2, 14, 50, 200])
def test_real_closes_stay_between_zero_and_one_hundred(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.rsi(ohlcv.close, period=period)

    assert np.isnan(result[:period]).all()
    assert ((result[period:] >= 0.0) & (result[period:] <= 100.0)).all()


def test_needs_one_more_value_than_the_period() -> None:
    with pytest.raises(ValueError, match="at least 15 values are required, got 14"):
        pyta.rsi(np.ones(14), period=14)


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.rsi(ohlcv.close), pyta.rsi(ohlcv.close, period=14))


@pytest.mark.parametrize("period", [9, 14])
def test_wilder_smoothing_matches_a_python_reference(ohlcv: Ohlcv, period: int) -> None:
    prices = ohlcv.close

    changes = np.diff(prices)
    gain = changes.clip(min=0.0)
    loss = (-changes).clip(min=0.0)
    average_gain, average_loss = gain[:period].mean(), loss[:period].mean()
    expected = [100.0 * average_gain / (average_gain + average_loss)]
    for up, down in zip(gain[period:], loss[period:], strict=True):
        average_gain = (average_gain * (period - 1) + up) / period
        average_loss = (average_loss * (period - 1) + down) / period
        expected.append(100.0 * average_gain / (average_gain + average_loss))

    np.testing.assert_allclose(pyta.rsi(prices, period=period)[period:], expected, rtol=1e-10)
