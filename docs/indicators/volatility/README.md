# Volatility indicators

How far and how fast prices move, independent of direction. Call them as `pyta.<name>` or `pyta.volatility.<name>`, and over many datasets as `pyta.batch.<name>`.

Available:

| Indicator | Inputs | Outputs |
|---|---|---|
| [ATR (Average True Range)](atr.md) | high, low, close | `atr` |
| [STDDEV (standard deviation)](stddev.md) | one series | `stddev` |

One page per indicator is added here as each ships. Planned for Sprint 11.5:

| Indicator | Inputs | Outputs |
|---|---|---|
| Bollinger Bands | one series | `bbands_upper`, `bbands_middle`, `bbands_lower` |
| Donchian Channels | high, low | `donchian_upper`, `donchian_middle`, `donchian_lower` |
| Keltner Channels | high, low, close | `keltner_upper`, `keltner_middle`, `keltner_lower` |
