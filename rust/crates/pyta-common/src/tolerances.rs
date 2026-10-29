//! Floating-point tolerances shared by kernels.

/// Relative tolerance below which a difference counts as zero: TA-Lib's
/// `TA_EPSILON` (`1e-14`), as used by its `TA_IS_ZERO_SCALED` (TA-Lib
/// 0.8.3, `src/ta_func/ta_utility.h`). `pyta_core::kernels::is_zero_scaled`
/// applies it.
///
/// It is about 90 ULPs of the operands' magnitude, so a difference that is
/// only rounding error (a flat window, a tie) still reads as zero. It sets
/// a TA-Lib convention rather than a speed trade-off: changing it changes
/// results.
pub const ZERO_TOLERANCE: f64 = 1e-14;
