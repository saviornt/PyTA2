//! Volatility indicators (ATR, BBANDS, Donchian Channels, Keltner Channels,
//! STDDEV), one per file.
//!
//! Shared kernels (true range, rolling variance, rolling extremes, EMA) live
//! in `pyta-core`, since category crates do not depend on each other;
//! helpers only this crate's indicators share (the flat-window snap, ATR's
//! values for Keltner Channels) live in this crate, private.

mod atr;
mod bbands;
mod deviation;
mod donchian;
mod keltner;
mod stddev;

pub use atr::atr;
pub use bbands::bbands;
pub use donchian::donchian;
pub use keltner::keltner;
pub use stddev::stddev;
