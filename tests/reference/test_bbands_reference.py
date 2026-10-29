"""Bollinger Bands against TA-Lib 0.8.3's own output (generated fixtures), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import Reference, load

FIXTURES = ["bbands_20_2_talib.csv", "bbands_20_2_edge_talib.csv"]
NAMES = ["bbands_upper", "bbands_middle", "bbands_lower"]


def _bbands(reference: Reference) -> tuple[list[float], list[float], list[float]]:
    return pyta.bbands(
        reference.input.tolist(), period=reference.period, k=reference.parameters["k"]
    )


@pytest.mark.parametrize("name", FIXTURES)
def test_bbands_matches_talib(name: str) -> None:
    reference = load(name)

    result = _bbands(reference)

    assert list(reference.outputs) == NAMES
    for got, want in zip(result, reference.outputs.values(), strict=True):
        np.testing.assert_allclose(
            np.asarray(got), want, rtol=reference.tolerance, atol=0, equal_nan=True
        )
        assert np.array_equal(np.isnan(got), np.isnan(want))


def test_the_edge_series_has_three_equal_bands_on_its_flat_stretch() -> None:
    reference = load("bbands_20_2_edge_talib.csv")
    upper, middle, lower = (np.asarray(band) for band in _bbands(reference))
    flat = reference.outputs["bbands_upper"] == reference.outputs["bbands_lower"]

    assert flat.any()
    assert (upper[flat] == 105.0).all()
    assert (middle[flat] == 105.0).all()
    assert (lower[flat] == 105.0).all()


def test_batch_bbands_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 20, k 2.0

    results = pyta.batch.bbands([{"close": reference.input} for reference in references], 20, 2.0)

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
