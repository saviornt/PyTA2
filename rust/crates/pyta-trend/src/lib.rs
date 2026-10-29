//! Trend indicators (SMA, EMA, WMA, DEMA, MACD), one per file.

mod dema;
mod ema;
mod macd;
mod sma;
mod wma;

pub use dema::dema;
pub use ema::ema;
pub use macd::macd;
pub use sma::sma;
pub use wma::wma;
