"""EMA against TA-Lib's own output (`talib.EMA`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["ema_10_talib.csv", "ema_30_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_ema_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.ema(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )
    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_ema_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.batch.ema({"close": {"close": reference.input}}, reference.period)["close"]

    np.testing.assert_allclose(
        result["ema"], reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )
