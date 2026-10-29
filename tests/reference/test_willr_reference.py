"""Williams %R against TA-Lib 0.8.3's own output (`talib.WILLR`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["willr_14_talib.csv", "willr_14_edge_talib.csv"]


@pytest.mark.parametrize("name", FIXTURES)
def test_willr_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.willr(reference.columns, period=reference.period)["willr"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib's own expressions, so every double matches exactly.
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("name", FIXTURES)
def test_willr_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low", "close"))

    result = np.asarray(pyta.willr(columns, period=reference.period))

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_willr_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 14

    results = pyta.batch.willr([reference.columns for reference in references], 14)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_allclose(
            result["willr"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
        )
