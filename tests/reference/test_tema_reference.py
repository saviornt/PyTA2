"""TEMA against TA-Lib's own output (`talib.TEMA`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["tema_30_talib.csv", "tema_30_edge_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_tema_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.tema(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_tema_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.batch.tema({"close": {"close": reference.input}}, reference.period)["close"]

    np.testing.assert_allclose(
        result["tema"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
