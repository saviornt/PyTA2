"""Stochastic Oscillator against TA-Lib's own output (`talib.STOCH` with SMA), via the public
API."""

import numpy as np
import pyta
import pytest
from reference_data import Reference, load

FIXTURES = ["stoch_14_3_3_talib.csv", "stoch_5_3_3_talib.csv", "stoch_14_3_3_edge_talib.csv"]
NAMES = ["stoch_k", "stoch_d"]


def _parameters(reference: Reference) -> tuple[int, int, int]:
    parameters = reference.parameters
    return int(parameters["k"]), int(parameters["k_smooth"]), int(parameters["d"])


@pytest.mark.parametrize("fixture", FIXTURES)
def test_stoch_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.stoch(reference.columns, *_parameters(reference))

    assert list(reference.outputs) == NAMES
    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )
        assert np.array_equal(np.isnan(result[name]), np.isnan(reference.outputs[name]))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_stoch_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    (result,) = pyta.batch.stoch([reference.columns], *_parameters(reference))

    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )
