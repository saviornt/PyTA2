"""Accumulation/Distribution against TA-Lib 0.8.3's own output (`talib.AD`), via the public API."""

import numpy as np
import pyta
import pytest
from reference_data import load

FIXTURES = ["ad_talib.csv", "ad_edge_talib.csv"]


@pytest.mark.parametrize("name", FIXTURES)
def test_ad_matches_talib(name: str) -> None:
    reference = load(name)

    result = pyta.ad(reference.columns)["ad"]

    # Totals reach 1e10, so the fixture's tolerance is relative.
    np.testing.assert_allclose(result, reference.expected, rtol=reference.tolerance, atol=0)
    # TA-Lib's operations in its order, so every double matches exactly.
    np.testing.assert_array_equal(result, reference.expected)


@pytest.mark.parametrize("name", FIXTURES)
def test_unnamed_ad_matches_talib(name: str) -> None:
    reference = load(name)
    columns = tuple(reference.columns[role] for role in ("high", "low", "close", "volume"))

    np.testing.assert_array_equal(pyta.ad(columns), reference.expected)


def test_edge_series_one_price_bar_adds_nothing() -> None:
    reference = load("ad_edge_talib.csv")
    result = np.asarray(pyta.ad(reference.columns)["ad"])

    # Row 80 is a one-price bar (high == low): A/D carries the previous total.
    assert reference.columns["high"][80] == reference.columns["low"][80]
    assert result[80] == result[79]


def test_batch_ad_matches_talib() -> None:
    references = [load(name) for name in FIXTURES]

    results = pyta.batch.ad([reference.columns for reference in references])

    for reference, result in zip(references, results, strict=True):
        np.testing.assert_array_equal(result["ad"], reference.expected)
