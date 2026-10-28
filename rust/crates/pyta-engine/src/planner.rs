use pyta_common::{BATCH_BASE_OVERHEAD_NS, BATCH_PER_REQUEST_OVERHEAD_NS, MAX_PARALLEL_SPEEDUP};

use crate::dispatch::estimated_cost_ns;
use crate::requests::IndicatorRequest;

/// Predicts whether the parallel engine will beat running the requests
/// one after another on the calling thread.
///
/// Sequential time is the sum of the estimated costs. Parallel time is the
/// scheduling overhead plus the larger of the longest single request (which
/// cannot be split) and the total work divided by the achievable speed-up.
/// Parallel execution is chosen only when that is predicted to be faster,
/// so a lone request and small batches stay sequential.
///
/// `workers` is the size of the Rayon pool the batch would run on.
pub fn should_parallelize(requests: &[IndicatorRequest], workers: usize) -> bool {
    requests.len() >= 2 && parallel_is_faster(requests, workers)
}

fn parallel_is_faster(requests: &[IndicatorRequest], workers: usize) -> bool {
    if requests.len() < 2 {
        return false;
    }

    let (total, longest) = requests
        .iter()
        .map(estimated_cost_ns)
        .fold((0.0_f64, 0.0_f64), |(total, longest), cost| {
            (total + cost, longest.max(cost))
        });

    let speedup = (workers.max(1) as f64).min(MAX_PARALLEL_SPEEDUP);
    let overhead = BATCH_BASE_OVERHEAD_NS + BATCH_PER_REQUEST_OVERHEAD_NS * requests.len() as f64;
    let parallel = overhead + longest.max(total / speedup);

    parallel < total
}

#[cfg(test)]
mod tests {
    use pyta_common::PLANNER_TEST_WORKERS;
    use pyta_core::Series;

    use super::parallel_is_faster;
    use crate::requests::{IndicatorKind, IndicatorRequest};

    const WORKERS: usize = PLANNER_TEST_WORKERS;

    fn request(kind: IndicatorKind, len: usize) -> IndicatorRequest {
        IndicatorRequest::new(kind, Series::new(vec![1.0; len]).unwrap(), 14)
    }

    fn many(kind: IndicatorKind, len: usize, count: usize) -> Vec<IndicatorRequest> {
        (0..count).map(|_| request(kind, len)).collect()
    }

    #[test]
    fn empty_and_single_requests_stay_sequential() {
        assert!(!parallel_is_faster(&[], WORKERS));
        assert!(!parallel_is_faster(
            &[request(IndicatorKind::Rsi, 10_000_000)],
            WORKERS
        ));
    }

    #[test]
    fn small_mixed_pair_stays_sequential() {
        let requests = [
            request(IndicatorKind::Sma, 1_000),
            request(IndicatorKind::Rsi, 1_000),
        ];

        assert!(!parallel_is_faster(&requests, WORKERS));
    }

    #[test]
    fn two_small_sma_stay_sequential() {
        assert!(!parallel_is_faster(
            &many(IndicatorKind::Sma, 1_000, 2),
            WORKERS
        ));
    }

    #[test]
    fn two_rsi_at_ten_thousand_go_concurrent() {
        assert!(parallel_is_faster(
            &many(IndicatorKind::Rsi, 10_000, 2),
            WORKERS
        ));
    }

    #[test]
    fn four_mixed_requests_at_ten_thousand_go_concurrent() {
        let requests = [
            request(IndicatorKind::Sma, 10_000),
            request(IndicatorKind::Rsi, 10_000),
            request(IndicatorKind::Sma, 10_000),
            request(IndicatorKind::Rsi, 10_000),
        ];

        assert!(parallel_is_faster(&requests, WORKERS));
    }

    #[test]
    fn two_large_sma_go_concurrent() {
        assert!(parallel_is_faster(
            &many(IndicatorKind::Sma, 1_000_000, 2),
            WORKERS
        ));
    }

    #[test]
    fn few_tiny_requests_stay_sequential() {
        assert!(!parallel_is_faster(
            &many(IndicatorKind::Sma, 100, 10),
            WORKERS
        ));
        assert!(!parallel_is_faster(
            &many(IndicatorKind::Sma, 100, 100),
            WORKERS
        ));
    }

    #[test]
    fn a_thousand_tiny_requests_go_parallel() {
        // Measured: 1,000 SMA of 100 points take 174 µs sequentially and
        // 88 µs on Rayon.
        assert!(parallel_is_faster(
            &many(IndicatorKind::Sma, 100, 1_000),
            WORKERS
        ));
    }

    #[test]
    fn a_single_worker_never_goes_concurrent() {
        assert!(!parallel_is_faster(
            &many(IndicatorKind::Rsi, 1_000_000, 8),
            1
        ));
    }
}
