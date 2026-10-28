"""RSI against the published StockCharts ChartSchool RSI-14 example, via the public API."""

import numpy as np
import pyta
from reference_data import load


def test_rsi_matches_the_published_example() -> None:
    reference = load("rsi_14_stockcharts.csv")

    result = pyta.rsi(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )


def test_rsi_warm_up_matches_the_published_example() -> None:
    reference = load("rsi_14_stockcharts.csv")

    result = pyta.rsi(reference.input, period=reference.period)

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_rsi_matches_the_published_example() -> None:
    reference = load("rsi_14_stockcharts.csv")

    (result,) = pyta.batch.rsi([reference.input, reference.input], period=reference.period)[:1]

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )
