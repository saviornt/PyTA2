"""Shared contracts for Sprint 11.5's indicators, before any of them exists.

Float and ordered parameters use the shared validators; a parameterless
indicator passes `()` through the runners; any indicator with a volume slot
rejects a negative volume. Fake native functions stand in for OBV (close and
volume in, one output) as `test_multi_output.py` does for Stochastic.
"""

import math
from collections.abc import Sequence
from fractions import Fraction

import numpy as np
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv
from pyta._api import run, run_batch, run_columns, run_columns_batch
from pyta._outputs import OutputNames
from pyta._validation import (
    ADJ_CLOSE,
    CLOSE,
    HIGH,
    LOW,
    VOLUME,
    Slot,
    validate_ascending,
    validate_int,
    validate_positive_float,
)

type Array = NDArray[np.float64]

# --- float parameters -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2.0, 2.0),
        (0.02, 0.02),
        (2, 2.0),
        (np.float64(1.5), 1.5),
        (np.int64(3), 3.0),
        (5e-324, 5e-324),
    ],
)
def test_positive_float_accepts_numbers_above_zero(value: object, expected: float) -> None:
    result = validate_positive_float("k", value)

    assert result == expected
    assert type(result) is float


@pytest.mark.parametrize("value", [0, 0.0, -0.0, -1, -0.5, math.nan, math.inf, -math.inf, 10**400])
def test_positive_float_rejects_zero_negative_and_non_finite(value: object) -> None:
    with pytest.raises(ValueError, match=r"^k must be a finite number greater than 0, got "):
        validate_positive_float("k", value)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (True, "k must be a number, not bool"),
        ("2.0", "k must be a number, got str"),
        (None, "k must be a number, got NoneType"),
        (Fraction(1, 2), "k must be a number, got Fraction"),
    ],
)
def test_positive_float_rejects_other_types(value: object, message: str) -> None:
    with pytest.raises(TypeError, match=f"^{message}$"):
        validate_positive_float("k", value)


def test_positive_float_upper_bound_is_inclusive() -> None:
    assert validate_positive_float("acceleration", 0.2, maximum=0.2) == 0.2
    assert validate_positive_float("acceleration", 1, maximum=2.0) == 1.0

    with pytest.raises(ValueError, match=r"^acceleration must be at most 0\.2, got 0\.3$"):
        validate_positive_float("acceleration", 0.3, maximum=0.2)
    with pytest.raises(ValueError, match=r"at most 0\.2, got 1$"):
        validate_positive_float("acceleration", 1, maximum=0.2)


def test_ascending_allows_equal_values_unless_strict() -> None:
    validate_ascending(("acceleration", 0.02), ("maximum", 0.2), strict=False)
    validate_ascending(("acceleration", 0.2), ("maximum", 0.2), strict=False)
    validate_ascending(("short", 7), ("medium", 14), ("long", 28), strict=True)

    with pytest.raises(
        ValueError, match=r"^acceleration must be at most maximum, got acceleration=0\.3 and "
    ):
        validate_ascending(("acceleration", 0.3), ("maximum", 0.2), strict=False)
    with pytest.raises(
        ValueError, match=r"^short must be less than medium, got short=7 and medium=7$"
    ):
        validate_ascending(("short", 7), ("medium", 7), ("long", 28), strict=True)
    with pytest.raises(
        ValueError, match=r"^medium must be less than long, got medium=14 and long=10$"
    ):
        validate_ascending(("short", 7), ("medium", 14), ("long", 10), strict=True)


def test_named_int_follows_the_period_rules() -> None:
    assert validate_int("short", 7) == 7
    assert validate_int("short", np.int64(7)) == 7
    assert validate_int("long", 2, minimum=2) == 2

    with pytest.raises(ValueError, match=r"^short must be between 1 and 2147483647, got 0$"):
        validate_int("short", 0)
    with pytest.raises(ValueError, match=r"^long must be between 2 and 2147483647, got 1$"):
        validate_int("long", 1, minimum=2)
    with pytest.raises(TypeError, match=r"^short must be an integer, not bool$"):
        validate_int("short", True)
    with pytest.raises(TypeError, match=r"^short must be an integer, got float$"):
        validate_int("short", 7.0)


# --- parameterless indicators ---------------------------------------------------------------

OBV_SLOTS = (Slot("close", (CLOSE, ADJ_CLOSE)), Slot("volume", (VOLUME,)))
OBV = OutputNames("obv", ("obv",), ("obv",))


def fake_obv(columns: Sequence[Array], *params: object) -> Array:
    """Not OBV: a running sum of signed volume. Takes no parameters, so `params` is empty."""
    assert params == ()
    close, volume = columns
    return np.cumsum(np.sign(np.diff(close, prepend=close[0])) * volume)


