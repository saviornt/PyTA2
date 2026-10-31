"""Every example runs as a script, and its results have the documented shape and values."""

import json
import subprocess
import sys
from pathlib import Path

import alphavantage
import batch
import numpy as np
import pandas as pd
import pyta
import pytest
import yfinance_dataframe

PROJECT_DIR = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((PROJECT_DIR / "examples").glob("*.py"))


def test_examples_are_found() -> None:
    assert {path.name for path in EXAMPLES} >= {
        "alphavantage.py",
        "batch.py",
        "yfinance_dataframe.py",
    }


@pytest.mark.parametrize("script", EXAMPLES, ids=lambda path: path.name)
def test_example_runs_as_a_script(script: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-W", "error", str(script)],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip()


def test_yfinance_example_keeps_index_and_title_case() -> None:
    result = yfinance_dataframe.main()
    assert list(result.columns) == [
        "Close",
        "SMA",
        "RSI",
        "MACD",
        "MACD_Signal",
        "MACD_Hist",
        "Stoch_K",
        "Stoch_D",
    ]
    assert len(result) == 300
    assert str(result.index.tz) == "America/New_York"
    assert result.index.name == "Date"
    assert result["SMA"].iloc[:19].isna().all()
    assert result["SMA"].iloc[19:].notna().all()
    assert result["RSI"].iloc[14:].between(0, 100).all()


def test_alphavantage_inputs_are_oldest_first() -> None:
    rows = alphavantage.load_csv_oldest_first().splitlines()
    assert rows[0] == "timestamp,open,high,low,close,volume"
    assert rows[1].startswith("2025-11-04,")
    assert rows[-1].startswith("2025-12-31,")
    records = json.loads(alphavantage.load_json_records())
    assert [records[0]["timestamp"], records[-1]["timestamp"]] == ["2025-11-04", "2025-12-31"]
    assert records[-1]["4. close"] == "681.9200"


def test_alphavantage_results_agree_with_the_dataframe(spy: pd.DataFrame) -> None:
    sma_csv, stoch_json, cci_series = alphavantage.main()
    tail = spy.iloc[-40:]  # the sample files hold the last 40 sessions

    header, *lines = sma_csv.splitlines()
    assert header == "sma"
    sma_values = np.array([float(line) if line else np.nan for line in lines])
    expected_sma = tail["Close"].rolling(10).mean().to_numpy()
    np.testing.assert_allclose(sma_values, expected_sma, rtol=0, atol=1e-9)

    records = json.loads(stoch_json)
    assert len(records) == 40
    assert list(records[-1]) == ["stoch_k", "stoch_d"]
    stoch = pyta.stoch(tail, k=5)
    for name, column in (("stoch_k", "Stoch_K"), ("stoch_d", "Stoch_D")):
        from_json = np.array([np.nan if r[name] is None else r[name] for r in records])
        np.testing.assert_array_equal(from_json, stoch[column].to_numpy())

    assert cci_series.name == "cci"
    np.testing.assert_array_equal(cci_series.to_numpy(), pyta.cci(tail, period=20)["CCI"])


def test_batch_example_returns_failures_in_place() -> None:
    results = batch.main()
    assert list(results) == ["SPY full", "SPY 2025 H2", "too short", "gap", "no close"]
    assert isinstance(results["SPY full"], pd.DataFrame)
    assert isinstance(results["SPY 2025 H2"], pd.DataFrame)
    for name in ("too short", "gap", "no close"):
        assert isinstance(results[name], ValueError), name
    assert "at least 15 values are required, got 10" in str(results["too short"])
    assert "at index 100" in str(results["gap"])
    assert "no 'close' column found" in str(results["no close"])
