"""STDDEV numerics, parameters and errors through the public API."""

import math

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv


def _two_pass(values: np.ndarray, period: int) -> np.ndarray:
    """Exact-as-possible population deviation of each window: centred, two passes."""
    windows = np.lib.stride_tricks.sliding_window_view(values, period)
    means = windows.mean(axis=1, keepdims=True)
    return np.sqrt(((windows - means) ** 2).mean(axis=1))


def test_known_values() -> None:
    # Windows of 2: half of each gap (1, 2, 0.5), times k = 2.
    result = pyta.stddev([1.0, 3.0, 7.0, 8.0], period=2, k=2.0)

    assert math.isnan(result[0])
    assert result[1:] == [2.0, 4.0, 1.0]


def test_is_the_population_deviation() -> None:
    values = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])

    result = pyta.stddev(values, period=8)

    assert result[-1] == 2.0  # sqrt(32 / 8); the sample deviation would be sqrt(32 / 7)
    assert result[-1] == pytest.approx(np.std(values))


def test_defaults_are_period_five_and_k_one(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.stddev(ohlcv.close), pyta.stddev(ohlcv.close, period=5, k=1.0)
    )


@pytest.mark.parametrize("period", [2, 5, 20, 200])
def test_matches_numpy_on_real_closes(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.stddev(ohlcv.close, period=period)

    assert np.isnan(result[: period - 1]).all()
    np.testing.assert_allclose(result[period - 1 :], _two_pass(ohlcv.close, period), rtol=1e-12)


def test_k_scales_the_result(ohlcv: Ohlcv) -> None:
    one = pyta.stddev(ohlcv.close, period=20)

    np.testing.assert_array_equal(pyta.stddev(ohlcv.close, period=20, k=2.5), one * 2.5)
    np.testing.assert_array_equal(pyta.stddev(ohlcv.close, period=20, k=2), one * 2.0)


def test_flat_prices_give_exactly_zero() -> None:
    result = pyta.stddev(np.full(30, 101.37), period=7)

    assert (result[6:] == 0.0).all()


def test_large_offset_with_a_small_spread_keeps_its_precision() -> None:
    # 1e5 + 1e-3 * noise: a running sum of squares (TA-Lib's form before 0.8.3)
    # loses most of its digits here; PyTA matches a two-pass reference.
    rng = np.random.default_rng(7)
    values = 1.0e5 + 1.0e-3 * rng.standard_normal(1_000)

    for period in (5, 20, 100):
        result = pyta.stddev(values, period=period)

        np.testing.assert_allclose(result[period - 1 :], _two_pass(values, period), rtol=1e-9)


def test_needs_at_least_period_values() -> None:
    with pytest.raises(ValueError, match=r"period \(5\) exceeds the series length \(4\)"):
        pyta.stddev([1.0, 2.0, 3.0, 4.0], period=5)


@pytest.mark.parametrize("period", [0, 1, -3, 2**31])
def test_period_must_be_at_least_two(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.stddev([1.0, 2.0, 3.0], period=period)


@pytest.mark.parametrize("period", ["5", 2.5, True, None])
def test_period_must_be_an_integer(period: object) -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.stddev([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


@pytest.mark.parametrize("k", [0, 0.0, -1.0, math.inf, math.nan, -math.inf])
def test_k_must_be_a_finite_number_above_zero(k: float) -> None:
    with pytest.raises(ValueError, match="k must be a finite number greater than 0"):
        pyta.stddev([1.0, 2.0, 3.0], period=2, k=k)


@pytest.mark.parametrize("k", ["2", True, None])
def test_k_must_be_a_number(k: object) -> None:
    with pytest.raises(TypeError, match="k must be a number"):
        pyta.stddev([1.0, 2.0, 3.0], period=2, k=k)  # type: ignore[arg-type]


def test_k_accepts_numpy_numbers() -> None:
    expected = pyta.stddev([1.0, 3.0, 7.0], period=2, k=2.0)

    assert pyta.stddev([1.0, 3.0, 7.0], period=2, k=np.float64(2.0))[1:] == expected[1:]
    assert pyta.stddev([1.0, 3.0, 7.0], period=2, k=np.int64(2))[1:] == expected[1:]


def test_columns_is_rejected() -> None:
    with pytest.raises(ValueError, match="columns"):
        pyta.stddev({"close": [1.0, 2.0, 3.0]}, columns=["close"])  # type: ignore[arg-type]


def test_uses_the_close_column_and_names_the_output(ohlcv: Ohlcv) -> None:
    data = {"open": ohlcv.open, "close": ohlcv.close}

    result = pyta.stddev(data, period=10)

    assert list(result) == ["stddev"]
    np.testing.assert_array_equal(result["stddev"], pyta.stddev(ohlcv.close, period=10))
    assert list(pyta.stddev({"Close": ohlcv.close})) == ["STDDEV"]


def test_column_selects_another_role(ohlcv: Ohlcv) -> None:
    data = {"open": ohlcv.open, "close": ohlcv.close}

    result = pyta.stddev(data, period=10, column="open")

    np.testing.assert_array_equal(result["stddev"], pyta.stddev(ohlcv.open, period=10))


def test_chains_after_another_indicator(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=10)

    result = pyta.stddev(sma, period=5)

    assert np.isnan(result[:13]).all()
    np.testing.assert_allclose(result[13:], _two_pass(sma[9:], 5), rtol=1e-12)


def test_batch_matches_single_calls_and_isolates_failures(ohlcv: Ohlcv) -> None:
    datasets = {"good": ohlcv.close, "short": [1.0, 2.0]}

    results = pyta.batch.stddev(datasets, period=3, k=2.0)

    np.testing.assert_array_equal(results["good"], pyta.stddev(ohlcv.close, period=3, k=2.0))
    assert isinstance(results["short"], ValueError)


def test_batch_rejects_an_invalid_k_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="k must be"):
        pyta.batch.stddev([ohlcv.close], k=-1.0)
