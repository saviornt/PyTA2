"""DEMA numerics, containers and errors through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_ema(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TA-Lib's EMA in Python: seeded with the mean of the first `period` prices."""
    out = np.full(prices.shape[0], np.nan)
    k = 2.0 / (period + 1)
    out[period - 1] = prices[:period].mean()
    for i in range(period, prices.shape[0]):
        out[i] = (prices[i] - out[i - 1]) * k + out[i - 1]
    return out


def reference_dema(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """DEMA in Python: 2 * EMA1 - EMA2, EMA2 the EMA of EMA1's values."""
    ema1 = reference_ema(prices, period)
    out = np.full(prices.shape[0], np.nan)
    out[period - 1 :] = reference_ema(ema1[period - 1 :], period)
    return 2.0 * ema1 - out


def test_known_values() -> None:
    # Period 3 on a ramp: EMA1 lags by 1, EMA2 by 2, so DEMA is the price.
    result = pyta.dema(np.arange(1.0, 9.0), period=3)

    assert np.isnan(result[:4]).all()
    np.testing.assert_array_equal(result[4:], [5.0, 6.0, 7.0, 8.0])


@pytest.mark.parametrize("period", [2, 10, 30, 100])
def test_matches_a_python_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.dema(ohlcv.close, period=period)
    start = 2 * (period - 1)

    assert np.isnan(result[:start]).all()
    assert np.isfinite(result[start:]).all()
    np.testing.assert_allclose(result, reference_dema(ohlcv.close, period), rtol=1e-12)


def test_period_one_returns_the_input(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.dema(ohlcv.close, period=1), ohlcv.close)


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.dema(ohlcv.close), pyta.dema(ohlcv.close, period=30))


def test_minimum_length_gives_one_value() -> None:
    result = pyta.dema(np.arange(1.0, 6.0), period=3)

    assert np.isnan(result[:4]).all()
    assert result[4] == 5.0


def test_flat_prices_stay_flat() -> None:
    assert (pyta.dema(np.full(400, 7.5), period=10)[18:] == 7.5).all()


def test_overshoots_a_step() -> None:
    # Unlike an EMA of an EMA, DEMA = 2 * EMA1 - EMA2 overshoots a step.
    prices = np.concatenate([np.zeros(10), np.full(10, 10.0)])

    result = pyta.dema(prices, period=3)

    assert result[10] == 7.5
    assert result[12] > 10.0


def test_needs_two_periods_less_one_values() -> None:
    with pytest.raises(ValueError, match="at least 19 values are required, got 18"):
        pyta.dema(np.ones(18), period=10)


@pytest.mark.parametrize(
    ("period", "error", "message"),
    [
        (0, ValueError, "period must be between 1 and 2147483647, got 0"),
        (-3, ValueError, "period must be between 1 and 2147483647, got -3"),
        (2**31, ValueError, "period must be between 1 and 2147483647, got 2147483648"),
        (2.5, TypeError, "period must be an integer, got float"),
        ("5", TypeError, "period must be an integer, got str"),
        (True, TypeError, "period must be an integer, not bool"),
    ],
)
def test_invalid_period(period: object, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        pyta.dema([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_largest_period_reports_its_requirement() -> None:
    with pytest.raises(ValueError, match="at least 4294967293 values are required, got 3"):
        pyta.dema([1.0, 2.0, 3.0], period=2**31 - 1)


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="dema uses one column"):
        pyta.dema({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.dema([1.0, 2.0, np.inf, 4.0], period=2)


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.dema(ohlcv.close, period=10)

    as_list = pyta.dema(ohlcv.close.tolist(), period=10)
    as_dict = pyta.dema(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.dema(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["dema"]
    np.testing.assert_array_equal(as_dict["dema"], want)
    assert list(as_json) == ["dema"]
    assert as_json["dema"][:18] == [None] * 18


def test_title_case_input_gives_title_case_output(ohlcv: Ohlcv) -> None:
    result = pyta.dema({"Close": ohlcv.close.tolist()}, period=10)

    assert list(result) == ["DEMA"]


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_dema(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.dema(series, period=10)

    assert result.name == "dema"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.dema(ohlcv.close, period=10))


def test_output_converts_the_container(ohlcv: Ohlcv) -> None:
    result = pyta.dema(ohlcv.close.tolist(), period=10, output="dict")

    assert list(result) == ["dema"]
    np.testing.assert_array_equal(result["dema"], pyta.dema(ohlcv.close, period=10))


def test_dema_of_an_sma_chains(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=20)

    chained = pyta.dema(sma, period=10)

    # The SMA's 19 warm-up NaN are skipped; the DEMA adds its own 18.
    assert np.isnan(chained[:37]).all()
    np.testing.assert_array_equal(chained[19:], pyta.dema(sma[19:], period=10))


def test_batch_isolates_a_failing_dataset(ohlcv: Ohlcv) -> None:
    results = pyta.batch.dema([ohlcv.close.tolist(), [1.0, 2.0]], period=5)

    np.testing.assert_array_equal(results[0], pyta.dema(ohlcv.close, period=5))
    assert isinstance(results[1], ValueError)
