"""Parabolic SAR against TA-Lib 0.8.3's own output (`talib.SAR`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import Reference, load

FIXTURES = ["sar_0.02_0.2_talib.csv", "sar_0.01_0.1_talib.csv", "sar_0.02_0.2_edge_talib.csv"]


def _parameters(reference: Reference) -> tuple[float, float]:
    return float(reference.parameters["acceleration"]), float(reference.parameters["maximum"])


@pytest.mark.parametrize("fixture", FIXTURES)
def test_sar_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.sar(reference.columns, *_parameters(reference))

    np.testing.assert_allclose(
        result["sar"],
        reference.expected,
        rtol=reference.tolerance,
        atol=0,
        equal_nan=True,
    )
    assert np.array_equal(np.isnan(result["sar"]), np.isnan(reference.expected))


def test_batch_sar_matches_ta_lib() -> None:
    references = [load(name) for name in FIXTURES]

    for reference in references:
        (result,) = pyta.batch.sar([reference.columns], *_parameters(reference))

        np.testing.assert_allclose(
            result["sar"],
            reference.expected,
            rtol=reference.tolerance,
            atol=0,
            equal_nan=True,
        )
