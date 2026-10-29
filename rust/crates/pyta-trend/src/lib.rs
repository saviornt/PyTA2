//! Trend indicators (SMA, EMA, WMA, DEMA, TEMA, KAMA, MACD, ADX, Parabolic
//! SAR, Aroon), one per file.

mod adx;
mod aroon;
mod dema;
mod ema;
mod kama;
mod macd;
mod sar;
mod sma;
mod tema;
mod wma;

pub use adx::adx;
pub use aroon::aroon;
pub use dema::dema;
pub use ema::ema;
pub use kama::kama;
pub use macd::macd;
pub use sar::sar;
pub use sma::sma;
pub use tema::tema;
pub use wma::wma;
