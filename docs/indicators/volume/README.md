# Volume indicators

How much is traded, and whether money flows into or out of an asset. Call them as `pyta.<name>` or `pyta.volume.<name>`, and over many datasets as `pyta.batch.<name>`.

A multi-column indicator with a `volume` input rejects a negative volume on any row with a `ValueError` naming the column and the row (zero is valid). One page per indicator is added here as each ships. Planned for Sprint 11.5:

| Indicator | Inputs | Outputs |
|---|---|---|
| OBV (On-Balance Volume) | close, volume | `obv` |
| Accumulation/Distribution | high, low, close, volume | `ad` |
| Chaikin Money Flow | high, low, close, volume | `cmf` |
| VWAP (Volume-Weighted Average Price) | high, low, close, volume | `vwap` |
| Volume ROC | volume | `vroc` |
