# Trend indicators

Which way prices are heading and how strongly: moving averages, trend strength and trend-following stops. Call them as `pyta.<name>` or `pyta.trend.<name>`, and over many datasets as `pyta.batch.<name>`.

Available:

| Indicator | Inputs | Outputs |
|---|---|---|
| [SMA (Simple Moving Average)](sma.md) | one series | `sma` |
| [EMA (Exponential Moving Average)](ema.md) | one series | `ema` |
| [WMA (Weighted Moving Average)](wma.md) | one series | `wma` |
| [DEMA (Double Exponential Moving Average)](dema.md) | one series | `dema` |
| [TEMA (Triple Exponential Moving Average)](tema.md) | one series | `tema` |
| [KAMA (Kaufman Adaptive Moving Average)](kama.md) | one series | `kama` |
| [MACD (Moving Average Convergence/Divergence)](macd.md) | one series | `macd`, `macd_signal`, `macd_hist` |
| [ADX (Average Directional Index)](adx.md) | high, low, close | `adx`, `adx_plus_di`, `adx_minus_di` |
| [Parabolic SAR](sar.md) | high, low | `sar` |
| [Aroon](aroon.md) | high, low | `aroon_up`, `aroon_down`, `aroon_osc` |
| [Ichimoku Cloud](ichimoku.md) | high, low, close | `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`, `ichimoku_chikou` |

One page per indicator; every trend indicator planned for Sprint 11.5 is now available.
