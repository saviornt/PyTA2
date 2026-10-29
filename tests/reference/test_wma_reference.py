"""WMA against TA-Lib's own output (`talib.WMA`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["wma_10_talib.csv", "wma_30_talib.csv", "wma_30_edge_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_wma_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.wma(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_wma_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.batch.wma({"close": {"close": reference.input}}, reference.period)["close"]

    np.testing.assert_allclose(
        result["wma"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
