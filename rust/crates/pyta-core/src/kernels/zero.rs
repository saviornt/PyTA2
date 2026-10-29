//! TA-Lib's scale-aware zero test.

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
