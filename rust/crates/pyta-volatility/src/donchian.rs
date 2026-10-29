use pyta_core::kernels::{rolling_max, rolling_min};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates Donchian Channels from high and low, as TA-Lib's `MAX(high)`
/// and `MIN(low)` (Donchian is not a TA-Lib function).
///
/// The upper channel is the highest high of the last `period` rows and the
/// lower channel the lowest low, both including the current row
/// (`pyta_core::kernels::rolling_max` and `rolling_min`, O(n) whatever the
/// period); the middle channel is `(upper + lower) / 2`. At least `period`
/// values are required.
///
/// Returns three outputs, in order: upper, middle, lower. Each has the same
/// length as the input, and the first `period - 1` positions of each are
/// `NaN` (warm-up).
///
/// Edge cases:
/// - `period` of 1: upper is high and lower is low.
/// - A flat window (or high equal to low throughout it) gives three equal
///   channels.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn donchian(high: &Series, low: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let (high, low) = (high.values(), low.values());

    if high.len() != low.len() {
        return Err(PytaError::LengthMismatch);
    }

    let length = high.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let upper = rolling_max(high, period);
    let lower = rolling_min(low, period);
    let mut middle = vec![f64::NAN; length];

    // Inputs are at most `MAX_ABS_INPUT` (1e290), so the sum stays finite.
    for ((mid, &top), &bottom) in middle[period - 1..]
        .iter_mut()
        .zip(&upper[period - 1..])
        .zip(&lower[period - 1..])
    {
        *mid = (top + bottom) / 2.0;
    }

    IndicatorOutput::with_outputs(vec![upper, middle, lower])
}
