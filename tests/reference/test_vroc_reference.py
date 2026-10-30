"""Volume ROC against TA-Lib 0.8.3's own output (`talib.ROC` of volume), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["vroc_10_talib.csv", "vroc_10_edge_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_vroc_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.vroc(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib's own expression, so every double matches exactly (zero bases included).
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_vroc_picks_the_volume_column_and_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)
    data = {"close": np.ones_like(reference.input), "Volume": reference.input}

    result = pyta.vroc(data, reference.period)["VROC"]

    np.testing.assert_array_equal(result, reference.expected)


def test_batch_vroc_matches_ta_lib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 10

    results = pyta.batch.vroc([reference.input for reference in references], 10)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_array_equal(result, reference.expected)
