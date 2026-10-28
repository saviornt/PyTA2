//! Size limits.

/// Elements checked per validation block when copying input. A block is
/// small enough to stay in L1 cache between the check and the copy.
pub const VALIDATION_BLOCK_LEN: usize = 64;

/// Largest magnitude an input value may have; `Series` validation rejects
/// anything beyond it.
///
/// Kernels form sums of up to `period` values and differences of two
/// values. With every value at most `1e290` in magnitude, a sum of
/// 2^60 values (the most a `Vec<f64>` can hold) is at most about
/// `1.2e308`, still below `f64::MAX` (about `1.8e308`), so no intermediate
/// result overflows and output `NaN` only ever marks warm-up. Checking
/// `|x| <= MAX_ABS_INPUT` costs the same as checking for finiteness.
pub const MAX_ABS_INPUT: f64 = 1e290;
