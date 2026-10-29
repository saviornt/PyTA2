//! Rolling mean and rolling population standard deviation.

use pyta_common::{LONG_WINDOW_LEN, LONG_WINDOW_SUM_LANES, SHORT_WINDOW_SUM_LANES};

use super::sum::{CompensatedSum, lane_sum, two_sum};

/// A sum of squared deviations below this may have lost terms to underflow
/// (a square below about `2.2e-308` is subnormal or zero), so the window is
/// summed again with scaling. At this size the lost terms are below `1e-58`
/// of the total for any window that fits in memory.
const MIN_UNSCALED_SQUARES: f64 = 1e-250;

/// Writes the mean of each `period`-value window of `values` to `means`, one
/// per window: `means[i]` is the mean of `values[i..i + period]`.
///
/// The window's sum is a running total, compensated so that it cannot
/// drift: after a large value leaves the window, a plain running sum keeps
/// its rounding error, and a flat window that follows would read that error
/// as a distance from its mean (CCI about -66.7 instead of 0). The total is
/// multiplied by `1 / period`, so a mean may differ from `sum / period` in
/// the last bit.
///
/// The caller guarantees `1 <= period <= values.len()` and
/// `means.len() == values.len() - period + 1`.
pub fn rolling_mean_into(values: &[f64], period: usize, means: &mut [f64]) {
    debug_assert!(period >= 1 && period <= values.len());
    debug_assert_eq!(means.len(), values.len() - period + 1);

    let mut sum = CompensatedSum::default();
    for &value in &values[..period] {
        sum.add(value);
    }

    let inverse = 1.0 / period as f64;
    means[0] = sum.value() * inverse;

    // Each later window gains its last value and loses the one before its
    // first. The change is formed exactly, so the total carries one
    // dependent addition per row.
    let entering = &values[period..];
    for ((mean, &value), &leaving) in means[1..].iter_mut().zip(entering).zip(values) {
        let (change, error) = two_sum(value, -leaving);
        sum.add_with_error(change, error);
        *mean = sum.value() * inverse;
    }
}

/// Calculates the rolling mean of `values` over `period` values, with `NaN`
/// in the first `period - 1` positions (warm-up). See
/// [`rolling_mean_into`].
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn rolling_mean(values: &[f64], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; values.len()];
    rolling_mean_into(values, period, &mut output[period - 1..]);
    output
}

/// Calculates the rolling population standard deviation (dividing by
/// `period`, as TA-Lib's `STDDEV` and Bollinger Bands do) of `values` over
/// `period` values, with `NaN` in the first `period - 1` positions.
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn rolling_std(values: &[f64], period: usize) -> Vec<f64> {
    rolling_mean_std(values, period).1
}

/// Calculates the rolling mean and rolling population standard deviation of
/// `values` over `period` values, both with `NaN` in the first `period - 1`
/// positions (Bollinger Bands needs both).
///
/// Each window's deviation is centred: the window's mean comes from
/// [`rolling_mean_into`], then the squared distances from it are summed
/// afresh (a two-pass algorithm per window). Unlike a running sum of
/// squares, this cannot cancel catastrophically on data with a large offset
/// and a small spread (`1e5 + 1e-3 * noise`), and it never drifts. A window
/// whose squares would overflow (values near `MAX_ABS_INPUT`) or underflow
/// is summed again with its deviations divided by the largest one, so every
/// valid input has a finite, accurate result.
///
/// A flat window gives 0 or a value within rounding of it (the mean is the
/// sum times `1 / period`, which can miss the repeated value by one ULP, so
/// the result is at most about `1e-16` of the window's magnitude). An
/// indicator that divides by it should test it with
/// [`is_zero_scaled`](super::is_zero_scaled).
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn rolling_mean_std(values: &[f64], period: usize) -> (Vec<f64>, Vec<f64>) {
    debug_assert!(period >= 1 && period <= values.len());

    let means = rolling_mean(values, period);
    let mut deviations = vec![f64::NAN; values.len()];
    let windows = values.windows(period).zip(&means[period - 1..]);
    let outputs = &mut deviations[period - 1..];

    if period < LONG_WINDOW_LEN {
        for ((window, &mean), slot) in windows.zip(outputs) {
            *slot = window_std::<SHORT_WINDOW_SUM_LANES>(window, mean);
        }
    } else {
        for ((window, &mean), slot) in windows.zip(outputs) {
            *slot = window_std::<LONG_WINDOW_SUM_LANES>(window, mean);
        }
    }

    (means, deviations)
}

/// Population standard deviation of one window whose mean is `mean`.
#[inline]
fn window_std<const LANES: usize>(window: &[f64], mean: f64) -> f64 {
    let count = window.len() as f64;
    let squares = lane_sum::<LANES>(window, |value| {
        let deviation = value - mean;
        deviation * deviation
    });

    if squares.is_finite() && squares >= MIN_UNSCALED_SQUARES {
        (squares / count).sqrt()
    } else {
        scaled_window_std(window, mean)
    }
}

/// [`window_std`] for a window whose squared deviations overflow or
/// underflow: the deviations are divided by the largest one first, so each
/// square is at most 1.
#[cold]
fn scaled_window_std(window: &[f64], mean: f64) -> f64 {
    let scale = window
        .iter()
        .fold(0.0_f64, |largest, &value| largest.max((value - mean).abs()));

    if scale == 0.0 {
        return 0.0;
    }

    let squares: f64 = window
        .iter()
        .map(|&value| {
            let deviation = (value - mean) / scale;
            deviation * deviation
        })
        .sum();

    scale * (squares / window.len() as f64).sqrt()
}
