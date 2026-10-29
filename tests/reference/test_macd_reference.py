"""MACD against TA-Lib's own output (`talib.MACD`), via the public API.

Where TA-Lib blanks `macd` until the signal exists, the fixture's `macd` column
comes from TA-Lib with `signalperiod=1`, so every output is checked with its
own warm-up.
"""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["macd_12_26_9_talib.csv", "macd_5_35_5_talib.csv"]
NAMES = ["macd", "macd_signal", "macd_hist"]


def _parameters(fixture: str) -> tuple[int, int, int]:
    parameters = load(fixture).parameters
    return int(parameters["fast"]), int(parameters["slow"]), int(parameters["signal"])


@pytest.mark.parametrize("fixture", FIXTURES)
def test_macd_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    result = pyta.macd(reference.input, *_parameters(fixture))

    assert list(reference.outputs) == NAMES
    for got, want in zip(result, reference.outputs.values(), strict=True):
        np.testing.assert_allclose(got, want, rtol=0, atol=reference.tolerance, equal_nan=True)
        assert np.array_equal(np.isnan(got), np.isnan(want))


@pytest.mark.parametrize("fixture", FIXTURES)
def test_batch_macd_matches_ta_lib(fixture: str) -> None:
    reference = load(fixture)

    (result,) = pyta.batch.macd([{"close": reference.input}], *_parameters(fixture))

    assert list(result) == NAMES
    for name in NAMES:
        np.testing.assert_allclose(
            result[name],
            reference.outputs[name],
            rtol=0,
            atol=reference.tolerance,
            equal_nan=True,
        )
