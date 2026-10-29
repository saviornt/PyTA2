//! Trend indicators (SMA, EMA, WMA, MACD), one per file.

mod ema;
mod macd;
mod sma;
mod wma;

pub use ema::ema;
pub use macd::macd;
pub use sma::sma;
pub use wma::wma;
