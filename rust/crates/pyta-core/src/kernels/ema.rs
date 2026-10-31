//! Exponential moving average with a simple-average seed (TA-Lib's
//! `INT_EMA`).

/// The EMA smoothing factor `k = 2 / (period + 1)`, as TA-Lib computes it.
#[inline]
#[must_use]
pub fn ema_multiplier(period: usize) -> f64 {
    2.0 / (period + 1) as f64
}

/// One EMA update: `(value - previous) * k + previous`, the order of
/// operations of TA-Lib's older `INT_EMA`, which every PyTA EMA uses so
/// their results agree bit for bit with each other.
///
/// TA-Lib 0.8.3 writes the update as `fma(beta, previous, k * value)` with
/// `beta = (period - 1) / (period + 1)`; PyTA keeps plain multiplies and
/// adds (the project's policy: agreement with TA-Lib within `1e-9`, not bit
/// for bit), so EMA-based results differ from 0.8.3's in the last bits
/// (EMA at most `2e-16` relative on its reference series).
#[inline]
#[must_use]
pub fn ema_step(previous: f64, value: f64, k: f64) -> f64 {
    (value - previous) * k + previous
}

/// Calculates the EMA of `values`, with `NaN` in the first `period - 1`
/// positions (warm-up).
///
/// The first value, at index `period - 1`, is the simple average of the
/// first `period` values; each later one is [`ema_step`] with
/// [`ema_multiplier`]. A period of 1 returns an exact copy of `values`
/// (`k = 1` would round: `(value - previous) * 1.0 + previous` is not
/// always `value`).
///
/// To cascade (DEMA, TEMA, TRIX), pass the previous EMA's output from its
/// first value on, `&first[period - 1..]`, and shift the result back by the
/// same offset.
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn ema(values: &[f64], period: usize) -> Vec<f64> {
    debug_assert!(period >= 1 && period <= values.len());

    if period == 1 {
        return values.to_vec();
    }

    let mut output = vec![f64::NAN; values.len()];
    ema_into(values, period, period - 1, &mut output);
    output
}

/// Writes the EMA of `values` to `output[start..]`, leaving the positions
/// before `start` as they are.
///
/// The seed, at `start`, is the simple average of the `period` values ending
/// there (a left-to-right sum divided by `period`), so `start` may be later
/// than `period - 1`: MACD seeds its fast EMA at the slow one's start that
/// way. Every later value is [`ema_step`]. The seed follows TA-Lib's
/// `INT_EMA`; the update is not 0.8.3's fused form (see [`ema_step`]), so
/// results agree with TA-Lib 0.8.3 within its reference tolerance rather
/// than bit for bit.
///
/// The caller guarantees `1 <= period <= start + 1 <= values.len()` and
/// `output.len() == values.len()`.
pub fn ema_into(values: &[f64], period: usize, start: usize, output: &mut [f64]) {
    debug_assert!(period >= 1 && period <= start + 1 && start < values.len());
    debug_assert_eq!(output.len(), values.len());

    let k = ema_multiplier(period);
    let mut previous = values[start + 1 - period..=start].iter().sum::<f64>() / period as f64;
    output[start] = previous;

    for (&value, slot) in values[start + 1..].iter().zip(&mut output[start + 1..]) {
        previous = ema_step(previous, value, k);
        *slot = previous;
    }
}
