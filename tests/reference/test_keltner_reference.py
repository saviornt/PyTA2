"""Keltner Channels against a hand calculation, via the public API.

No reference library has Keltner Channels (TA-Lib does not), so the checks are
the hand-computed table in `tests/fixtures/keltner_hand.csv` (derivation in its
comments) and, on the SPY fixture, PyTA's own EMA and ATR, which are checked
against TA-Lib in their own reference tests.
"""

import numpy as np
import pyta
from ohlcv_data import load as load_ohlcv
from reference_data import load

FIXTURE = "keltner_hand.csv"
NAMES = ["keltner_upper", "keltner_middle", "keltner_lower"]


def test_keltner_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)
    parameters = reference.parameters

    result = pyta.keltner(
        reference.columns,
        period=reference.period,
        atr_period=int(parameters["atr_period"]),
        k=float(parameters["k"]),
    )

    assert list(reference.outputs) == NAMES
    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )


def test_batch_keltner_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    (result,) = pyta.batch.keltner([reference.columns], 3, 3, 2.0)

    for name in NAMES:
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )


def test_keltner_is_pyta_ema_plus_and_minus_two_atr_on_spy() -> None:
    ohlcv = load_ohlcv()

    upper, middle, lower = (pyta.keltner(ohlcv.columns(), 20, 10, 2.0)[name] for name in NAMES)

    ema = pyta.ema(ohlcv.close, 20)
    atr = pyta.atr(ohlcv.columns(), 10)["atr"]
    np.testing.assert_array_equal(middle, ema)
    np.testing.assert_array_equal(upper[19:], ema[19:] + 2.0 * atr[19:])
    np.testing.assert_array_equal(lower[19:], ema[19:] - 2.0 * atr[19:])
    assert np.isnan(upper[:19]).all()
    assert np.isnan(lower[:19]).all()
