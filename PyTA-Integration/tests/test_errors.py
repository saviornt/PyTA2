"""Invalid parameters and data raise the documented exception types and messages (API.md §7).

The messages are matched exactly here on purpose: this project pins the wording an outside user
sees. PyTA's docs say the wording may change between releases; update these tests when it does.
"""

import re
from typing import Any

import numpy as np
import pandas as pd
import pyta
import pytest

CLOSE = [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("function", "args", "kwargs", "error", "message"),
    [
        (
            pyta.sma,
            (CLOSE,),
            {"period": 5},
            ValueError,
            "period (5) exceeds the series length (3); use a smaller period or provide more data",
        ),
        (
            pyta.rsi,
            (CLOSE,),
            {"period": 5},
            ValueError,
            "not enough data: at least 6 values are required, got 3",
        ),
        (
            pyta.sma,
            ([1.0, float("nan"), 3.0, 4.0],),
            {"period": 2},
            ValueError,
            "non-finite value (NaN or infinity) at index 1; only leading NaN values are skipped",
        ),
        (
            pyta.sma,
            (CLOSE,),
            {"period": 0},
            ValueError,
            "period must be between 1 and 2147483647, got 0",
        ),
        (pyta.sma, (CLOSE,), {"period": "14"}, TypeError, "period must be an integer, got str"),
        (pyta.sma, (CLOSE,), {"period": True}, TypeError, "period must be an integer, not bool"),
        (
            pyta.stddev,
            (CLOSE,),
            {"period": 2, "k": -1.0},
            ValueError,
            "k must be a finite number greater than 0, got -1.0",
        ),
        (
            pyta.macd,
            (np.arange(1.0, 60.0),),
            {"fast": 1},
            ValueError,
            "fast must be between 2 and 2147483647, got 1",
        ),
        (
            pyta.sar,
            ({"high": [2.0, 3.0, 4.0], "low": [1.0, 2.0, 3.0]},),
            {"acceleration": 0.3, "maximum": 0.2},
            ValueError,
            "acceleration must be at most maximum, got acceleration=0.3 and maximum=0.2",
        ),
        (
            pyta.ultosc,
            ({"high": [2.0] * 40, "low": [1.0] * 40, "close": [1.5] * 40},),
            {"short": 14, "medium": 7},
            ValueError,
            "short must be less than medium, got short=14 and medium=7",
        ),
    ],
)
def test_documented_messages(
    function: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=f"^{re.escape(message)}$"):
        function(*args, **kwargs)


def test_missing_close_column_names_the_available_ones() -> None:
    frame = pd.DataFrame({"px": [1.0, 2.0, 3.0], "vol": [10.0, 20.0, 30.0]})
    message = "no 'close' column found; available columns: 'px', 'vol'. Pass column= to choose one"
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        pyta.sma(frame, period=2)


def test_missing_multi_column_input_names_the_missing_role(spy: pd.DataFrame) -> None:
    frame = spy[["Open", "High", "Close", "Volume"]]
    with pytest.raises(
        ValueError, match=r"^cci needs the columns high, low and close .*missing: low"
    ):
        pyta.cci(frame, period=20)


def test_high_below_low_is_a_row_error(spy: pd.DataFrame) -> None:
    frame = spy.copy()
    frame.iloc[5, frame.columns.get_loc("Low")] = frame["High"].iloc[5] + 1.0
    with pytest.raises(ValueError, match="High"):
        pyta.atr(frame)


def test_one_series_given_to_a_multi_column_indicator_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        pyta.cci(np.arange(1.0, 30.0), period=5)


def test_text_that_is_not_a_number_names_column_and_index() -> None:
    data = {"close": ["1.0", "2.0", "abc", "4.0"]}
    message = "column 'close' value 'abc' at index 2 is not a number"
    with pytest.raises(TypeError, match=re.escape(message)):
        pyta.sma(data, period=2)


def test_column_must_be_a_standard_name(spy: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match=r"^column 'Px' is not a recognized column name"):
        pyta.sma(spy, period=5, column="Px")


def test_unknown_output_target_raises_before_reading_data() -> None:
    with pytest.raises(ValueError, match=r"^output must be None or one of .*; got 'JSON'$"):
        pyta.sma({1.0, 2.0}, period=2, output="JSON")  # type: ignore[arg-type]


def test_ichimoku_shift_must_be_a_bool(spy: pd.DataFrame) -> None:
    with pytest.raises(TypeError, match=r"^shift must be True or False, got int$"):
        pyta.ichimoku(spy, shift=1)  # type: ignore[arg-type]


def test_unsupported_container_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        pyta.sma({1.0, 2.0, 3.0}, period=2)  # type: ignore[arg-type]


def test_batch_parameter_errors_raise_for_the_whole_call() -> None:
    with pytest.raises(ValueError, match="period must be between 1 and 2147483647, got 0"):
        pyta.batch.sma([CLOSE, CLOSE], period=0)


def test_batch_data_errors_are_returned_in_place() -> None:
    results = pyta.batch.sma([CLOSE, [1.0], [1.0, "abc", 3.0], {1.0, 2.0}], period=2)
    assert np.isnan(results[0][0])
    assert results[0][1:] == [1.5, 2.5]
    assert isinstance(results[1], ValueError)
    assert str(results[1]).startswith("period (2) exceeds the series length (1)")
    assert isinstance(results[2], TypeError)
    assert "value 'abc' at index 1 is not a number" in str(results[2])
    assert isinstance(results[3], TypeError)
