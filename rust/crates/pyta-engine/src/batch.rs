use std::sync::{Arc, OnceLock};

use pyta_core::PytaError;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;

use crate::execution::{execute, execute_direct};
use crate::requests::{IndicatorRequest, IndicatorResult};

/// Upper bound for concurrent batch requests.
///
/// This is a safety cap, not a claim that 32 is optimal for every
/// workload. Benchmarking can guide future tuning.
const MAX_BATCH_CONCURRENCY: usize = 32;

/// Number of workers available to this process, computed once.
///
/// `available_parallelism` re-reads OS and cgroup state on every call
/// (about 18 µs on Linux), which is far too slow for a hot path.
fn available_workers() -> usize {
    static WORKERS: OnceLock<usize> = OnceLock::new();

    *WORKERS.get_or_init(|| {
        std::thread::available_parallelism()
            .map(usize::from)
            .unwrap_or(1)
    })
}

/// Determines the in-flight request limit from available parallelism.
pub(crate) fn batch_concurrency(batch_len: usize) -> usize {
    available_workers()
        .min(MAX_BATCH_CONCURRENCY)
        .min(batch_len)
        .max(1)
}

/// Executes a batch one request at a time on the calling thread.
///
/// Results retain input order and a failed request does not affect the
/// others, exactly like [`execute_batch`]. This is the cheaper choice
/// when `should_parallelize` predicts that concurrency will not pay off.
///
/// This is synchronous CPU work. Do not call it from an async task;
/// run it on a blocking thread instead.
pub fn execute_sequential(requests: &[IndicatorRequest]) -> Vec<IndicatorResult> {
    requests
        .iter()
        .enumerate()
        .map(|(index, request)| match execute_direct(request) {
            Ok(output) => IndicatorResult::success(index, output),
            Err(error) => IndicatorResult::error(index, error),
        })
        .collect()
}

/// Executes a batch with bounded concurrency.
///
/// Requests are processed independently and results retain their
/// original input order. A failed request does not cancel others.
///
/// An empty batch returns an empty vector.
pub async fn execute_batch(requests: Vec<IndicatorRequest>) -> Vec<IndicatorResult> {
    let total = requests.len();

    if total == 0 {
        return Vec::new();
    }

    let permits = Arc::new(Semaphore::new(batch_concurrency(total)));
    let mut tasks = JoinSet::new();

    for (index, request) in requests.into_iter().enumerate() {
        let permits = Arc::clone(&permits);

        tasks.spawn(async move {
            // The semaphore is never closed, so this only fails if
            // that invariant is broken.
            let Ok(_permit) = permits.acquire_owned().await else {
                return IndicatorResult::error(index, PytaError::ExecutionFailed);
            };

            match execute(request).await {
                Ok(output) => IndicatorResult::success(index, output),
                Err(error) => IndicatorResult::error(index, error),
            }
        });
    }

    let mut slots: Vec<Option<IndicatorResult>> = (0..total).map(|_| None).collect();

    // A task that panics or is cancelled leaves its slot empty and
    // does not affect the others.
    while let Some(joined) = tasks.join_next().await {
        if let Ok(result) = joined {
            let index = result.index;
            slots[index] = Some(result);
        }
    }

    slots
        .into_iter()
        .enumerate()
        .map(|(index, slot)| {
            slot.unwrap_or_else(|| IndicatorResult::error(index, PytaError::ExecutionFailed))
        })
        .collect()
}
