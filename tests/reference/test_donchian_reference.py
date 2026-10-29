"""Donchian Channels against TA-Lib 0.8.3's MAX(high) and MIN(low), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["donchian_20_talib.csv", "donchian_20_edge_talib.csv"]
NAMES = ["donchian_upper", "donchian_middle", "donchian_lower"]


@pytest.mark.parametrize("name", FIXTURES)
def test_donchian_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.donchian(reference.columns, period=reference.period)

    assert list(reference.outputs) == NAMES
    for output in NAMES:
        np.testing.assert_allclose(
            result[output],
            reference.outputs[output],
            rtol=reference.tolerance,
            atol=0,
            equal_nan=True,
        )
    # Upper and lower are copied input values, so they match TA-Lib exactly.
    np.testing.assert_array_equal(result["donchian_upper"], reference.outputs["donchian_upper"])
    np.testing.assert_array_equal(result["donchian_lower"], reference.outputs["donchian_lower"])


@pytest.mark.parametrize("name", FIXTURES)
def test_donchian_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low"))

    for got, want in zip(
        pyta.donchian(columns, period=reference.period), reference.outputs.values(), strict=True
    ):
        assert np.array_equal(np.isnan(got), np.isnan(want))


def test_batch_donchian_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 20

    results = pyta.batch.donchian([reference.columns for reference in references], 20)

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
