"""VWAP against a hand calculation, via the public API.

TA-Lib has no VWAP, so the checks are the hand-computed table in
`tests/fixtures/vwap_hand.csv` (derivation in its comments: leading rows
without volume, a row without volume later, and a one-price bar) and, on the
SPY fixture, a cumulative sum computed independently of PyTA.
"""

import numpy as np
import pyta
from ohlcv_data import load as load_ohlcv
from reference_data import load

FIXTURE = "vwap_hand.csv"


def test_vwap_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    result = pyta.vwap(reference.columns)["vwap"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=reference.tolerance, atol=0, equal_nan=True
    )
    # Rows 0 and 1 have no volume yet.
    assert np.isnan(result[:2]).all()


def test_batch_vwap_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    (result,) = pyta.batch.vwap([reference.columns])

    np.testing.assert_allclose(
        result["vwap"],
        reference.expected,
        rtol=reference.tolerance,
        atol=0,
        equal_nan=True,
    )


def test_vwap_matches_a_cumulative_sum_on_spy() -> None:
    ohlcv = load_ohlcv()
    typical = (ohlcv.high + ohlcv.low + ohlcv.close) / 3.0
    expected = np.cumsum(typical * ohlcv.volume) / np.cumsum(ohlcv.volume)

    result = np.asarray(pyta.vwap(ohlcv.columns())["vwap"])

    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=0)
