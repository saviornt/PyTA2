"""Ultimate Oscillator against TA-Lib 0.8.3's own output (`talib.ULTOSC`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["ultosc_7_14_28_talib.csv", "ultosc_7_14_28_edge_talib.csv"]


def windows(name: str) -> tuple[int, int, int]:
    parameters = load(name).parameters
    return int(parameters["short"]), int(parameters["medium"]), int(parameters["long"])


@pytest.mark.parametrize("name", FIXTURES)
def test_ultosc_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.ultosc(reference.columns, *windows(name))["ultosc"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib's own sums, resets and weighting in its order, so every double matches exactly.
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("name", FIXTURES)
def test_ultosc_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low", "close"))

    result = np.asarray(pyta.ultosc(columns, *windows(name)))

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_ultosc_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both 7, 14, 28

    results = pyta.batch.ultosc([reference.columns for reference in references], 7, 14, 28)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_array_equal(result["ultosc"], reference.expected)
