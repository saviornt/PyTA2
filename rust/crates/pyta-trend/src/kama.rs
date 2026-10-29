use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Slowest smoothing constant, `2 / (30 + 1)`; TA-Lib hard-wires it.
const SLOWEST: f64 = 2.0 / (30.0 + 1.0);
/// Fastest smoothing constant `2 / (2 + 1)` less the slowest one.
const FAST_LESS_SLOW: f64 = 2.0 / (2.0 + 1.0) - SLOWEST;

/// Calculates Kaufman's Adaptive Moving Average (KAMA), as TA-Lib's
/// `TA_KAMA` 0.8.3.
///
/// The efficiency ratio `ER = |close[i] - close[i - period]| / S`, where `S`
/// is the sum of the `period` absolute one-row changes over the same window,
/// sets the smoothing constant `SC = (ER * (2/3 - 2/31) + 2/31)^2`, and
/// `KAMA = prev + SC * (close - prev)`. The previous KAMA is seeded with the
/// value at index `period - 1`, so the first output is at index `period`; the
/// positions before it are `NaN` (warm-up). A period of 1 returns an exact
/// copy of the input from index 0, as TA-Lib does.
///
/// Edge cases follow TA-Lib: `ER` is 1 when `S` is zero or not above the
/// signed net change, and is clamped to 1 (a rolling `S` can drift below the
/// net change). Once `period` one-row changes in a row are exactly zero, the
/// window is flat: `S` is reset to exactly 0 (dropping rounding residue) and
/// `ER` is 1. TA-Lib's source writes its two multiply-adds as `fma`; they
/// are plain here, as in the shared `ema_step`, because `f64::mul_add`
/// without a target FMA feature is a library call that more than doubled
/// the kernel's time. The TA-Lib 0.8.3 wheel's output is still matched bit
/// for bit (both reference fixtures).
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than `period + 1`
/// values (for `period` above 1).
pub fn kama(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();

    if period == 1 {
        return Ok(IndicatorOutput::new(values.to_vec()));
    }

    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_add(1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let mut output = vec![f64::NAN; length];

    // Sum of the first window's one-row changes, and the run of exact zeros
    // at its end.
    let mut sum = 0.0;
    let mut zero_run = 0_usize;
    for pair in values[..=period].windows(2) {
        let change = (pair[0] - pair[1]).abs();
        sum += change;
        zero_run = if change == 0.0 { zero_run + 1 } else { 0 };
    }

    // TA-Lib checks only `S` for the first window, not the zero run.
    let ratio = efficiency_ratio(sum, values[period] - values[0]);
    let mut kama = values[period - 1];
    kama = adapt(kama, values[period], ratio);
    output[period] = kama;

    let rows = values[period + 1..]
        .iter()
        .zip(&values[period..])
        .zip(values[1..].iter().zip(&values[..length - period - 1]));
    for (((&value, &previous), (&trailing, &before_trailing)), slot) in
        rows.zip(&mut output[period + 1..])
    {
        // Remove the change leaving the window, then add the new one
        // (TA-Lib's order).
        sum -= (before_trailing - trailing).abs();
        let change = (value - previous).abs();
        sum += change;
        zero_run = if change == 0.0 { zero_run + 1 } else { 0 };

        let ratio = if zero_run >= period {
            zero_run = period;
            sum = 0.0;
            1.0
        } else {
            efficiency_ratio(sum, value - trailing)
        };
        kama = adapt(kama, value, ratio);
        *slot = kama;
    }

    Ok(IndicatorOutput::new(output))
}

/// `|net / sum|` clamped to 1, and 1 when `sum` is zero or not above the
/// signed `net` change (TA-Lib compares the signed value).
fn efficiency_ratio(sum: f64, net: f64) -> f64 {
    if sum <= 0.0 || sum <= net {
        1.0
    } else {
        (net / sum).abs().min(1.0)
    }
}

/// One KAMA step: `prev + SC * (value - prev)` with
/// `SC = (ratio * (fast - slow) + slow)^2`.
fn adapt(previous: f64, value: f64, ratio: f64) -> f64 {
    let constant = ratio * FAST_LESS_SLOW + SLOWEST;
    (value - previous) * (constant * constant) + previous
}
