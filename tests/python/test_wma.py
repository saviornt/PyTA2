"""WMA numerics, containers and errors through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_wma(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TA-Lib's WMA written out in Python: weights 1 (oldest) to `period` (newest)."""
    out = np.full(prices.shape[0], np.nan)
    weights = np.arange(1.0, period + 1.0)
    for i in range(period - 1, prices.shape[0]):
        out[i] = prices[i + 1 - period : i + 1] @ weights / weights.sum()
    return out


def test_known_values() -> None:
    # Period 3, divisor 6: (1 + 2*2 + 3*4) / 6 = 17/6, (2 + 2*4 + 3*10) / 6 = 40/6.
    result = pyta.wma(np.array([1.0, 2.0, 4.0, 10.0]), period=3)

    assert np.isnan(result[:2]).all()
    np.testing.assert_allclose(result[2:], [17.0 / 6.0, 40.0 / 6.0], rtol=1e-15)


@pytest.mark.parametrize("period", [2, 10, 30, 200])
def test_matches_a_python_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.wma(ohlcv.close, period=period)

    assert np.isnan(result[: period - 1]).all()
    assert np.isfinite(result[period - 1 :]).all()
    np.testing.assert_allclose(result, reference_wma(ohlcv.close, period), rtol=1e-12)


def test_period_one_returns_the_input(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.wma(ohlcv.close, period=1), ohlcv.close)


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.wma(ohlcv.close), pyta.wma(ohlcv.close, period=30))


def test_period_equal_to_length_gives_one_value() -> None:
    result = pyta.wma([1.0, 2.0, 6.0], period=3)

    assert np.isnan(result[:2]).all()
    assert result[2] == pytest.approx(23.0 / 6.0, rel=1e-15)


def test_flat_prices_stay_flat() -> None:
    assert (pyta.wma(np.full(400, 7.5), period=10)[9:] == 7.5).all()


def test_long_series_matches_the_direct_weighted_sum() -> None:
    # 100,000 rows of a random walk: the running sums are rebuilt every
    # 8 * period rows, so they never drift from the window's own sum.
    rng = np.random.default_rng(7)
    prices = 100.0 + np.cumsum(rng.uniform(-1.0, 1.0, 100_000))
    period = 25

    result = pyta.wma(prices, period=period)

    windows = np.lib.stride_tricks.sliding_window_view(prices, period)
    weights = np.arange(1.0, period + 1.0)
    expected = windows @ weights / weights.sum()
    scale = np.abs(windows).max(axis=1)
    assert (np.abs(result[period - 1 :] - expected) <= 1e-9 * np.maximum(scale, 1.0)).all()


def test_needs_at_least_period_values() -> None:
    with pytest.raises(ValueError, match=r"period \(10\) exceeds the series length \(9\)"):
        pyta.wma(np.ones(9), period=10)


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
        pyta.wma([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="wma uses one column"):
        pyta.wma({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.wma([1.0, 2.0, np.inf, 4.0], period=2)


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.wma(ohlcv.close, period=10)

    as_list = pyta.wma(ohlcv.close.tolist(), period=10)
    as_dict = pyta.wma(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.wma(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["wma"]
    np.testing.assert_array_equal(as_dict["wma"], want)
    assert list(as_json) == ["wma"]
    assert as_json["wma"][:9] == [None] * 9


def test_title_case_input_gives_title_case_output(ohlcv: Ohlcv) -> None:
    result = pyta.wma({"Close": ohlcv.close.tolist()}, period=10)

    assert list(result) == ["WMA"]


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_wma(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.wma(series, period=10)

    assert result.name == "wma"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.wma(ohlcv.close, period=10))


def test_output_converts_the_container(ohlcv: Ohlcv) -> None:
    result = pyta.wma(ohlcv.close.tolist(), period=10, output="dict")

    assert list(result) == ["wma"]
    np.testing.assert_array_equal(result["wma"], pyta.wma(ohlcv.close, period=10))


def test_wma_of_an_sma_chains(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=20)

    chained = pyta.wma(sma, period=10)

    # The SMA's 19 warm-up NaN are skipped; the WMA adds its own 9.
    assert np.isnan(chained[:28]).all()
    np.testing.assert_array_equal(chained[19:], pyta.wma(sma[19:], period=10))


def test_batch_isolates_a_failing_dataset(ohlcv: Ohlcv) -> None:
    results = pyta.batch.wma([ohlcv.close.tolist(), [1.0, 2.0]], period=5)

    np.testing.assert_array_equal(results[0], pyta.wma(ohlcv.close, period=5))
    assert isinstance(results[1], ValueError)
