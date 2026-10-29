//! TA-Lib's zero tests: the scale-aware one and the fixed band.

use pyta_common::ZERO_TOLERANCE;

/// Whether `value` is zero relative to `scale`: `|value| <= 1e-14 * scale`
/// ([`ZERO_TOLERANCE`]).
///
/// Mirrors TA-Lib 0.8.3's `TA_IS_ZERO_SCALED(v, scale)`, defined in
/// `src/ta_func/ta_utility.h` as `fabs(v) <= (TA_EPSILON*(scale))` with
/// `TA_EPSILON` `1e-14` (issue #107). Use it when `value` is a difference of
/// comparable magnitudes and `scale` their size (TA-Lib passes `|a| + |b|`;
/// CCI passes the window's mean): a fixed band misses ties once the
/// operands grow past about 1. The bound is inclusive and kept as a
/// multiply and compare, TA-Lib's form, so results agree at the boundary.
#[inline]
#[must_use]
pub fn is_zero_scaled(value: f64, scale: f64) -> bool {
    value.abs() <= ZERO_TOLERANCE * scale
}

/// Whether `value` lies strictly inside `(-1e-14, 1e-14)`
/// ([`ZERO_TOLERANCE`]).
///
/// Mirrors TA-Lib 0.8.3's `TA_IS_ZERO(v)`, defined in
/// `src/ta_func/ta_utility.h` as `((-TA_EPSILON)<v)&&(v<TA_EPSILON)`: a fixed
/// band, right only where TA-Lib uses it on a value of known scale (ADX's
/// sum of the two DIs, in percent). Use [`is_zero_scaled`] where TA-Lib
/// does.
#[inline]
#[must_use]
pub fn is_zero(value: f64) -> bool {
    -ZERO_TOLERANCE < value && value < ZERO_TOLERANCE
}
