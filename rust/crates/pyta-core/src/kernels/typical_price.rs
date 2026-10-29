//! Typical price, `(high + low + close) / 3`.

/// The typical price of one row, `(high + low + close) / 3`, added left to
/// right as TA-Lib's `TA_TYPPRICE` and CCI do.
#[inline]
#[must_use]
pub fn typical_price_at(high: f64, low: f64, close: f64) -> f64 {
    (high + low + close) / 3.0
}

/// Calculates the typical price of every row (CCI, MFI, VWAP).
///
/// The caller guarantees the three slices have equal lengths.
#[must_use]
pub fn typical_price(high: &[f64], low: &[f64], close: &[f64]) -> Vec<f64> {
    debug_assert!(high.len() == close.len() && low.len() == close.len());

    high.iter()
        .zip(low)
        .zip(close)
        .map(|((&high, &low), &close)| typical_price_at(high, low, close))
        .collect()
}
