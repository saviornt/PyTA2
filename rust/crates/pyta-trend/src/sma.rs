/// Calculates the Simple Moving Average (SMA).
///
/// The first `period - 1` output positions are `None`.
/// Each subsequent position contains the arithmetic mean of the
/// current value and the preceding `period - 1` values.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

pub fn sma(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let mut output = vec![None; length];
    let mut window_sum = 0.0;

    for (index, &value) in values.iter().enumerate() {
        window_sum += value;

        if index >= period {
            window_sum -= values[index - period];
        }

        if index >= period - 1 {
            output[index] = Some(window_sum / period as f64);
        }
    }

    Ok(IndicatorOutput::new(output))
}