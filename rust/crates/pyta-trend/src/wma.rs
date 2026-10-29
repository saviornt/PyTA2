use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// How many windows the running sums slide between rebuilds from scratch:
/// TA-Lib's `TA_WMA` (0.8.3) rebuilds every `8 * period` rows, and so does
/// this kernel, which bounds the drift of the running sums on long series
/// while adding only `1 / 8` of a window's work per row.
const REBUILD_EVERY_PERIODS: usize = 8;

/// Calculates the Weighted Moving Average (WMA), as TA-Lib's `TA_WMA`.
///
/// Each value at index `period - 1` or later is a weighted mean of the
/// `period` values ending there: the oldest weighs 1, the newest `period`,
/// and the weighted sum is divided by `period * (period + 1) / 2`. The first
/// `period - 1` positions are `NaN` (warm-up). A period of 1 returns an
/// exact copy of the input.
///
/// The plain and weighted window sums are updated as the window slides
/// (`weighted - plain + period * newest`, TA-Lib's order) and rebuilt from
/// the window every `8 * period` rows, as TA-Lib does, so rounding cannot
/// accumulate over a long series.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn wma(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    if period == 1 {
        return Ok(IndicatorOutput::new(values.to_vec()));
    }

    let weight = period as f64;
    let divisor = weight * (weight + 1.0) / 2.0;
    let mut output = vec![f64::NAN; length];
    let mut plain_sum = 0.0_f64;
    let mut weighted_sum = 0.0_f64;
    let mut until_rebuild = 0_usize;

    for index in (period - 1)..length {
        let start = index + 1 - period;

        if until_rebuild == 0 {
            (plain_sum, weighted_sum) = window_sums(&values[start..=index]);
            until_rebuild = REBUILD_EVERY_PERIODS.saturating_mul(period) - 1;
        } else {
            // Every weight drops by one (the oldest value's to 0), and the
            // newest value enters with the top weight.
            let newest = values[index];
            weighted_sum = weighted_sum - plain_sum + weight * newest;
            plain_sum += newest - values[start - 1];
            until_rebuild -= 1;
        }

        output[index] = weighted_sum / divisor;
    }

    Ok(IndicatorOutput::new(output))
}

/// The plain sum and the weighted sum (weights 1, 2, ... from the oldest)
/// of one window, oldest first as TA-Lib adds them.
fn window_sums(window: &[f64]) -> (f64, f64) {
    window
        .iter()
        .zip(1_u32..)
        .fold((0.0, 0.0), |(plain, weighted), (value, weight)| {
            (plain + value, weighted + value * f64::from(weight))
        })
}
