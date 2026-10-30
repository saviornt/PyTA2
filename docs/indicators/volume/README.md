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
| [Volume ROC](vroc.md) | volume (one column) | `vroc` |

Every volume indicator planned for Sprint 11.5 is now available. Volume ROC also rejects a negative value when its column is matched to the volume role by name.
