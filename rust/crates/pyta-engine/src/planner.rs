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
///
/// Logs the choice and its estimates at DEBUG (target `pyta::planner`).
pub fn should_parallelize(requests: &[IndicatorRequest], workers: usize) -> bool {
    let estimate = estimate(requests, workers);
    let parallel = estimate.parallel_is_faster();

    // The macro checks `log`'s maximum level first, so this costs one atomic
    // load when DEBUG is off, and the arguments are formatted only when on.
    log::debug!(
        target: "pyta::planner",
        "{} {} on {} workers: estimated {:.0} ns sequential, {:.0} ns parallel: {}",
        requests.len(),
        if requests.len() == 1 { "request" } else { "requests" },
        workers,
        estimate.sequential_ns,
        estimate.parallel_ns,
        if parallel { "parallel" } else { "sequential" },
    );

    parallel
}

/// The planner's predicted run times for one batch.
struct Estimate {
    requests: usize,
    sequential_ns: f64,
    parallel_ns: f64,
}

impl Estimate {
    fn parallel_is_faster(&self) -> bool {
        self.requests >= 2 && self.parallel_ns < self.sequential_ns
    }
}

fn estimate(requests: &[IndicatorRequest], workers: usize) -> Estimate {
    let (total, longest) = requests
        .iter()
        .map(estimated_cost_ns)
        .fold((0.0_f64, 0.0_f64), |(total, longest), cost| {
            (total + cost, longest.max(cost))
        });

    let speedup = (workers.max(1) as f64).min(MAX_PARALLEL_SPEEDUP);
    let overhead = BATCH_BASE_OVERHEAD_NS + BATCH_PER_REQUEST_OVERHEAD_NS * requests.len() as f64;

    Estimate {
        requests: requests.len(),
        sequential_ns: total,
        parallel_ns: overhead + longest.max(total / speedup),
    }
}

#[cfg(test)]
fn parallel_is_faster(requests: &[IndicatorRequest], workers: usize) -> bool {
    estimate(requests, workers).parallel_is_faster()
}

#[cfg(test)]
mod tests {
    use pyta_common::PLANNER_TEST_WORKERS;
    use pyta_core::Series;

    use log::Level;

    use super::{parallel_is_faster, should_parallelize};
    use crate::requests::{IndicatorKind, IndicatorRequest};
    use crate::test_log::capture;

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
    fn the_planner_logs_its_choice_at_debug() {
        let small = many(IndicatorKind::Sma, 100, 2);
        let large = many(IndicatorKind::Rsi, 1_000_000, 2);

        let records = capture(|| {
            assert!(!should_parallelize(&small, WORKERS));
            assert!(should_parallelize(&large, WORKERS));
        });

        let [
            (small_level, small_target, small_message),
            (_, _, large_message),
        ] = &records[..]
        else {
            panic!("expected two records, got {records:?}");
        };
        assert_eq!(*small_level, Level::Debug);
        assert_eq!(small_target, "pyta::planner");
        assert!(small_message.starts_with("2 requests on 16 workers: estimated "));
        assert!(small_message.ends_with(": sequential"));
        assert!(large_message.ends_with(": parallel"));
    }

    #[test]
    fn a_single_worker_never_goes_concurrent() {
        assert!(!parallel_is_faster(
            &many(IndicatorKind::Rsi, 1_000_000, 8),
            1
        ));
    }
}
