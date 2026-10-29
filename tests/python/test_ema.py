"""EMA numerics, containers and errors through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_ema(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TA-Lib's EMA written out in Python: SMA seed, then k = 2 / (period + 1)."""
    out = np.full(prices.shape[0], np.nan)
    k = 2.0 / (period + 1)
    out[period - 1] = prices[:period].mean()
    for i in range(period, prices.shape[0]):
        out[i] = out[i - 1] + k * (prices[i] - out[i - 1])
    return out


def test_known_values() -> None:
    # Seed mean(1, 2, 3) = 2; k = 0.5: 2 + 0.5 * (4 - 2) = 3, 3 + 0.5 * (8 - 3) = 5.5.
    result = pyta.ema(np.array([1.0, 2.0, 3.0, 4.0, 8.0]), period=3)

    assert np.isnan(result[:2]).all()
    np.testing.assert_array_equal(result[2:], [2.0, 3.0, 5.5])


@pytest.mark.parametrize("period", [2, 10, 30, 200])
def test_matches_a_python_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.ema(ohlcv.close, period=period)

    assert np.isnan(result[: period - 1]).all()
    assert np.isfinite(result[period - 1 :]).all()
    np.testing.assert_allclose(result, reference_ema(ohlcv.close, period), rtol=1e-12)


def test_period_one_returns_the_input(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.ema(ohlcv.close, period=1), ohlcv.close)


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.ema(ohlcv.close), pyta.ema(ohlcv.close, period=30))


def test_flat_prices_stay_flat() -> None:
    assert (pyta.ema(np.full(40, 7.5), period=10)[9:] == 7.5).all()


def test_needs_at_least_period_values() -> None:
    with pytest.raises(ValueError, match="at least 10 values are required, got 9"):
        pyta.ema(np.ones(9), period=10)


@pytest.mark.parametrize(
    ("period", "error", "message"),
    [
        (0, ValueError, "period must be between 1 and 2147483647, got 0"),
        (-3, ValueError, "period must be between 1 and 2147483647, got -3"),
        (2.5, TypeError, "period must be an integer, got float"),
        ("5", TypeError, "period must be an integer, got str"),
        (True, TypeError, "period must be an integer, not bool"),
    ],
)
def test_invalid_period(period: object, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        pyta.ema([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="ema uses one column"):
        pyta.ema({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.ema(ohlcv.close, period=10)

    as_list = pyta.ema(ohlcv.close.tolist(), period=10)
    as_dict = pyta.ema(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.ema(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["ema"]
    np.testing.assert_array_equal(as_dict["ema"], want)
    assert list(as_json) == ["ema"]
    assert as_json["ema"][:9] == [None] * 9


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_ema(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.ema(series, period=10)

    assert result.name == "ema"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.ema(ohlcv.close, period=10))


def test_ema_of_an_sma_chains(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=20)

    chained = pyta.ema(sma, period=10)

    # The SMA's 19 warm-up NaN are skipped; the EMA adds its own 9.
    assert np.isnan(chained[:28]).all()
    np.testing.assert_array_equal(chained[19:], pyta.ema(sma[19:], period=10))
