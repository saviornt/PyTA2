//! Chaikin's money-flow multiplier, shared by Accumulation/Distribution and
//! Chaikin Money Flow.

/// Chaikin's money-flow multiplier of one row,
/// `((close - low) - (high - close)) / (high - low)`, in TA-Lib 0.8.3's
/// `TA_AD` order of operations: from -1 (close at the low) to 1 (close at the
/// high).
///
/// When `high - low` is not above 0 (a one-price bar) the multiplier is 0:
/// TA-Lib adds nothing for such a row, and adding `0 * volume` to a running
/// total that is never `-0.0` gives the same bits.
///
/// A close outside its bar is not checked (the Python layer does not either),
/// so the multiplier can then exceed 1 in magnitude, as in TA-Lib.
#[inline]
pub(crate) fn money_flow_multiplier(high: f64, low: f64, close: f64) -> f64 {
    let range = high - low;

    if range > 0.0 {
        (close - low - (high - close)) / range
    } else {
        0.0
    }
}
