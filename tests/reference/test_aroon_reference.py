"""Aroon against TA-Lib 0.8.3's own output (`talib.AROON`, `talib.AROONOSC`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["aroon_14_talib.csv", "aroon_14_edge_talib.csv"]
NAMES = ["aroon_up", "aroon_down", "aroon_osc"]


@pytest.mark.parametrize("name", FIXTURES)
def test_aroon_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.aroon(reference.columns, period=reference.period)

    assert list(reference.outputs) == NAMES
    for output in NAMES:
        np.testing.assert_allclose(
            result[output],
            reference.outputs[output],
            rtol=reference.tolerance,
            atol=0,
            equal_nan=True,
        )
        # TA-Lib's own expressions, so every double matches exactly.
        np.testing.assert_array_equal(result[output], reference.outputs[output])


@pytest.mark.parametrize("name", FIXTURES)
def test_aroon_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low"))

    for got, want in zip(
        pyta.aroon(columns, period=reference.period), reference.outputs.values(), strict=True
    ):
        assert np.array_equal(np.isnan(got), np.isnan(want))


def test_batch_aroon_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 14

    results = pyta.batch.aroon([reference.columns for reference in references], 14)

    for reference, result in zip(references, results, strict=True):
        assert list(result) == NAMES
        for name in NAMES:
            np.testing.assert_allclose(
                result[name],
                reference.outputs[name],
                rtol=reference.tolerance,
                atol=0,
                equal_nan=True,
            )
