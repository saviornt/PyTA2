use std::collections::VecDeque;
use std::sync::Arc;

use tokio::sync::Mutex;

use crate::execution::execute;
use crate::requests::{IndicatorRequest, IndicatorResult};

/// Upper bound for concurrent batch workers.
///
/// This is a safety cap, not a claim that 32 workers are optimal
/// for every workload. Benchmarking can guide future tuning.
const MAX_BATCH_CONCURRENCY: usize = 32;

/// Determines the default worker count based on available parallelism.
fn batch_concurrency(batch_len: usize) -> usize {
    let available = std::thread::available_parallelism()
        .map(usize::from)
        .unwrap_or(1);

    available.min(MAX_BATCH_CONCURRENCY).min(batch_len).max(1)
}

/// Executes a batch with bounded concurrency.
///
/// Requests are processed independently and results retain their
/// original input order. A failed request does not cancel others.
///
/// An empty batch returns an empty vector.
pub async fn execute_batch(
    requests: Vec<IndicatorRequest>,
) -> Vec<IndicatorResult> {
    if requests.is_empty() {
        return Vec::new();
    }

    let concurrency = batch_concurrency(requests.len());

    let jobs = Arc::new(Mutex::new(
        requests.into_iter().enumerate().collect::<VecDeque<_>>(),
    ));

    let result_count = jobs.lock().await.len();
    let results = Arc::new(Mutex::new(
        (0..result_count)
            .map(|_| None)
            .collect::<Vec<Option<IndicatorResult>>>(),
    ));

    let mut workers = Vec::with_capacity(concurrency);

    for _ in 0..concurrency {
        let jobs = Arc::clone(&jobs);
        let results = Arc::clone(&results);

        workers.push(tokio::spawn(async move {
            loop {
                // Lock only long enough to take the next job.
                let job = {
                    let mut queue = jobs.lock().await;
                    queue.pop_front()
                };

                let Some((index, request)) = job else {
                    break;
                };

                let result = match execute(request).await {
                    Ok(output) => IndicatorResult::success(index, output),
                    Err(error) => IndicatorResult::error(index, error),
                };

                results.lock().await[index] = Some(result);
            }
        }));
    }

    // Wait for every worker. A worker failure does not cancel the
    // other workers or the remaining queued requests.
    for worker in workers {
        let _ = worker.await;
    }

    let mut results = results.lock().await;

    // Ensure every input has a corresponding result, even if a
    // worker unexpectedly panicked before recording its result.
    results
        .iter_mut()
        .enumerate()
        .map(|(index, result)| {
            result.take().unwrap_or_else(|| {
                IndicatorResult::error(
                    index,
                    pyta_core::PytaError::ExecutionFailed,
                )
            })
        })
        .collect()
}
