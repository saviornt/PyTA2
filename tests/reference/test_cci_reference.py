"""CCI against the published StockCharts ChartSchool CCI-20 example, via the public API."""

import numpy as np
import pyta
from reference_data import load


def test_cci_matches_the_published_example() -> None:
    reference = load("cci_20_stockcharts.csv")

    result = pyta.cci(reference.columns, period=reference.period)["cci_20"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )


def test_cci_warm_up_matches_the_published_example() -> None:
    reference = load("cci_20_stockcharts.csv")
    columns = tuple(reference.columns[name] for name in ("high", "low", "close"))

    result = np.asarray(pyta.cci(columns, period=reference.period))

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_cci_matches_the_published_example() -> None:
    reference = load("cci_20_stockcharts.csv")

    (result,) = pyta.batch.cci([reference.columns, reference.columns], reference.period)[:1]

    np.testing.assert_allclose(
        result["cci_20"], reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )
