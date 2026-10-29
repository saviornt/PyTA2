//! Trend indicators (SMA, EMA, MACD), one per file.

mod ema;
mod macd;
mod sma;

pub use ema::ema;
pub use macd::macd;
pub use sma::sma;
