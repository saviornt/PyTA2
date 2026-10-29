use pyta_core::kernels::{ema_multiplier, ema_step};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Double Exponential Moving Average (DEMA), as TA-Lib's
/// `TA_DEMA`.
///
/// `EMA1` is the EMA of the input, seeded with the simple average of the
/// first `period` values (TA-Lib's seed); `EMA2` is the EMA of `EMA1`'s
/// values, seeded with the simple average of `EMA1`'s first `period` values.
/// `DEMA = 2 * EMA1 - EMA2`, from index `2 * (period - 1)`; the positions
/// before it are `NaN` (warm-up). A period of 1 returns an exact copy of the
/// input, as TA-Lib does.
///
/// Both EMAs run in one pass, kept here rather than two calls to
/// `kernels::ema` because the fused loop is faster. Every update is the
/// shared `ema_step` and every seed a left-to-right sum divided by the
/// period, as in `kernels::ema_into`, so the result is bit for bit that of
/// one EMA pass after another.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than
/// `2 * period - 1` values.
pub fn dema(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();
    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_mul(2) - 1;

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    if period == 1 {
        return Ok(IndicatorOutput::new(values.to_vec()));
    }

    let k = ema_multiplier(period);
    let ema1_start = period - 1;
    let start = 2 * (period - 1);
    let mut output = vec![f64::NAN; length];

    // EMA1 alone until EMA2 can be seeded; its values are kept in `output`
    // only to seed EMA2, then overwritten by the warm-up.
    let mut ema1 = values[..period].iter().sum::<f64>() / period as f64;
    output[ema1_start] = ema1;
    for (&value, slot) in values[period..=start]
        .iter()
        .zip(&mut output[period..=start])
    {
        ema1 = ema_step(ema1, value, k);
        *slot = ema1;
    }

    let mut ema2 = output[ema1_start..=start].iter().sum::<f64>() / period as f64;
    output[ema1_start..start].fill(f64::NAN);
    output[start] = 2.0 * ema1 - ema2;

    for (&value, slot) in values[start + 1..].iter().zip(&mut output[start + 1..]) {
        ema1 = ema_step(ema1, value, k);
        ema2 = ema_step(ema2, ema1, k);
        *slot = 2.0 * ema1 - ema2;
    }

    Ok(IndicatorOutput::new(output))
}
