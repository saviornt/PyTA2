"""ROC numerics, containers and errors through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_roc(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TA-Lib's ROC written out with NumPy: (price / earlier - 1) * 100, 0 on a scaled-zero base."""
    out = np.full(prices.shape[0], np.nan)
    earlier = prices[:-period]
    with np.errstate(divide="ignore", invalid="ignore"):
        zero = np.abs(earlier) <= 1e-14 * np.abs(prices[period:])
        out[period:] = np.where(zero, 0.0, (prices[period:] / earlier - 1.0) * 100.0)
    return out


def test_known_values() -> None:
    # Period 2: 12 against 10 is +20%, 9 against 11 about -18.18%, 15 against 12 +25%.
    result = pyta.roc(np.array([10.0, 11.0, 12.0, 9.0, 15.0]), period=2)

    assert np.isnan(result[:2]).all()
    np.testing.assert_array_equal(
        result[2:], [(12 / 10 - 1) * 100, (9 / 11 - 1) * 100, (15 / 12 - 1) * 100]
    )


@pytest.mark.parametrize("period", [1, 10, 12, 50, 200])
def test_matches_a_numpy_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.roc(ohlcv.close, period=period)

    assert np.isnan(result[:period]).all()
    assert np.isfinite(result[period:]).all()
    # The same IEEE operations in the same order, so the doubles are equal.
    np.testing.assert_array_equal(result, reference_roc(ohlcv.close, period))


def test_default_period_is_ten(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.roc(ohlcv.close), pyta.roc(ohlcv.close, period=10))


def test_zero_base_gives_zero_and_flat_prices_give_zero() -> None:
    # An earlier value of exactly 0 gives 0, not an infinity (as TA-Lib).
    assert pyta.roc([0.0, 5.0, 5.0, 0.0, 5.0], period=1)[1:] == [0.0, 0.0, -100.0, 0.0]
    assert (pyta.roc(np.full(20, 7.5), period=5)[5:] == 0.0).all()


def test_a_tiny_base_gives_zero_where_talib_gives_infinity() -> None:
    # |earlier| <= 1e-14 * |current| counts as zero, so every output is finite.
    result = pyta.roc(np.array([1e-300, 1e10, 1e-300, 1.0, 1e-14, 1.0, 2e-14, 1.0]), period=1)

    assert np.isfinite(result[1:]).all()
    assert list(result[[1, 3, 5]]) == [0.0, 0.0, 0.0]
    # Just above the scaled zero the ratio is written.
    assert result[7] == (1.0 / 2e-14 - 1.0) * 100.0


def test_needs_period_plus_one_values() -> None:
    with pytest.raises(ValueError, match="at least 11 values are required, got 10"):
        pyta.roc(np.ones(10), period=10)

    assert pyta.roc(np.ones(11), period=10)[10] == 0.0


@pytest.mark.parametrize(
    ("period", "error", "message"),
    [
        (0, ValueError, "period must be between 1 and 2147483647, got 0"),
        (-3, ValueError, "period must be between 1 and 2147483647, got -3"),
        (2**31, ValueError, "period must be between 1 and 2147483647, got 2147483648"),
        (2.5, TypeError, "period must be an integer, got float"),
        (True, TypeError, "period must be an integer, not bool"),
    ],
)
def test_invalid_period(period: object, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        pyta.roc([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="roc uses one column"):
        pyta.roc({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.roc([1.0, 2.0, np.inf, 4.0], period=1)


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.roc(ohlcv.close, period=10)

    as_list = pyta.roc(ohlcv.close.tolist(), period=10)
    as_dict = pyta.roc(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.roc(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["roc"]
    np.testing.assert_array_equal(as_dict["roc"], want)
    assert list(as_json) == ["roc"]
    assert as_json["roc"][:10] == [None] * 10


def test_column_selects_another_series(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.roc(ohlcv.columns(), period=5, column="open")["roc"], pyta.roc(ohlcv.open, period=5)
    )


def test_title_case_input_gives_title_case_output(ohlcv: Ohlcv) -> None:
    result = pyta.roc({"Close": ohlcv.close.tolist()}, period=10)

    assert list(result) == ["ROC"]


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_roc(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.roc(series, period=10)

    assert result.name == "roc"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.roc(ohlcv.close, period=10))


def test_output_converts_the_container(ohlcv: Ohlcv) -> None:
    result = pyta.roc(ohlcv.close.tolist(), period=10, output="dict")

    assert list(result) == ["roc"]
    np.testing.assert_array_equal(result["roc"], pyta.roc(ohlcv.close, period=10))


def test_roc_of_an_sma_chains(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=20)

    chained = pyta.roc(sma, period=10)

    # The SMA's 19 warm-up NaN are skipped; the ROC adds its own 10.
    assert np.isnan(chained[:29]).all()
    np.testing.assert_array_equal(chained[19:], pyta.roc(sma[19:], period=10))


def test_batch_isolates_a_failing_dataset(ohlcv: Ohlcv) -> None:
    results = pyta.batch.roc([ohlcv.close.tolist(), [1.0, 2.0]], period=5)

    np.testing.assert_array_equal(results[0], pyta.roc(ohlcv.close, period=5))
    assert isinstance(results[1], ValueError)
    assert "at least 6 values are required, got 2" in str(results[1])


def test_batch_by_category_with_a_mapping(ohlcv: Ohlcv) -> None:
    results = pyta.batch.momentum.roc({"b": [1.0, 2.0, 4.0], "a": ohlcv.close}, 1)

    assert list(results) == ["b", "a"]
    assert results["b"][1:] == [100.0, 100.0]
