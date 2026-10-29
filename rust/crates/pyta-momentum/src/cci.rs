use pyta_common::{LONG_WINDOW_LEN, LONG_WINDOW_SUM_LANES, SHORT_WINDOW_SUM_LANES, ZERO_TOLERANCE};
use pyta_core::kernels::{is_zero_scaled, lane_sum, rolling_mean_into, typical_price};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Lambert's constant, chosen so that most values fall within ±100.
const LAMBERT: f64 = 0.015;

/// Calculates the Commodity Channel Index (CCI).
///
/// The typical price is `(high + low + close) / 3`. For each window of
/// `period` typical prices, CCI is the latest typical price minus the
/// window's mean, divided by `0.015` times the window's mean absolute
/// deviation. At least `period` values are required.
///
/// The output has the same length as the input. The first `period - 1`
/// positions are `NaN` (warm-up).
///
/// Edge cases, following TA-Lib:
/// - The latest typical price equals the mean, or the mean deviation is
///   zero (a flat window), within a relative `1e-14` of the mean: CCI is 0.
/// - `period` of 1: every window is flat, so CCI is 0 throughout.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than `period` values.
pub fn cci(
    high: &Series,
    low: &Series,
    close: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    if period > close.len() {
        return Err(PytaError::InsufficientData {
            required: period,
            length: close.len(),
        });
    }

    let typical = typical_price(high, low, close);
    let mut output = vec![f64::NAN; typical.len()];

    // Pass 1: each window's mean, stored where its CCI will go. The kernel's
    // running sum is compensated so that it cannot drift: a plain one would
    // keep the rounding error of a large price that has left the window, and
    // a flat window that follows would read it as both its distance from the
    // mean and its deviation (CCI about -66.7 instead of 0).
    let means = &mut output[period - 1..];
    rolling_mean_into(&typical, period, means);

    // Pass 2: each window's CCI from its mean. The rows are independent here,
    // so the CPU overlaps them; in one combined loop each row waited for the
    // running sum.
    if period < LONG_WINDOW_LEN {
        windows_cci::<SHORT_WINDOW_SUM_LANES>(&typical, period, means);
    } else {
        windows_cci::<LONG_WINDOW_SUM_LANES>(&typical, period, means);
    }

    Ok(IndicatorOutput::new(output))
}

/// Replaces each window's mean in `means` with the window's CCI, summing
/// the deviations with `LANES` independent totals.
fn windows_cci<const LANES: usize>(typical: &[f64], period: usize, means: &mut [f64]) {
    for (window, value) in typical.windows(period).zip(means) {
        *value = window_cci::<LANES>(window, *value);
    }
}

/// CCI of one window of typical prices whose mean is `mean`.
#[inline]
fn window_cci<const LANES: usize>(window: &[f64], mean: f64) -> f64 {
    let period = window.len() as f64;
    // The mean deviation times `period`: dividing it out is folded into the
    // final division, one fewer on the critical path.
    let deviation_sum = lane_sum::<LANES>(window, |price| (price - mean).abs());
    let distance = window[window.len() - 1] - mean;

    // TA-Lib's scaled zero test, relative to the mean. For the deviation it
    // is applied to the sum, so the bound is multiplied by `period` (in this
    // order, which `is_zero_scaled` cannot express).
    if is_zero_scaled(distance, mean.abs())
        || deviation_sum <= ZERO_TOLERANCE * mean.abs() * period
        || LAMBERT * deviation_sum == 0.0
    {
        0.0
    } else {
        distance * period / (LAMBERT * deviation_sum)
    }
}
