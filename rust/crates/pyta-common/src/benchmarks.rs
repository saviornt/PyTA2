//! Parameters shared by benchmarks and tests.

/// Input sizes for the engine workload benchmarks.
pub const WORKLOAD_SIZES: [usize; 5] = [100, 1_000, 3_000, 10_000, 1_000_000];

/// Input sizes for the single-call benchmarks.
pub const SINGLE_CALL_SIZES: [usize; 5] = [100, 1_000, 10_000, 100_000, 1_000_000];

/// Dataset counts for the many-dataset batch workloads.
pub const MANY_DATASET_COUNTS: [usize; 3] = [10, 100, 1_000];

/// Points per dataset for the many-dataset batch workloads.
pub const MANY_DATASET_SIZES: [usize; 3] = [100, 1_000, 10_000];

/// Request counts for the few-request batch workloads, where the planner's
/// choice between sequential and parallel is closest.
pub const FEW_REQUEST_COUNTS: [usize; 3] = [3, 5, 10];

/// Points per request for the few-request batch workloads.
pub const FEW_REQUEST_SIZES: [usize; 4] = [100, 1_000, 3_000, 10_000];

/// Input size at or above which benchmarks use fewer samples, because
/// each iteration is slow.
pub const LARGE_INPUT_LEN: usize = 1_000_000;

/// Criterion sample size for inputs below [`LARGE_INPUT_LEN`].
pub const SAMPLE_SIZE: usize = 100;

/// Criterion sample size for inputs at or above [`LARGE_INPUT_LEN`].
pub const LARGE_SAMPLE_SIZE: usize = 20;

/// Worker count assumed by the planner's unit tests, so they do not
/// depend on the machine running them.
pub const PLANNER_TEST_WORKERS: usize = 16;
