//! Calculation building blocks shared by indicators in different
//! categories.
//!
//! Category crates may not depend on each other, so a calculation that more
//! than one category needs (an EMA inside TRIX and Keltner Channels, true
//! range inside ATR and ADX) lives here, one block per file. Each block
//! takes plain slices that `Series` has already validated (finite, at most
//! `MAX_ABS_INPUT` in magnitude) and leaves argument checks (periods,
//! lengths) to the indicator, which reports them as `PytaError`s; the
//! blocks only `debug_assert!` their preconditions.
//!
//! Each block's arithmetic is fixed, in a documented order, so an indicator
//! built from it gives the same bits wherever it is used.

mod ema;
mod extremes;
mod rolling;
mod sum;
mod true_range;
mod typical_price;
mod wilder;
mod zero;

pub use ema::{ema, ema_into, ema_multiplier, ema_step};
pub use extremes::{for_each_window_max, for_each_window_min, rolling_max, rolling_min};
pub use rolling::{rolling_mean, rolling_mean_into, rolling_mean_std, rolling_std};
pub use sum::{CompensatedSum, lane_sum, two_sum};
pub use true_range::{true_range, true_range_at};
pub use typical_price::{typical_price, typical_price_at};
pub use wilder::{WilderAverage, WilderSum, wilder_into};
pub use zero::is_zero_scaled;
