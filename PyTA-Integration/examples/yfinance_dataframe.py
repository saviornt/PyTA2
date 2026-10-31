"""SMA, RSI, MACD and the Stochastic on a pandas DataFrame shaped like yfinance's output.

yfinance's `Ticker(...).history(auto_adjust=False)` gives a time-zone aware DatetimeIndex named
`Date` and title-case columns `Open High Low Close Adj Close Volume`. PyTA finds the columns by
name, so the frame goes in as it is, and the results come back as DataFrames on the same index
with title-case names (`SMA`, `MACD_Signal`, `Stoch_K`).

Run: .venv/bin/python examples/yfinance_dataframe.py
"""

from pathlib import Path

import pandas as pd
import pyta

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_yfinance_frame() -> pd.DataFrame:
    """Read the SPY sample (300 sessions) into the shape yfinance returns."""
    raw = pd.read_csv(
        DATA_DIR / "spy_daily.csv", comment="#", index_col="date", parse_dates=["date"]
    )
    frame = raw.rename(columns=str.title)
    frame.index = frame.index.tz_localize("America/New_York").rename("Date")
    # The sample is unadjusted and carries no adjusted series, so "Adj Close" repeats "Close"
    # here; it is present only to give the frame yfinance's full set of columns.
    frame.insert(4, "Adj Close", frame["Close"])
    return frame


def main() -> pd.DataFrame:
    frame = load_yfinance_frame()

    sma = pyta.sma(frame, period=20)  # one column, "SMA", picked from "Close"
    rsi = pyta.rsi(frame)  # period 14 by default
    macd = pyta.macd(frame)  # MACD, MACD_Signal, MACD_Hist (12/26/9)
    stoch = pyta.stoch(frame)  # Stoch_K, Stoch_D from High, Low and Close (14/3/3)

    result = frame[["Close"]].join([sma, rsi, macd, stoch])
    print(f"SPY, {len(frame)} sessions; last five rows:")
    print(result.tail().round(4).to_string())
    return result


if __name__ == "__main__":
    main()
