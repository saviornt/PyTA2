"""Ichimoku Cloud against a hand calculation and Donchian Channels, via the public API.

No reference library has the Ichimoku Cloud with unshifted spans (TA-Lib has no
Ichimoku), so the checks are the hand-computed table in
`tests/fixtures/ichimoku_hand.csv` (derivation in its comments) and, on the SPY
fixture, PyTA's own Donchian Channels, whose upper and lower channels are
checked against TA-Lib's MAX and MIN in their own reference test.
"""

import numpy as np
import pyta
from ohlcv_data import load as load_ohlcv
from reference_data import load

FIXTURE = "ichimoku_hand.csv"
NAMES = [
    "ichimoku_tenkan",
    "ichimoku_kijun",
    "ichimoku_senkou_a",
    "ichimoku_senkou_b",
    "ichimoku_chikou",
]


def test_ichimoku_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)
    parameters = reference.parameters

    result = pyta.ichimoku(
        reference.columns,
        tenkan=int(parameters["tenkan"]),
        kijun=int(parameters["kijun"]),
        senkou=int(parameters["senkou"]),
    )

    assert list(reference.outputs) == NAMES
    for name in NAMES:
        # Every value is an exact double, so the tolerance is 0.
        np.testing.assert_allclose(
            result[name], reference.outputs[name], rtol=reference.tolerance, atol=0, equal_nan=True
        )


def test_batch_ichimoku_matches_the_hand_calculation() -> None:
    reference = load(FIXTURE)

    (result,) = pyta.batch.ichimoku([reference.columns], 2, 3, 5)

    for name in NAMES:
        np.testing.assert_array_equal(result[name], reference.outputs[name])


def test_ichimoku_lines_are_pyta_donchian_middles_on_spy() -> None:
    ohlcv = load_ohlcv()

    result = pyta.ichimoku(ohlcv.columns(), 9, 26, 52)

    def middle(period: int) -> np.ndarray:
        return np.asarray(pyta.donchian(ohlcv.columns(), period)["donchian_middle"])

    tenkan, kijun = middle(9), middle(26)
    np.testing.assert_array_equal(result["ichimoku_tenkan"], tenkan)
    np.testing.assert_array_equal(result["ichimoku_kijun"], kijun)
    np.testing.assert_array_equal(result["ichimoku_senkou_a"], (tenkan + kijun) / 2)
    np.testing.assert_array_equal(result["ichimoku_senkou_b"], middle(52))
    np.testing.assert_array_equal(result["ichimoku_chikou"], ohlcv.close)
