use pyta_core::kernels::rolling_mean_std;
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::deviation::scaled_deviation;

/// The smallest `period` STDDEV accepts (TA-Lib's lower bound): a window of
/// one value has no spread.
const MIN_PERIOD: usize = 2;

/// Calculates the rolling Standard Deviation (STDDEV), following TA-Lib's
/// `TA_STDDEV`: the population standard deviation (dividing by `period`) of
/// the last `period` values, multiplied by `k`.
///
/// Each window is centred on its own mean and summed afresh
/// (`pyta_core::kernels::rolling_mean_std`), not computed from a running sum
/// of squares as older TA-Lib releases did, so data with a large offset and
/// a small spread keeps its precision. At least `period` values are
/// required.
///
/// The output has the same length as the input. The first `period - 1`
/// positions are `NaN` (warm-up).
///
/// Edge cases:
/// - A flat window gives exactly 0, as TA-Lib's does: a deviation within
///   `ZERO_TOLERANCE` (1e-14) of the window's mean is the kernel's rounding
///   (`pyta_core::kernels::is_zero_scaled`), not spread. Bollinger Bands
///   snaps with the same rule.
/// - `k` scales every value; a `k` so large that the product overflows
///   gives infinity.
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `InvalidFloatParameter` when `k` is not a finite number above 0.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn stddev(input: &Series, period: usize, k: f64) -> PytaResult<IndicatorOutput> {
    if period < MIN_PERIOD {
        return Err(PytaError::InvalidParameter {
            name: "period",
            minimum: MIN_PERIOD,
            value: period,
        });
    }

    // Also rejects NaN, for which every comparison is false.
    if !(k > 0.0 && k.is_finite()) {
        return Err(PytaError::InvalidFloatParameter {
            name: "k",
            value: k,
        });
    }

    let values = input.values();
    let length = values.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let (means, mut output) = rolling_mean_std(values, period);

    for (deviation, mean) in output[period - 1..].iter_mut().zip(&means[period - 1..]) {
        *deviation = scaled_deviation(*deviation, *mean, k);
    }

    Ok(IndicatorOutput::new(output))
}
