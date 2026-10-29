use pyta_core::kernels::rolling_mean_std;
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::deviation::scaled_deviation;

/// The smallest `period` Bollinger Bands accepts (TA-Lib's lower bound): a
/// window of one value has no spread.
const MIN_PERIOD: usize = 2;

/// Calculates Bollinger Bands (BBANDS), following TA-Lib's `TA_BBANDS` with
/// a simple moving average: the middle band is the mean of the last `period`
/// values, and the upper and lower bands lie `k` population standard
/// deviations (dividing by `period`) of the same window above and below it.
///
/// One pass of `pyta_core::kernels::rolling_mean_std` gives both the mean and
/// the deviation; the deviation is centred on the window's own mean, so data
/// with a large offset and a small spread keeps its precision. At least
/// `period` values are required.
///
/// Returns three outputs, in order: upper, middle, lower. Each has the same
/// length as the input, and the first `period - 1` positions of each are
/// `NaN` (warm-up).
///
/// Edge cases:
/// - A flat window gives three equal bands, as TA-Lib's does: its deviation
///   is snapped to exactly 0 by the rule STDDEV uses.
/// - One `k` serves both bands (TA-Lib's `nbdevup` and `nbdevdn` equal).
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `InvalidFloatParameter` when `k` is not a finite number above 0.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn bbands(input: &Series, period: usize, k: f64) -> PytaResult<IndicatorOutput> {
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

    // The deviations' buffer becomes the upper band and the means the
    // middle, so only the lower band is a new allocation.
    let (middle, mut upper) = rolling_mean_std(values, period);
    let mut lower = vec![f64::NAN; length];

    for ((high, low), &mean) in upper[period - 1..]
        .iter_mut()
        .zip(&mut lower[period - 1..])
        .zip(&middle[period - 1..])
    {
        let width = scaled_deviation(*high, mean, k);
        *high = mean + width;
        *low = mean - width;
    }

    IndicatorOutput::with_outputs(vec![upper, middle, lower])
}
