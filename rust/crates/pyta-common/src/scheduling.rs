//! Costs of the parallel engine, used by the planner.
//!
//! All figures were fitted to the many-dataset runs of `workloads.rs` on a
//! 16-thread Intel i9-9900K (8 cores). Re-fit them on other hardware.

/// Fixed cost of entering the parallel engine (waking Rayon workers and
/// joining their results), in nanoseconds.
pub const BATCH_BASE_OVERHEAD_NS: f64 = 12_000.0;

/// Additional scheduling cost for each request, in nanoseconds.
pub const BATCH_PER_REQUEST_OVERHEAD_NS: f64 = 30.0;

/// The most speed-up a parallel batch is expected to reach, however many
/// workers there are. The kernels are memory-bound and the machine has fewer
/// physical cores than threads, so 16 workers measured only about 4x.
pub const MAX_PARALLEL_SPEEDUP: f64 = 4.2;
