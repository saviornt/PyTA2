//! Rate of change against the value `period` rows earlier (TA-Lib's
//! `TA_ROC`), shared by ROC (momentum), Volume ROC (volume) and TRIX's last
//! step.

use super::is_zero_scaled;

/// Calculates the rate of change of `values`, in percent, with `NaN` in the
/// first `period` positions (warm-up). See [`rate_of_change_into`].
///
/// The caller guarantees `1 <= period < values.len()`.
#[must_use]
pub fn rate_of_change(values: &[f64], period: usize) -> Vec<f64> {
    debug_assert!(period >= 1 && period < values.len());

    let mut output = vec![f64::NAN; values.len()];
    rate_of_change_into(values, period, &mut output[period..]);
    output
}

/// Writes `(values[i + period] / values[i] - 1) * 100` to `output[i]` for
/// every `i`, TA-Lib's expression and order of operations.
///
/// When the earlier value is zero relative to the current one,
/// `|earlier| <= 1e-14 * |current|` ([`is_zero_scaled`], an exact `0.0`
/// included), the result is `0`. TA-Lib 0.8.3's `TA_ROC` tests only an
/// exact `0.0`, so a tiny non-zero base there gives a huge ratio or `±inf`;
/// here every result is finite (`|ratio| < 1e14` percent). Elsewhere the
/// results are TA-Lib's bit for bit.
///
/// The caller guarantees `1 <= period` and
/// `output.len() == values.len() - period`.
pub fn rate_of_change_into(values: &[f64], period: usize, output: &mut [f64]) {
    debug_assert!(period >= 1 && period <= values.len());
    debug_assert_eq!(output.len(), values.len() - period);

    for ((slot, &current), &earlier) in output.iter_mut().zip(&values[period..]).zip(values) {
        *slot = if is_zero_scaled(earlier, current.abs()) {
            0.0
        } else {
            (current / earlier - 1.0) * 100.0
        };
    }
}
