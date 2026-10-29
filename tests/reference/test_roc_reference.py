"""ROC against TA-Lib 0.8.3's own output (`talib.ROC`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["roc_10_talib.csv", "roc_10_edge_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_roc_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.roc(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib's own expression, so every double matches exactly (the edge
    # series' zero base included).
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_roc_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.batch.roc({"close": {"close": reference.input}}, reference.period)["close"]

    np.testing.assert_allclose(
        result["roc"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
