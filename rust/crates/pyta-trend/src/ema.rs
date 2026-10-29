use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Exponential Moving Average (EMA), as TA-Lib's `TA_EMA`.
///
/// The first value, at index `period - 1`, is the simple average of the
/// first `period` values (TA-Lib's default seed). Each later value is
/// `previous + (value - previous) * k`, with `k = 2 / (period + 1)`. The
/// first `period - 1` positions are `NaN` (warm-up). A period of 1 returns
/// the input unchanged.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than `period` values.
pub fn ema(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();

    if period > length {
        return Err(PytaError::InsufficientData {
            required: period,
            length,
        });
    }

    let mut output = vec![f64::NAN; length];
    ema_into(values, period, period - 1, &mut output);

    Ok(IndicatorOutput::new(output))
}

/// Writes the EMA of `values` to `output[start..]`, leaving the positions
/// before `start` as they are.
///
/// The seed, at `start`, is the simple average of the `period` values ending
/// there, so `start` may be later than `period - 1` (MACD seeds its fast EMA
/// where the slow one starts). The arithmetic follows TA-Lib's `INT_EMA`
/// exactly, in the same order, so results match it bit for bit.
///
/// The caller guarantees `1 <= period <= start + 1 <= values.len()` and
/// `output.len() == values.len()`.
pub(crate) fn ema_into(values: &[f64], period: usize, start: usize, output: &mut [f64]) {
    debug_assert!(period >= 1 && period <= start + 1 && start < values.len());
    debug_assert_eq!(output.len(), values.len());

    let k = 2.0 / (period + 1) as f64;
    let mut previous = values[start + 1 - period..=start].iter().sum::<f64>() / period as f64;
    output[start] = previous;

    for (value, slot) in values[start + 1..].iter().zip(&mut output[start + 1..]) {
        previous = (value - previous) * k + previous;
        *slot = previous;
    }
}
