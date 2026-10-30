"""OBV against TA-Lib 0.8.3's own output (`talib.OBV`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["obv_talib.csv", "obv_edge_talib.csv"]


@pytest.mark.parametrize("name", FIXTURES)
def test_obv_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.obv(reference.columns)["obv"]

    np.testing.assert_allclose(result, reference.expected, rtol=reference.tolerance, atol=0)
    # Sums of whole volumes are exact, so every double matches.
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("name", FIXTURES)
def test_unnamed_obv_matches_talib(name: str) -> None:
    reference = load(name)
    columns = (reference.columns["close"], reference.columns["volume"])

    np.testing.assert_array_equal(pyta.obv(columns), reference.expected)


def test_batch_obv_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]

    results = pyta.batch.obv([reference.columns for reference in references])

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_array_equal(result["obv"], reference.expected)
