"""TRIX against TA-Lib 0.8.3's own output (`talib.TRIX`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["trix_30_talib.csv", "trix_15_talib.csv", "trix_30_edge_talib.csv"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_trix_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.trix(reference.input, period=reference.period)

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib 0.8.3 fuses its EMA update (`fma`); PyTA's differs in the last
    # bits of the EMAs, so TRIX agrees to about 4e-13 relative, not exactly.
    np.testing.assert_allclose(result, reference.expected, rtol=1e-12, atol=1e-15, equal_nan=True)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_trix_warm_up_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.trix(reference.input, period=reference.period)

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_batch_trix_matches_ta_lib() -> None:
    references = [load(name) for name in FIXTURES if "_30_" in name]

    results = pyta.batch.trix([reference.input for reference in references], 30)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_allclose(
            result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
        )
