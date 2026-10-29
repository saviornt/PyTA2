//! Volatility indicators (ATR, BBANDS, Donchian Channels, STDDEV), one per
//! file.
//!
//! Planned for Sprint 11.5: Keltner Channels. Shared kernels (true range,
//! rolling variance, rolling extremes) live in `pyta-core`, since
//! category crates do not depend on each other; helpers only this crate's
//! indicators share (the flat-window snap) live in private modules here.

mod atr;
mod bbands;
mod deviation;
mod donchian;
mod stddev;

pub use atr::atr;
pub use bbands::bbands;
pub use donchian::donchian;
pub use stddev::stddev;
