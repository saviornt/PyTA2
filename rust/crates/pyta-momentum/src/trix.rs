use pyta_core::kernels::{ema_multiplier, ema_step, is_zero_scaled, rate_of_change};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates Jack Hutson's TRIX, as TA-Lib 0.8.3's `TA_TRIX`: the one-row
/// rate of change, in percent, of a triple-smoothed EMA.
///
/// `EMA1` is the EMA of the input, seeded with the simple average of the
/// first `period` values (TA-Lib's seed); `EMA2` is the EMA of `EMA1`'s
/// values and `EMA3` the EMA of `EMA2`'s, each seeded with the simple
/// average of its input's first `period` values. From index
/// `3 * (period - 1) + 1`, `TRIX = (EMA3 / previous EMA3 - 1) * 100`; the
/// positions before it are `NaN` (warm-up). At least `3 * period - 1`
/// values are required. A period of 1 is the one-row rate of change of the
/// input itself, as TA-Lib's is.
///
/// The three EMAs run in one pass, kept here rather than three calls to
/// `kernels::ema` because the fused loop is faster (as TEMA's). Every update
/// is the shared `ema_step` and every seed a left-to-right sum divided by
/// the period, as in `kernels::ema_into`, and the rate of change is
/// `kernels::rate_of_change`'s expression, so the result is bit for bit
/// that of three EMA passes and a rate of change. TA-Lib 0.8.3 writes its
/// EMA update as `fma(beta, previous, k * value)`, so the two differ in the
/// last bits of the EMAs (within `4e-13` relative on its fixtures).
///
/// Edge case: when the previous `EMA3` is zero relative to the current one
/// (`|previous| <= 1e-14 * |EMA3|`, an exact 0 included) the result is 0,
/// so every value is finite. TA-Lib tests only an exact 0, which gives an
/// infinity on a tiny non-zero previous `EMA3`.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than
/// `3 * period - 1` values.
pub fn trix(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();
    // `3 * (period - 1) + 2`. Saturates so a huge period from a direct
    // `_native` call is reported, not overflowed; the public API caps periods
    // far below this.
    let required = period.saturating_mul(3) - 1;

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    if period == 1 {
        // Each EMA of period 1 is a copy of its input.
        return Ok(IndicatorOutput::new(rate_of_change(values, 1)));
    }

    let k = ema_multiplier(period);
    let ema1_start = period - 1;
    let ema2_start = 2 * (period - 1);
    let start = 3 * (period - 1);
    let mut output = vec![f64::NAN; length];

    // EMA1 alone until EMA2 can be seeded, then EMA1 and EMA2 until EMA3 can
    // be. Their values are kept in `output` only to seed the next EMA, then
    // overwritten by the warm-up.
    let mut ema1 = values[..period].iter().sum::<f64>() / period as f64;
    output[ema1_start] = ema1;
    for (&value, slot) in values[period..=ema2_start]
        .iter()
        .zip(&mut output[period..=ema2_start])
    {
        ema1 = ema_step(ema1, value, k);
        *slot = ema1;
    }

    let mut ema2 = output[ema1_start..=ema2_start].iter().sum::<f64>() / period as f64;
    output[ema2_start] = ema2;
    for (&value, slot) in values[ema2_start + 1..=start]
        .iter()
        .zip(&mut output[ema2_start + 1..=start])
    {
        ema1 = ema_step(ema1, value, k);
        ema2 = ema_step(ema2, ema1, k);
        *slot = ema2;
    }

    let mut ema3 = output[ema2_start..=start].iter().sum::<f64>() / period as f64;
    output[ema1_start..=start].fill(f64::NAN);

    for (&value, slot) in values[start + 1..].iter().zip(&mut output[start + 1..]) {
        let previous = ema3;
        ema1 = ema_step(ema1, value, k);
        ema2 = ema_step(ema2, ema1, k);
        ema3 = ema_step(ema3, ema2, k);
        // `kernels::rate_of_change_into`'s expression and zero rule.
        *slot = if is_zero_scaled(previous, ema3.abs()) {
            0.0
        } else {
            (ema3 / previous - 1.0) * 100.0
        };
    }

    Ok(IndicatorOutput::new(output))
}
