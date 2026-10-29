"""ATR against TA-Lib 0.8.3's own output (generated fixtures), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["atr_14_talib.csv", "atr_14_edge_talib.csv"]


@pytest.mark.parametrize("name", FIXTURES)
def test_atr_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.atr(reference.columns, period=reference.period)["atr"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )


@pytest.mark.parametrize("name", FIXTURES)
def test_atr_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[name] for name in ("high", "low", "close"))

    result = np.asarray(pyta.atr(columns, period=reference.period))

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_atr_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]

    results = pyta.batch.atr([reference.columns for reference in references], 14)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_allclose(
            result["atr"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
        )
