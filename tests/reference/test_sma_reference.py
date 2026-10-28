"""SMA against published worked examples (StockCharts ChartSchool), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load


@pytest.mark.parametrize("name", ["sma_5_stockcharts.csv", "sma_10_stockcharts.csv"])
def test_sma_matches_the_published_example(name: str) -> None:
    reference = load(name)

    result = pyta.sma(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )


def test_sma_warm_up_matches_the_published_example() -> None:
    reference = load("sma_10_stockcharts.csv")

    result = pyta.sma(reference.input, period=reference.period)

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_sma_matches_the_published_examples() -> None:
    names = ["sma_5_stockcharts.csv", "sma_10_stockcharts.csv"]
    references = [load(name) for name in names]

    for reference in references:
        (result,) = pyta.batch.sma([reference.input], period=reference.period)
        np.testing.assert_allclose(
            result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
        )
