//! Trend indicators (SMA, EMA, WMA, DEMA, TEMA, KAMA, MACD), one per file.

mod dema;
mod ema;
mod kama;
mod macd;
mod sma;
mod tema;
mod wma;

pub use dema::dema;
pub use ema::ema;
pub use kama::kama;
pub use macd::macd;
pub use sma::sma;
pub use tema::tema;
pub use wma::wma;
