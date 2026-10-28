"""SMA numerics through the public API."""

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv, rolling_mean


def test_known_values() -> None:
    result = pyta.sma(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), period=2)

    np.testing.assert_allclose(result, [np.nan, 1.5, 2.5, 3.5, 4.5], equal_nan=True)


def test_period_one_returns_the_input() -> None:
    values = np.array([3.0, -1.0, 2.5, 7.0])

    np.testing.assert_array_equal(pyta.sma(values, period=1), values)


def test_period_equal_to_length_gives_one_value() -> None:
    result = pyta.sma(np.array([2.0, 4.0, 6.0, 8.0]), period=4)

    assert np.isnan(result[:3]).all()
    assert result[3] == 5.0


def test_period_longer_than_the_series_raises() -> None:
    with pytest.raises(ValueError, match=r"period \(5\) exceeds the series length \(4\)"):
        pyta.sma([1.0, 2.0, 3.0, 4.0], period=5)


def test_flat_series_gives_a_flat_average() -> None:
    result = pyta.sma(np.full(30, 7.25), period=10)

    assert (result[9:] == 7.25).all()


@pytest.mark.parametrize("period", [5, 20, 50, 200])
def test_matches_a_rolling_mean_of_real_closes(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.sma(ohlcv.close, period=period)

    np.testing.assert_allclose(
        result, rolling_mean(ohlcv.close, period), rtol=1e-12, equal_nan=True
    )


@pytest.mark.parametrize("column", ["open", "high", "low", "volume"])
def test_matches_a_rolling_mean_of_every_real_column(ohlcv: Ohlcv, column: str) -> None:
    values = ohlcv.columns()[column]

    np.testing.assert_allclose(
        pyta.sma(values, period=20), rolling_mean(values, 20), rtol=1e-12, equal_nan=True
    )


def test_chained_sma_skips_the_inner_warm_up() -> None:
    values = np.arange(1.0, 11.0)

    result = pyta.sma(pyta.sma(values, period=3), period=2)

    assert np.isnan(result[:3]).all()
    np.testing.assert_allclose(result[3:], np.arange(2.5, 9.5))
