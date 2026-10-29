"""ADX, +DI and -DI against TA-Lib's own output (`talib.ADX`, `PLUS_DI`, `MINUS_DI`), via the
public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["adx_14_talib.csv", "adx_14_edge_talib.csv"]
NAMES = ["adx", "adx_plus_di", "adx_minus_di"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_adx_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.adx(reference.columns, period=reference.period)

    assert list(reference.outputs) == NAMES
    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )
        assert np.array_equal(np.isnan(result[name]), np.isnan(reference.outputs[name]))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_adx_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    (result,) = pyta.batch.adx([reference.columns], reference.period)

    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )
