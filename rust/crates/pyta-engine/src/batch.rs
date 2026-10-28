use pyta_core::PytaError;
use rayon::prelude::*;

use crate::execution::execute_direct;
use crate::requests::{IndicatorRequest, IndicatorResult};

/// Executes a batch one request at a time on the calling thread.
///
/// Results retain input order and a failed request does not affect the
/// others, exactly like [`execute_parallel`]. This is the cheaper choice
/// when `should_parallelize` predicts that concurrency will not pay off.
pub fn execute_sequential(requests: &[IndicatorRequest]) -> Vec<IndicatorResult> {
    requests
        .iter()
        .enumerate()
        .map(|(index, request)| result_of(index, request))
        .collect()
}

/// Executes a batch across Rayon's worker pool.
///
/// Rayon splits the batch across workers and balances the load, so
/// scheduling cost per request is tiny. Results retain input order and a
/// failed request does not affect the others.
///
/// Runs on the current Rayon pool: the global pool, or a specific pool when
/// called inside `ThreadPool::install`.
///
/// This blocks the calling thread until the batch is done. Do not call it
/// from an async task; use [`execute_batch`] there.
pub fn execute_parallel(requests: &[IndicatorRequest]) -> Vec<IndicatorResult> {
    requests
        .par_iter()
        .enumerate()
        .map(|(index, request)| result_of(index, request))
        .collect()
}

/// Executes a batch from async code.
///
/// This is the async front door to [`execute_parallel`]: the whole batch
/// moves to a blocking thread in one hop, so the Tokio runtime is not kept
/// busy and no calculation path exists besides the Rayon one.
///
/// An empty batch returns an empty vector. If the blocking task is lost,
/// every request is reported as `ExecutionFailed`.
pub async fn execute_batch(requests: Vec<IndicatorRequest>) -> Vec<IndicatorResult> {
    let total = requests.len();

    if total == 0 {
        return Vec::new();
    }

    tokio::task::spawn_blocking(move || execute_parallel(&requests))
        .await
        .unwrap_or_else(|_| {
            (0..total)
                .map(|index| IndicatorResult::error(index, PytaError::ExecutionFailed))
                .collect()
        })
}

fn result_of(index: usize, request: &IndicatorRequest) -> IndicatorResult {
    match execute_direct(request) {
        Ok(output) => IndicatorResult::success(index, output),
        Err(error) => IndicatorResult::error(index, error),
    }
}
