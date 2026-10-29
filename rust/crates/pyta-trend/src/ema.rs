use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series, kernels};

/// Calculates the Exponential Moving Average (EMA), as TA-Lib's `TA_EMA`.
///
/// The first value, at index `period - 1`, is the simple average of the
/// first `period` values (TA-Lib's default seed). Each later value is
/// `previous + (value - previous) * k`, with `k = 2 / (period + 1)`. The
/// first `period - 1` positions are `NaN` (warm-up). A period of 1 returns
/// an exact copy of the input (TA-Lib rejects it; `k = 1` would round).
///
/// The arithmetic is `pyta_core::kernels::ema`, shared with every indicator
/// that smooths with an EMA.
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

    Ok(IndicatorOutput::new(kernels::ema(values, period)))
}
