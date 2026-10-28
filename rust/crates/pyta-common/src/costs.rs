//! Estimated single-threaded cost of each indicator, used by the planner.
//!
//! Relative accuracy matters more than absolute accuracy. Figures come
//! from `workloads.rs` on a 16-core development machine. When adding an
//! indicator, benchmark it, add a constant here, and include any
//! dependence on `period` in its estimate.

/// Simple Moving Average, in nanoseconds per input element.
pub const SMA_NS_PER_ELEMENT: f64 = 1.8;

/// Relative Strength Index, in nanoseconds per input element.
pub const RSI_NS_PER_ELEMENT: f64 = 3.0;

/// Commodity Channel Index, in nanoseconds per input row, excluding the
/// window passes (see [`CCI_NS_PER_WINDOW_VALUE`]).
///
/// Provisional (2026-10-28, quick run): the kernel at 1,000,000 rows and
/// periods 1 to 100, fitted as `3.3 + 1.28 * period` ns and scaled by
/// `RSI_NS_PER_ELEMENT` / RSI's kernel time in the same session.
pub const CCI_NS_PER_ELEMENT: f64 = 3.8;

/// Commodity Channel Index, in nanoseconds per row and per unit of
/// `period`: every row sums its window and takes its mean deviation, so
/// the cost is O(rows * period). Provisional, as [`CCI_NS_PER_ELEMENT`].
pub const CCI_NS_PER_WINDOW_VALUE: f64 = 1.5;
