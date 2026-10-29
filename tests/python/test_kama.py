"""KAMA numerics, containers and errors through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

SLOWEST = 2.0 / 31.0
FASTEST = 2.0 / 3.0


def reference_kama(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """KAMA by its definition (TA-Lib's seed and ratio rules), each window summed afresh."""
    out = np.full(prices.shape[0], np.nan)
    previous = prices[period - 1]
    for i in range(period, prices.shape[0]):
        total = float(np.abs(np.diff(prices[i - period : i + 1])).sum())
        net = prices[i] - prices[i - period]
        ratio = 1.0 if total <= 0.0 or total <= net else min(abs(net / total), 1.0)
        constant = (ratio * (FASTEST - SLOWEST) + SLOWEST) ** 2
        previous += constant * (prices[i] - previous)
        out[i] = previous
    return out


def test_known_value() -> None:
    # Period 2 on 1, 2, 4: ER = 1, SC = (2/3) ** 2, seeded with 2.
    result = pyta.kama([1.0, 2.0, 4.0], period=2)

    assert np.isnan(result[:2]).all()
    assert result[2] == pytest.approx(2.0 + 8.0 / 9.0, rel=1e-15)


def test_choppy_prices_move_at_the_slowest_rate() -> None:
    # Alternating prices: zero net change over an even period, so ER = 0.
    prices = [10.0, 11.0] * 5

    result = pyta.kama(prices, period=4)

    assert result[4] == pytest.approx(11.0 - SLOWEST**2, rel=1e-15)


@pytest.mark.parametrize("period", [2, 10, 30, 90])
def test_matches_a_python_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.kama(ohlcv.close, period=period)

    assert np.isnan(result[:period]).all()
    assert np.isfinite(result[period:]).all()
    np.testing.assert_allclose(result, reference_kama(ohlcv.close, period), rtol=1e-12)


def test_period_one_returns_the_input(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.kama(ohlcv.close, period=1), ohlcv.close)


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.kama(ohlcv.close), pyta.kama(ohlcv.close, period=30))


def test_minimum_length_gives_one_value() -> None:
    result = pyta.kama(np.arange(1.0, 5.0), period=3)

    assert np.isnan(result[:3]).all()
    assert np.isfinite(result[3])


def test_flat_prices_stay_flat() -> None:
    assert (pyta.kama(np.full(400, 7.5), period=10)[10:] == 7.5).all()


def test_flat_stretch_after_movement_matches_the_definition() -> None:
    # Inexact changes, then a flat stretch longer than the period (the
    # rolling sum is reset there), then movement again.
    prices = np.concatenate(
        [100.0 + np.sin(np.arange(40) * 0.7) * 3.1, np.full(25, 103.3), np.arange(30) * 0.13]
    )

    result = pyta.kama(prices, period=10)

    np.testing.assert_allclose(result, reference_kama(prices, 10), rtol=1e-12)


def test_needs_one_more_value_than_its_period() -> None:
    with pytest.raises(ValueError, match="at least 11 values are required, got 10"):
        pyta.kama(np.ones(10), period=10)


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
        pyta.kama([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_largest_period_reports_its_requirement() -> None:
    with pytest.raises(ValueError, match="at least 2147483648 values are required, got 3"):
        pyta.kama([1.0, 2.0, 3.0], period=2**31 - 1)


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="kama uses one column"):
        pyta.kama({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.kama([1.0, 2.0, np.inf, 4.0], period=2)


def test_containers_and_name(ohlcv: Ohlcv) -> None:
    want = pyta.kama(ohlcv.close, period=10)

    as_list = pyta.kama(ohlcv.close.tolist(), period=10)
    as_dict = pyta.kama(ohlcv.columns(), period=10)
    as_json = json.loads(pyta.kama(json.dumps(ohlcv.lists()), period=10))

    assert isinstance(as_list, list)
    np.testing.assert_array_equal(as_list, want)
    assert list(as_dict) == ["kama"]
    np.testing.assert_array_equal(as_dict["kama"], want)
    assert list(as_json) == ["kama"]
    assert as_json["kama"][:10] == [None] * 10


def test_title_case_input_gives_title_case_output(ohlcv: Ohlcv) -> None:
    result = pyta.kama({"Close": ohlcv.close.tolist()}, period=10)

    assert list(result) == ["KAMA"]


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named_kama(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates), name="close")

    result = pyta.kama(series, period=10)

    assert result.name == "kama"
    assert result.index.equals(series.index)
    np.testing.assert_array_equal(result, pyta.kama(ohlcv.close, period=10))


def test_output_converts_the_container(ohlcv: Ohlcv) -> None:
    result = pyta.kama(ohlcv.close.tolist(), period=10, output="dict")

    assert list(result) == ["kama"]
    np.testing.assert_array_equal(result["kama"], pyta.kama(ohlcv.close, period=10))


def test_kama_of_a_tema_chains(ohlcv: Ohlcv) -> None:
    tema = pyta.tema(ohlcv.close, period=5)

    chained = pyta.kama(tema, period=10)

    # The TEMA's 12 warm-up NaN are skipped; the KAMA adds its own 10.
    assert np.isnan(chained[:22]).all()
    np.testing.assert_array_equal(chained[12:], pyta.kama(tema[12:], period=10))


def test_batch_isolates_a_failing_dataset(ohlcv: Ohlcv) -> None:
    results = pyta.batch.kama([ohlcv.close.tolist(), [1.0, 2.0]], period=5)

    np.testing.assert_array_equal(results[0], pyta.kama(ohlcv.close, period=5))
    assert isinstance(results[1], ValueError)
