"""Chaikin Money Flow against a hand calculation, via the public API.

TA-Lib has no CMF, so the checks are the hand-computed table in
`tests/fixtures/cmf_hand.csv` (derivation in its comments: a one-price bar and
a window without volume included) and, on the SPY fixture, fresh sums over
every window computed independently of PyTA.
"""

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from ohlcv_data import load as load_ohlcv
from reference_data import load

FIXTURE = "cmf_hand.csv"


def test_cmf_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    result = pyta.cmf(reference.columns, period=reference.period)["cmf"]

    np.testing.assert_allclose(
        result, reference.expected, rtol=0, atol=reference.tolerance, equal_nan=True
    )
    # Row 7's window (rows 5-7) has no volume.
    assert np.isnan(result[7])


def test_batch_cmf_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    (result,) = pyta.batch.cmf([reference.columns], reference.period)

    np.testing.assert_allclose(
        result["cmf"],
        reference.expected,
        rtol=0,
        atol=reference.tolerance,
        equal_nan=True,
    )


@pytest.mark.parametrize("period", [20, 21])
def test_cmf_matches_fresh_window_sums_on_spy(period: int) -> None:
    ohlcv = load_ohlcv()
    high, low, close, volume = ohlcv.high, ohlcv.low, ohlcv.close, ohlcv.volume
    multiplier = ((close - low) - (high - close)) / (high - low)  # no one-price bar in SPY
    flow = sliding_window_view(multiplier * volume, period).sum(axis=1)
    total = sliding_window_view(volume, period).sum(axis=1)

    result = np.asarray(pyta.cmf(ohlcv.columns(), period)["cmf"])

    assert (high > low).all()
    assert np.isnan(result[: period - 1]).all()
    np.testing.assert_allclose(result[period - 1 :], flow / total, rtol=0, atol=1e-12)
