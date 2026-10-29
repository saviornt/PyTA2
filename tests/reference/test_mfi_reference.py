"""MFI against TA-Lib 0.8.3's own output (`talib.MFI`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["mfi_14_talib.csv", "mfi_14_edge_talib.csv"]


@pytest.mark.parametrize("name", FIXTURES)
def test_mfi_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.mfi(reference.columns, period=reference.period)["mfi"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # TA-Lib's own sums, resets and divisions in its order, so every double matches exactly.
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("name", FIXTURES)
def test_mfi_warm_up_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low", "close", "volume"))

    result = np.asarray(pyta.mfi(columns, period=reference.period))

    assert np.array_equal(np.isnan(result), np.isnan(reference.expected))


def test_mfi_flat_window_with_volume_is_zero() -> None:
    reference = load("mfi_14_edge_talib.csv")
    result = np.asarray(pyta.mfi(reference.columns, period=14)["mfi"])

    # The edge series holds a flat stretch with volume: TA-Lib 0.8.3 gives 0.
    assert (result[np.flatnonzero(reference.expected == 0.0)] == 0.0).all()
    assert (reference.expected == 0.0).any()


def test_batch_mfi_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]  # both period 14

    results = pyta.batch.mfi([reference.columns for reference in references], 14)

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_array_equal(result["mfi"], reference.expected)
