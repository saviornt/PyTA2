//! Tuning of kernel inner loops.
//!
//! When a kernel sums a window, one running total makes every addition wait
//! for the previous one; several independent totals (lanes) let the CPU
//! overlap them. More lanes pay off on long windows, but on short ones the
//! leftover values that do not fill a lane, and adding the lanes together,
//! cost more than they save.
//!
//! Measured on the CCI kernel (i9-9900K, 2026-10-28, 1,000,000 rows, native
//! call): 2 lanes against 4 took 13.3 vs 14.7 ms at period 14, 14.7 vs
//! 14.6 ms at period 20, 23.3 vs 20.0 ms at 50, and 39.4 vs 29.7 ms at 100;
//! 1 lane (101 µs) and 8 lanes (91 µs) were both slower than 2 (77 µs) at
//! period 14 on 10,000 rows (Criterion kernel, quick runs).

/// Lanes for summing a window shorter than [`LONG_WINDOW_LEN`].
pub const SHORT_WINDOW_SUM_LANES: usize = 2;

/// Lanes for summing a window of at least [`LONG_WINDOW_LEN`] values.
pub const LONG_WINDOW_SUM_LANES: usize = 4;

/// The window length from which [`LONG_WINDOW_SUM_LANES`] is used; the two
/// lane counts measured about equal here.
pub const LONG_WINDOW_LEN: usize = 20;
