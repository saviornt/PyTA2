//! Volatility indicators (ATR), one per file.
//!
//! Planned for Sprint 11.5: STDDEV, Bollinger Bands, Donchian Channels and
//! Keltner Channels. Shared kernels (true range, rolling variance) live in
//! `pyta-core`, since category crates do not depend on each other.

mod atr;

pub use atr::atr;
