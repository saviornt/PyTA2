use pyta_core::kernels::ema;
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::atr::atr_values;

/// Calculates Keltner Channels from high, low and close, in the modern
/// definition (Linda Raschke's, which StockCharts and most charting
/// platforms use).
/// Keltner Channels are not a TA-Lib function.
///
/// The middle line is the EMA of close over `period`
/// (`pyta_core::kernels::ema`: TA-Lib's convention, seeded with the simple
/// average of the first `period` values, so it equals PyTA's EMA bit for
/// bit). The bands lie `k` times the ATR over `atr_period` above and below
/// it, with ATR exactly as this crate's `atr` computes it (Wilder's smoothing,
/// first value at row `atr_period`). At least
/// `max(period, atr_period + 1)` values are required.
///
/// Returns three outputs, in order: upper, middle, lower. Each has the same
/// length as the input. The middle line's first `period - 1` positions are
/// `NaN`; the bands' first `max(period - 1, atr_period)` (each output keeps
/// its own warm-up).
///
/// Edge cases:
/// - A flat series (or high equal to low with an unchanged close): ATR 0, so
///   three equal lines.
/// - `period` of 1: the middle line is close.
/// - A `k` so large that `k * ATR` overflows gives infinite bands.
///
/// Chester Keltner's 1960 original (a 10-day simple average of the typical
/// price, plus and minus a 10-day simple average of high - low) is not
/// implemented.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InvalidParameter` when `atr_period` is zero.
/// Returns `InvalidFloatParameter` when `k` is not a finite number above 0.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than
/// `max(period, atr_period + 1)` values.
pub fn keltner(
    high: &Series,
    low: &Series,
    close: &Series,
    period: usize,
    atr_period: usize,
    k: f64,
) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    if atr_period == 0 {
        return Err(PytaError::InvalidParameter {
            name: "atr_period",
            minimum: 1,
            value: atr_period,
        });
    }

    // Also rejects NaN, for which every comparison is false.
    if !(k > 0.0 && k.is_finite()) {
        return Err(PytaError::InvalidFloatParameter {
            name: "k",
            value: k,
        });
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    let length = close.len();
    // Saturating, so a huge `atr_period` from a Rust caller is an error, not
    // an overflow.
    let required = period.max(atr_period.saturating_add(1));

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let middle = ema(close, period);
    // The ATR buffer becomes the upper band, so only the lower band is a new
    // allocation.
    let mut upper = atr_values(high, low, close, atr_period);
    let mut lower = vec![f64::NAN; length];
    let start = (period - 1).max(atr_period);

    // Rows before `start` stay NaN: either the EMA or the ATR has no value.
    upper[..start].fill(f64::NAN);
    for ((top, bottom), &mid) in upper[start..]
        .iter_mut()
        .zip(&mut lower[start..])
        .zip(&middle[start..])
    {
        let width = k * *top;
        *top = mid + width;
        *bottom = mid - width;
    }

    IndicatorOutput::with_outputs(vec![upper, middle, lower])
}
