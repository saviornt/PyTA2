use pyta_core::kernels::is_zero_scaled;

/// A window's population deviation times `k`, with a flat window snapped to
/// exactly 0, as TA-Lib's STDDEV and BBANDS give.
///
/// The centred kernel (`pyta_core::kernels::rolling_mean_std`) can leave a
/// flat window about `1e-16` of its magnitude away from 0, because the mean
/// may miss the repeated value by one unit in the last place. A deviation
/// within `ZERO_TOLERANCE` (1e-14) of the window's mean is that rounding,
/// not spread (`pyta_core::kernels::is_zero_scaled`), and reads 0.
#[inline]
pub(crate) fn scaled_deviation(deviation: f64, mean: f64, k: f64) -> f64 {
    if is_zero_scaled(deviation, mean.abs()) {
        0.0
    } else {
        deviation * k
    }
}
