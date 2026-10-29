"""TEMA numerics, containers and errors through the public API."""

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


def reference_tema(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TEMA in Python: EMA3 + 3 * (EMA1 - EMA2), each EMA of the one before."""
    lag = period - 1
    ema1 = reference_ema(prices, period)
    ema2 = np.full(prices.shape[0], np.nan)
    ema2[lag:] = reference_ema(ema1[lag:], period)
    ema3 = np.full(prices.shape[0], np.nan)
    ema3[2 * lag :] = reference_ema(ema2[2 * lag :], period)
    return ema3 + (3.0 * ema1 - 3.0 * ema2)


def test_known_values() -> None:
    # Period 3 on a ramp: the EMAs lag by 1, 2 and 3, so TEMA is the price.
    result = pyta.tema(np.arange(1.0, 11.0), period=3)

    assert np.isnan(result[:6]).all()
    np.testing.assert_array_equal(result[6:], [7.0, 8.0, 9.0, 10.0])


@pytest.mark.parametrize("period", [2, 10, 30, 90])
def test_matches_a_python_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.tema(ohlcv.close, period=period)
    start = 3 * (period - 1)

    assert np.isnan(result[:start]).all()
    assert np.isfinite(result[start:]).all()
    np.testing.assert_allclose(result, reference_tema(ohlcv.close, period), rtol=1e-12)


def test_period_one_returns_the_input(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.tema(ohlcv.close, period=1), ohlcv.close)


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.tema(ohlcv.close), pyta.tema(ohlcv.close, period=30))


def test_minimum_length_gives_one_value() -> None:
    result = pyta.tema(np.arange(1.0, 8.0), period=3)

    assert np.isnan(result[:6]).all()
    assert result[6] == 7.0


def test_flat_prices_stay_flat() -> None:
    assert (pyta.tema(np.full(400, 7.5), period=10)[27:] == 7.5).all()


def test_overshoots_a_step() -> None:
    prices = np.concatenate([np.zeros(10), np.full(10, 10.0)])

    result = pyta.tema(prices, period=3)

    assert result[10] == 8.75
    assert result[11] == 10.625


def test_needs_three_periods_less_two_values() -> None:
    with pytest.raises(ValueError, match="at least 28 values are required, got 27"):
        pyta.tema(np.ones(27), period=10)


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
        pyta.tema([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_largest_period_reports_its_requirement() -> None:
    with pytest.raises(ValueError, match="at least 6442450939 values are required, got 3"):
        pyta.tema([1.0, 2.0, 3.0], period=2**31 - 1)


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="tema uses one column"):
        pyta.tema({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.tema([1.0, 2.0, np.inf, 4.0], period=2)


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.tema(ohlcv.close, period=10)

    as_list = pyta.tema(ohlcv.close.tolist(), period=10)
    as_dict = pyta.tema(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.tema(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["tema"]
    np.testing.assert_array_equal(as_dict["tema"], want)
    assert list(as_json) == ["tema"]
    assert as_json["tema"][:27] == [None] * 27


def test_title_case_input_gives_title_case_output(ohlcv: Ohlcv) -> None:
    result = pyta.tema({"Close": ohlcv.close.tolist()}, period=10)

    assert list(result) == ["TEMA"]


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_tema(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.tema(series, period=10)

    assert result.name == "tema"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.tema(ohlcv.close, period=10))


def test_output_converts_the_container(ohlcv: Ohlcv) -> None:
    result = pyta.tema(ohlcv.close.tolist(), period=10, output="dict")

    assert list(result) == ["tema"]
    np.testing.assert_array_equal(result["tema"], pyta.tema(ohlcv.close, period=10))


def test_tema_of_a_dema_chains(ohlcv: Ohlcv) -> None:
    dema = pyta.dema(ohlcv.close, period=10)

    chained = pyta.tema(dema, period=5)

    # The DEMA's 18 warm-up NaN are skipped; the TEMA adds its own 12.
    assert np.isnan(chained[:30]).all()
    np.testing.assert_array_equal(chained[18:], pyta.tema(dema[18:], period=5))


def test_batch_isolates_a_failing_dataset(ohlcv: Ohlcv) -> None:
    results = pyta.batch.tema([ohlcv.close.tolist(), [1.0, 2.0]], period=5)

    np.testing.assert_array_equal(results[0], pyta.tema(ohlcv.close, period=5))
    assert isinstance(results[1], ValueError)
