//! Wilder's true range (TA-Lib's `TA_TRANGE`).

/// The true range of one row: the largest of `high - low`,
/// `|high - previous_close|` and `|low - previous_close|`.
#[inline]
#[must_use]
pub fn true_range_at(high: f64, low: f64, previous_close: f64) -> f64 {
    (high - low)
        .max((high - previous_close).abs())
        .max((low - previous_close).abs())
}

/// Calculates the true range of every row, with `NaN` at index 0 (it needs
/// the previous close; TA-Lib's lookback is 1).
///
/// High below low is not checked here (the Python layer rejects it), so the
/// result is whatever [`true_range_at`] gives for such a row.
///
/// The caller guarantees the three slices have equal lengths.
#[must_use]
pub fn true_range(high: &[f64], low: &[f64], close: &[f64]) -> Vec<f64> {
    debug_assert!(high.len() == close.len() && low.len() == close.len());

    let mut output = Vec::with_capacity(close.len());
    if close.is_empty() {
        return output;
    }

    output.push(f64::NAN);
    output.extend(
        high[1..]
            .iter()
            .zip(&low[1..])
            .zip(close)
            .map(|((&high, &low), &previous_close)| true_range_at(high, low, previous_close)),
    );
    output
}
