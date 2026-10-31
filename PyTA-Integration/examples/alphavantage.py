"""Indicators on AlphaVantage-shaped CSV and JSON text.

AlphaVantage sends the newest row first, and PyTA never reorders rows, so both inputs are put
oldest first before the call. The CSV (`timestamp,open,high,low,close,volume`) then goes in as it
is. The JSON nests each day under its date (`{"Time Series (Daily)": {"2025-12-31": {"1. open":
"687.1400", ...}}}`), which PyTA does not unpack: it is flattened into records with the standard
library. The numbered names (`4. close`) and the numbers as strings are accepted as they are.

Run: .venv/bin/python examples/alphavantage.py
"""

import json
from pathlib import Path

import pandas as pd
import pyta

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_csv_oldest_first() -> str:
    """The daily CSV with its rows reversed to oldest first, header kept on top."""
    header, *rows = (DATA_DIR / "alphavantage_daily.csv").read_text().splitlines()
    return "\n".join([header, *reversed(rows)]) + "\n"


def load_json_records() -> str:
    """The daily JSON flattened into a JSON array of records, oldest first."""
    document = json.loads((DATA_DIR / "alphavantage_daily.json").read_text())
    series: dict[str, dict[str, str]] = document["Time Series (Daily)"]
    # ISO dates sort chronologically, whatever order the provider used.
    records = [{"timestamp": day, **fields} for day, fields in sorted(series.items())]
    return json.dumps(records)


def main() -> tuple[str, str, pd.Series]:
    csv_text = load_csv_oldest_first()
    json_text = load_json_records()

    sma_csv = pyta.sma(csv_text, period=10)  # CSV in, CSV out: a header "sma", one row per row
    stoch_json = pyta.stoch(json_text, k=5)  # JSON records in, records of stoch_k and stoch_d out
    cci_series = pyta.cci(json_text, period=20, output="pandas")  # JSON in, a pandas Series out

    header, *lines = sma_csv.splitlines()
    print("SMA(10) on the CSV, header and last three lines:")
    print("\n".join([header, *lines[-3:]]))
    print("\nStochastic(5, 3, 3) on the JSON, last three records:")
    for record in json.loads(stoch_json)[-3:]:
        print(record)
    print("\nCCI(20) on the JSON as a pandas Series, last three values:")
    print(cci_series.tail(3).round(4).to_string())
    return sma_csv, stoch_json, cci_series


if __name__ == "__main__":
    main()
