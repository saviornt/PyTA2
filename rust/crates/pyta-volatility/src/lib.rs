//! Volatility indicators (ATR, STDDEV), one per file.
//!
//! Planned for Sprint 11.5: Bollinger Bands, Donchian Channels and
//! Keltner Channels. Shared kernels (true range, rolling variance) live in
//! `pyta-core`, since category crates do not depend on each other.

mod atr;
mod stddev;

pub use atr::atr;
pub use stddev::stddev;
