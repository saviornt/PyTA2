"""One indicator over several datasets in one call, with failures returned in place.

`pyta.batch.<name>` takes a list or a mapping of datasets (each any supported container) and
returns results in the same shape. A dataset that fails is returned as its exception, under its
own key or at its own position; the others still complete.

Run: .venv/bin/python examples/batch.py
"""

import numpy as np
import pandas as pd
import pyta
from yfinance_dataframe import load_yfinance_frame


def build_datasets(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Five slices of one frame: two valid, three that fail in different ways."""
    gap = frame.copy()
    gap.iloc[100, gap.columns.get_loc("Close")] = np.nan  # a gap after the first value
    return {
        "SPY full": frame,
        "SPY 2025 H2": frame.loc["2025-07-01":],
        "too short": frame.iloc[:10],  # RSI(14) needs 15 rows
        "gap": gap,
        "no close": frame.drop(columns=["Close", "Adj Close"]),
    }


def main() -> dict[str, pd.DataFrame | Exception]:
    frame = load_yfinance_frame()
    results = pyta.batch.rsi(build_datasets(frame), period=14)
    print("RSI(14) over five datasets in one call:")
    for name, result in results.items():
        if isinstance(result, Exception):
            print(f"  {name:12} failed, {type(result).__name__}: {result}")
        else:
            print(f"  {name:12} {len(result):3} rows, last RSI {result['RSI'].iloc[-1]:.2f}")

    # A list works the same way; multi-output indicators give their usual tuple per dataset.
    close = frame["Close"].to_numpy()
    bands = pyta.batch.bbands([close, close[-60:], close[:5]], period=20, k=2.0)
    print("\nBollinger Bands(20, 2) over a list of three NumPy arrays:")
    for position, result in enumerate(bands):
        if isinstance(result, Exception):
            print(f"  [{position}] failed, {type(result).__name__}: {result}")
        else:
            upper, middle, lower = result
            print(f"  [{position}] last bands {upper[-1]:.4f} / {middle[-1]:.4f} / {lower[-1]:.4f}")
    return results


if __name__ == "__main__":
    main()
