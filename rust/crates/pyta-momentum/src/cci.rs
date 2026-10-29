use pyta_common::{LONG_WINDOW_LEN, LONG_WINDOW_SUM_LANES, SHORT_WINDOW_SUM_LANES};
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

    // Pass 1: each window's mean, stored where its CCI will go. The window's
    // sum is a running total, compensated so that it cannot drift: after a
    // large price leaves the window, a plain running sum keeps its rounding
    // error, and a flat window that follows would read that error as both
    // its distance from the mean and its deviation (CCI about -66.7 instead
    // of 0).
    let mut sum = CompensatedSum::default();
    for &price in &typical[..period] {
        sum.add(price);
    }

    let inverse = 1.0 / period_f;
    let means = &mut output[period - 1..];
    means[0] = sum.value() * inverse;

    // Each later window gains its last price and loses the one before its first.
    let entering = &typical[period..];
    for ((mean, &price), &leaving) in means[1..].iter_mut().zip(entering).zip(&typical) {
        // The change is formed exactly, so the total carries one dependent
        // addition per row.
        let (change, error) = two_sum(price, -leaving);
        sum.add(change);
        sum.compensation += error;
        *mean = sum.value() * inverse;
    }

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
    let scale = ZERO_TOLERANCE * mean.abs();

    if distance.abs() <= scale || deviation_sum <= scale * period || LAMBERT * deviation_sum == 0.0
    {
        0.0
    } else {
        distance * period / (LAMBERT * deviation_sum)
    }
}

/// A running sum with Neumaier-style compensation: each addition's rounding
/// error is computed exactly (Knuth's two-sum) and kept apart, so the total
/// stays as accurate as a fresh sum however many values pass through.
#[derive(Default)]
struct CompensatedSum {
    sum: f64,
    compensation: f64,
}

impl CompensatedSum {
    #[inline]
    fn add(&mut self, value: f64) {
        let (total, error) = two_sum(self.sum, value);
        self.compensation += error;
        self.sum = total;
    }

    #[inline]
    fn value(&self) -> f64 {
        self.sum + self.compensation
    }
}

/// `a + b` and its rounding error exactly (Knuth's two-sum): `a + b` equals
/// the two results added in exact arithmetic. Exact whichever operand is
/// larger, so no branch is needed.
#[inline]
fn two_sum(a: f64, b: f64) -> (f64, f64) {
    let total = a + b;
    let b_part = total - a;
    let a_part = total - b_part;
    (total, (a - a_part) + (b - b_part))
}

/// Sums `term(x)` over `values` with `LANES` independent totals, so the
/// additions overlap instead of each waiting for the last (see
/// `pyta_common::kernels`).
#[inline]
fn lane_sum<const LANES: usize>(values: &[f64], term: impl Fn(f64) -> f64) -> f64 {
    let mut lanes = [0.0; LANES];
    let (chunks, tail) = values.as_chunks::<LANES>();

    for chunk in chunks {
        for (lane, &value) in lanes.iter_mut().zip(chunk) {
            *lane += term(value);
        }
    }

    tail.iter().map(|&value| term(value)).sum::<f64>() + lanes.iter().sum::<f64>()
}
