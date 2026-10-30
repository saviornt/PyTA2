# Momentum indicators

How fast prices are changing, and whether a move is stretched (overbought or oversold). Call them as `pyta.<name>` or `pyta.momentum.<name>`, and over many datasets as `pyta.batch.<name>`.

Available:

| Indicator | Inputs | Outputs |
|---|---|---|
| [RSI (Relative Strength Index)](rsi.md) | one series | `rsi` |
| [CCI (Commodity Channel Index)](cci.md) | high, low, close | `cci` |
| [Stochastic Oscillator](stoch.md) | high, low, close | `stoch_k`, `stoch_d` |
| [Williams %R](willr.md) | high, low, close | `willr` |
| [ROC (Rate of Change)](roc.md) | one series | `roc` |
| [MFI (Money Flow Index)](mfi.md) | high, low, close, volume | `mfi` |
| [TRIX](trix.md) | one series | `trix` |
| [Ultimate Oscillator](ultosc.md) | high, low, close | `ultosc` |

One page per indicator; every momentum indicator planned for Sprint 11.5 is now available. MFI rejects a negative volume on any row, like the [volume indicators](../volume/README.md).
