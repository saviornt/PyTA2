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

/// Average True Range, in nanoseconds per input row; independent of
/// `period` (one true-range pass and one smoothing pass after the seed).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_03-31-27.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 4.344 ms for ATR-14 and 2.508 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 1.73). Confirm with a full
/// `--single --rust --indicator atr`.
pub const ATR_NS_PER_ELEMENT: f64 = 5.2;

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

/// Standard Deviation, in nanoseconds per input row, excluding the
/// per-window pass (see [`STDDEV_NS_PER_WINDOW_VALUE`]): the compensated
/// rolling mean and the multiply.
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_06-18-35.txt`, `--single --rust
/// --quick`, governor `performance`: kernels at 1,000,000 rows took
/// 9.079 ms for STDDEV-5 and 2.735 ms for RSI-14) and a period sweep of the
/// release-built native call at 1,000,000 rows (periods 2 to 200, best of
/// 15, twice): `7.5 + 0.214 * period` ms, less the native call's ~0.55 ms
/// of copying (RSI's native call minus its kernel), so the kernel is about
/// `6.95 + 0.214 * period` ns per row, scaled here by `RSI_NS_PER_ELEMENT`
/// / RSI's kernel time (1.10). Confirm with a full
/// `--single --rust --indicator stddev`.
pub const STDDEV_NS_PER_ELEMENT: f64 = 7.6;

/// Standard Deviation, in nanoseconds per row and per unit of `period`:
/// each row's deviation is a fresh pass over its window, so the cost is
/// O(rows * period). Measured as [`STDDEV_NS_PER_ELEMENT`].
pub const STDDEV_NS_PER_WINDOW_VALUE: f64 = 0.23;

/// Bollinger Bands, in nanoseconds per input row, excluding the per-window
/// pass (see [`BBANDS_NS_PER_WINDOW_VALUE`]): the compensated rolling mean
/// and the two bands.
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_06-37-49.txt`, `--single --rust
/// --quick`, governor `performance`: kernels at 1,000,000 rows took
/// 12.698 ms for BBANDS-20 and 2.535 ms for RSI-14) and a period sweep of
/// the release-built native call at 1,000,000 rows (periods 2 to 200, best
/// of 15, twice): `8.19 + 0.217 * period` ms, so the kernel is about
/// `12.698 - 0.217 * 20 = 8.36` ns per row plus 0.217 per period, scaled
/// here by `RSI_NS_PER_ELEMENT` / RSI's kernel time (1.18). Confirm with a
/// full `--single --rust --indicator bbands`.
pub const BBANDS_NS_PER_ELEMENT: f64 = 9.9;

/// Bollinger Bands, in nanoseconds per row and per unit of `period`: each
/// row's deviation is a fresh pass over its window, as for STDDEV, so the
/// cost is O(rows * period). Measured as [`BBANDS_NS_PER_ELEMENT`].
pub const BBANDS_NS_PER_WINDOW_VALUE: f64 = 0.26;

/// Donchian Channels, in nanoseconds per input row; independent of
/// `period` (the van Herk/Gil-Werman rolling maximum and minimum are O(n)
/// whatever the window).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_06-48-34.txt`, `--single --rust
/// --quick`, governor `performance`: kernels at 1,000,000 rows took
/// 9.798 ms for Donchian-20 and 2.774 ms for RSI-14), scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 3.53). A period sweep of the release-built
/// native call at 1,000,000 rows (best of 15, twice) was flat from period
/// 14 on (12.4 ms at 14, 12.1 at 20, 11.6 at 200) and higher only for tiny
/// windows (14.1 ms at 5, 16.9 at 2: one block per `period` rows), so the
/// constant has no `period` term. Confirm with a full
/// `--single --rust --indicator donchian`.
pub const DONCHIAN_NS_PER_ELEMENT: f64 = 10.6;

/// Exponential Moving Average, in nanoseconds per input element; independent
/// of `period` (one pass after the seed).
///
/// Provisional, from a quick run on 2026-10-28
/// (`benches/results/benchmark_2026-10-28_21-51-12.txt`, `--single --rust
/// --quick`): kernels at 1,000,000 rows took 2.888 ms for EMA-20 and
/// 2.405 ms for RSI-14, scaled here by `RSI_NS_PER_ELEMENT` (3.0 * 1.20).
/// Confirm with a full `--single --rust --indicator ema`.
pub const EMA_NS_PER_ELEMENT: f64 = 3.6;

/// Weighted Moving Average, in nanoseconds per input element; independent
/// of `period` (running sums, rebuilt every `8 * period` rows).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_07-21-17.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 2.353 ms for WMA-30 and 2.638 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 0.89). Confirm with a full
/// `--single --rust --indicator wma`.
pub const WMA_NS_PER_ELEMENT: f64 = 2.7;

/// Double Exponential Moving Average, in nanoseconds per input element;
/// independent of `period` (one fused pass for both EMAs after their seeds).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_07-35-17.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 3.220 ms for DEMA-30 and 2.555 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 1.26). Confirm with a full
/// `--single --rust --indicator dema`.
pub const DEMA_NS_PER_ELEMENT: f64 = 3.8;

/// Triple Exponential Moving Average, in nanoseconds per input element;
/// independent of `period` (one fused pass for the three EMAs after their
/// seeds).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_07-42-44.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 3.535 ms for TEMA-30 and 2.490 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 1.42). Confirm with a full
/// `--single --rust --indicator tema`.
pub const TEMA_NS_PER_ELEMENT: f64 = 4.3;

/// Kaufman Adaptive Moving Average, in nanoseconds per input element;
/// independent of `period` (a rolling sum of one-row changes).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_07-56-32.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 3.627 ms for KAMA-30 and 2.699 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 1.34). Confirm with a full
/// `--single --rust --indicator kama`.
pub const KAMA_NS_PER_ELEMENT: f64 = 4.0;

/// Average Directional Index with +DI and -DI, in nanoseconds per input
/// row; independent of `period` (one fused pass of three Wilder sums).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_11-20-19.txt`, `--single --rust
/// --quick`, governor `performance`): kernels at 1,000,000 rows took
/// 9.388 ms for ADX-14 and 2.660 ms for RSI-14, scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 3.53). Confirm with a full
/// `--single --rust --indicator adx`.
pub const ADX_NS_PER_ELEMENT: f64 = 10.6;

/// Keltner Channels, in nanoseconds per input row; independent of `period`,
/// `atr_period` and `k` (one EMA pass, one true-range and Wilder pass, one
/// band pass).
///
/// Provisional, from a quick run on 2026-10-29
/// (`benches/results/benchmark_2026-10-29_07-04-38.txt`, `--single --rust
/// --quick`, governor `performance`: kernels at 1,000,000 rows took
/// 9.165 ms for Keltner-20/10 and 2.428 ms for RSI-14), scaled here by
/// `RSI_NS_PER_ELEMENT` (3.0 * 3.77). Confirm with a full
/// `--single --rust --indicator keltner`.
pub const KELTNER_NS_PER_ELEMENT: f64 = 11.3;

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
