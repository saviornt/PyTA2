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
/// mean-deviation pass (see [`CCI_NS_PER_WINDOW_VALUE`]): typical price and
/// the compensated running mean.
///
/// Measured 2026-10-28 (full runs `benches/results/benchmark_2026-10-28_17-25-51.txt`
/// for CCI and `_17-31-04` for RSI: kernels at 1,000,000 rows took 9.63 ms
/// at period 14 and 2.50 ms). The kernel at periods 1 to 200 (the native
/// call less its 3.7 ns/row of copying) fits `6.0 + 0.20 * period` ns per
/// row, scaled here by `RSI_NS_PER_ELEMENT` / RSI's kernel time (1.2).
pub const CCI_NS_PER_ELEMENT: f64 = 7.2;

/// Commodity Channel Index, in nanoseconds per row and per unit of
/// `period`: each row's mean deviation is a pass over its window, so the
/// cost is O(rows * period). Measured as [`CCI_NS_PER_ELEMENT`].
pub const CCI_NS_PER_WINDOW_VALUE: f64 = 0.24;

/// Exponential Moving Average, in nanoseconds per input element; independent
/// of `period` (one pass after the seed).
///
/// Provisional, from a quick run on 2026-10-28
/// (`benches/results/benchmark_2026-10-28_21-51-12.txt`, `--single --rust
/// --quick`): kernels at 1,000,000 rows took 2.888 ms for EMA-20 and
/// 2.405 ms for RSI-14, scaled here by `RSI_NS_PER_ELEMENT` (3.0 * 1.20).
/// Confirm with a full `--single --rust --indicator ema`.
pub const EMA_NS_PER_ELEMENT: f64 = 3.6;

/// Moving Average Convergence/Divergence, in nanoseconds per input row for
/// all three outputs; independent of its periods (one fused pass for the
/// three EMAs after their seeds).
///
/// Provisional, from two quick runs on 2026-10-28 after fusing the kernel
/// (`benches/results/benchmark_2026-10-28_22-18-11.txt` and `_22-19-05`,
/// `--single --rust --quick`): the MACD(12, 26, 9) kernel at 1,000,000 rows
/// took 5.649 ms on average against RSI-14's 2.517 ms in the same runs,
/// scaled here by `RSI_NS_PER_ELEMENT` (3.0 * 2.24). Confirm with a full
/// `--single --rust --indicator macd`.
pub const MACD_NS_PER_ELEMENT: f64 = 6.7;