def fake_obv_batch(datasets: Sequence[Sequence[Array]], *params: object) -> list[Array]:
    assert params == ()
    return [fake_obv(columns) for columns in datasets]


def obv_data(ohlcv: Ohlcv) -> dict[str, Array]:
    return {"Close": ohlcv.close.copy(), "Volume": ohlcv.volume.copy()}


def test_parameterless_multi_column_indicator_takes_empty_params(ohlcv: Ohlcv) -> None:
    result = run_columns(fake_obv, OBV, obv_data(ohlcv), (), None, OBV_SLOTS)
    batch = run_columns_batch(fake_obv_batch, OBV, [obv_data(ohlcv)], (), None, OBV_SLOTS)

    assert list(result) == ["OBV"]
    np.testing.assert_array_equal(result["OBV"], fake_obv([ohlcv.close, ohlcv.volume]))
    np.testing.assert_array_equal(batch[0]["OBV"], result["OBV"])


def test_parameterless_single_column_indicator_takes_empty_params(ohlcv: Ohlcv) -> None:
    def total(values: Array, *params: object) -> Array:
        assert params == ()
        return np.cumsum(values)

    def total_batch(datasets: Sequence[Array], *params: object) -> list[Array]:
        return [total(values, *params) for values in datasets]

    names = OutputNames("total", ("total",), ())

    np.testing.assert_array_equal(
        run(total, names, ohlcv.volume, (), None, VOLUME), np.cumsum(ohlcv.volume)
    )
    assert run_batch(total_batch, names, [[1.0, 2.0]], (), None, VOLUME) == [[1.0, 3.0]]


def test_float_params_pass_through_unchanged(ohlcv: Ohlcv) -> None:
    def scaled(values: Array, period: int, k: float) -> Array:
        assert type(period) is int
        assert type(k) is float
        return values * k

    names = OutputNames("scaled", ("scaled",), ())
    result = run(scaled, names, ohlcv.close, (20, validate_positive_float("k", 2)), None, CLOSE)

    np.testing.assert_array_equal(result, ohlcv.close * 2.0)


# --- negative volume ------------------------------------------------------------------------


def test_negative_volume_names_the_column_and_the_callers_row(ohlcv: Ohlcv) -> None:
    data = obv_data(ohlcv)
    data["Close"][:3] = np.nan  # rows are numbered as the caller's, not after the skip
    data["Volume"][42] = -100.0

    with pytest.raises(ValueError, match="is negative") as error:
        run_columns(fake_obv, OBV, data, (), None, OBV_SLOTS)

    assert str(error.value) == (
        "column 'Volume' (volume) is negative at index 42 (-100.0); "
        "volume must be zero or more on every row"
    )


def test_zero_volume_is_valid(ohlcv: Ohlcv) -> None:
    data = obv_data(ohlcv)
    data["Volume"][:10] = 0.0
    data["Volume"][20] = -0.0

    result = run_columns(fake_obv, OBV, data, (), None, OBV_SLOTS)

    assert result["OBV"][0] == 0.0


def test_negative_volume_in_a_leading_gap_is_skipped(ohlcv: Ohlcv) -> None:
    # The leading run is trimmed by its NaN close, so its volume never reaches the kernel.
    data = obv_data(ohlcv)
    data["Close"][:2] = np.nan
    data["Volume"][1] = -5.0

    result = run_columns(fake_obv, OBV, data, (), None, OBV_SLOTS)

    assert np.isnan(result["OBV"][:2]).all()


def test_negative_volume_fails_only_its_dataset_in_a_batch(ohlcv: Ohlcv) -> None:
    bad = obv_data(ohlcv)
    bad["Volume"][5] = -1.0

    results = run_columns_batch(
        fake_obv_batch, OBV, {"good": obv_data(ohlcv), "bad": bad}, (), None, OBV_SLOTS
    )

    assert isinstance(results["good"], dict)
    assert isinstance(results["bad"], ValueError)
    assert "is negative at index 5" in str(results["bad"])


def test_volume_is_not_checked_when_the_indicator_has_no_volume_slot(ohlcv: Ohlcv) -> None:
    def spread(columns: Sequence[Array]) -> Array:
        high, low = columns
        return high - low

    slots = (Slot("high", (HIGH,)), Slot("low", (LOW,)))
    data = {"High": ohlcv.high, "Low": ohlcv.low, "Volume": -ohlcv.volume}

    result = run_columns(spread, OutputNames("spread", ("spread",), ()), data, (), None, slots)

    np.testing.assert_array_equal(result["Spread"], ohlcv.high - ohlcv.low)
