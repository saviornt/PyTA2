use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Simple Moving Average (SMA).
///
/// The first `period - 1` output positions are `NaN` (warm-up).
/// Each subsequent position contains the arithmetic mean of the
/// current value and the preceding `period - 1` values.
///
/// The window sum is updated incrementally and recomputed from scratch
/// each time the window advances by a full `period`, which bounds
/// floating-point drift on long series.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn sma(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let divisor = period as f64;
    let mut output = vec![f64::NAN; length];
    let mut running_sum = 0.0_f64;
    let mut until_recompute = 0_usize;

    for index in (period - 1)..length {
        let start = index + 1 - period;

        if until_recompute == 0 {
            running_sum = values[start..=index].iter().sum::<f64>();
            until_recompute = period - 1;
        } else {
            running_sum += values[index] - values[start - 1];
            until_recompute -= 1;
        }

        output[index] = running_sum / divisor;
    }

    Ok(IndicatorOutput::new(output))
}
