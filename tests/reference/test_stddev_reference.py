"""STDDEV against TA-Lib 0.8.3's own output (generated fixtures), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import Reference, load

FIXTURES = ["stddev_5_1_talib.csv", "stddev_20_2_talib.csv", "stddev_5_1_edge_talib.csv"]


def _stddev(reference: Reference) -> list[float]:
    return pyta.stddev(
        reference.input.tolist(), period=reference.period, k=reference.parameters["k"]
    )


@pytest.mark.parametrize("name", FIXTURES)
def test_stddev_matches_talib(name: str) -> None:
    reference = load(name)

    result = np.asarray(_stddev(reference))

    # Relative, with no absolute floor: TA-Lib's exact zeros must be exact here too.
    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_the_edge_series_has_exact_zeros_on_its_flat_stretch() -> None:
    reference = load("stddev_5_1_edge_talib.csv")
    zeros = reference.expected == 0.0

    assert zeros.any()
    assert (np.asarray(_stddev(reference))[zeros] == 0.0).all()


def test_batch_stddev_matches_talib() -> None:
    references = [load(name) for name in FIXTURES[::2]]  # both period 5, k 1.0

    results = pyta.batch.stddev([{"close": reference.input} for reference in references], 5, 1.0)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_allclose(
            result["stddev"], reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
        )
