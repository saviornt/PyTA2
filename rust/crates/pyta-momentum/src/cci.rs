use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Lambert's constant, chosen so that most values fall within ±100.
const LAMBERT: f64 = 0.015;

/// Relative tolerance below which a difference counts as zero, as in
/// TA-Lib's `TA_IS_ZERO_SCALED` (scaled by the window's mean).
const ZERO_TOLERANCE: f64 = 1e-14;

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

    let typical: Vec<f64> = high
        .iter()
        .zip(low)
        .zip(close)
        .map(|((high, low), close)| (high + low + close) / 3.0)
        .collect();

    let mut output = vec![f64::NAN; typical.len()];
    let period_f = period as f64;

    // Each window is summed afresh: the mean deviation needs a pass over the
    // window anyway, and a fresh sum cannot drift like a running one.
    for (window, value) in typical.windows(period).zip(&mut output[period - 1..]) {
        let mean = window.iter().sum::<f64>() / period_f;
        let mean_deviation =
            window.iter().map(|price| (price - mean).abs()).sum::<f64>() / period_f;
        let distance = window[period - 1] - mean;
        let scale = ZERO_TOLERANCE * mean.abs();

        *value = if distance.abs() <= scale
            || mean_deviation <= scale
            || LAMBERT * mean_deviation == 0.0
        {
            0.0
        } else {
            distance / (LAMBERT * mean_deviation)
        };
    }

    Ok(IndicatorOutput::new(output))
}
