# Volume indicators

How much is traded, and whether money flows into or out of an asset. Call them as `pyta.<name>` or `pyta.volume.<name>`, and over many datasets as `pyta.batch.<name>`.

A multi-column indicator with a `volume` input rejects a negative volume on any row with a `ValueError` naming the column and the row (zero is valid).

Available:

| Indicator | Inputs | Outputs |
|---|---|---|
| [OBV (On-Balance Volume)](obv.md) | close, volume | `obv` |
| [Accumulation/Distribution](ad.md) | high, low, close, volume | `ad` |
| [Chaikin Money Flow](cmf.md) | high, low, close, volume | `cmf` |
| [VWAP (Volume-Weighted Average Price)](vwap.md) | high, low, close, volume | `vwap` |

One page per indicator is added here as each ships. Planned for Sprint 11.5:

| Indicator | Inputs | Outputs |
|---|---|---|
| Volume ROC | volume | `vroc` |
