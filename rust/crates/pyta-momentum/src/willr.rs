use pyta_core::kernels::{for_each_window_max, for_each_window_min, is_zero_scaled};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// The smallest `period` Williams %R accepts (TA-Lib's lower bound).
const MIN_PERIOD: usize = 2;

/// Calculates Larry Williams' %R from high, low and close, as TA-Lib 0.8.3's
/// `TA_WILLR`.
///
/// On each row, `(highest high - close) / (highest high - lowest low) * -100`,
/// the extremes over the last `period` rows, the current row included
/// (`pyta_core::kernels`' rolling extremes, O(n) whatever the period). The
/// result lies between -100 (close at the lowest low) and 0 (close at the
/// highest high).
///
/// Returns one output with the input's length; the first `period - 1`
/// positions are `NaN` (warm-up). At least `period` values are required.
///
/// Edge cases, as TA-Lib 0.8.3:
/// - A flat window (the range is zero next to `|highest| + |lowest|`,
///   TA-Lib's `TA_IS_ZERO_SCALED`) gives 0.
/// - A value above 0 or below -100 is clamped to that bound; it happens
///   only when a close lies outside its window's range, which nothing
///   checks. A close at the highest high gives `-0.0`, as TA-Lib's does.
///
/// The columns are not checked against each other (for example high below
/// low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn willr(
    high: &Series,
    low: &Series,
    close: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period < MIN_PERIOD {
        return Err(PytaError::InvalidParameter {
            name: "period",
            minimum: MIN_PERIOD,
            value: period,
        });
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    let length = close.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let mut output = vec![f64::NAN; length];

    // The highest high is parked in the output until the lowest low is known.
    for_each_window_max(high, period, |row, index| output[row] = high[index]);
    for_each_window_min(low, period, |row, index| {
        let (highest, lowest) = (output[row], low[index]);
        let range = highest - lowest;

        output[row] = if is_zero_scaled(range, highest.abs() + lowest.abs()) {
            0.0
        } else {
            // TA-Lib divides by the range, then scales, then clamps with
            // `> 0.0` and `< -100.0`, which is `clamp`'s rule: a `-0.0`
            // passes through unchanged.
            ((highest - close[row]) / range * -100.0).clamp(-100.0, 0.0)
        };
    });

    Ok(IndicatorOutput::new(output))
}
