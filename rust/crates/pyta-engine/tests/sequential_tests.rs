//! Sequential and parallel execution give identical results.

use pyta_core::{Columns, Series};
use pyta_engine::{
    IndicatorKind, IndicatorRequest, IndicatorResult, IndicatorStatus, execute_batch,
    execute_parallel, execute_sequential,
};

fn request(kind: IndicatorKind, len: usize, period: usize) -> IndicatorRequest {
    let values = (0..len).map(|i| (i as f64 * 0.7).sin() + 10.0).collect();

    IndicatorRequest::new(kind, Series::new(values).unwrap(), period)
}

/// A CCI request on high, low and close made from one wave.
fn cci_request(len: usize, period: usize) -> IndicatorRequest {
    let column = |offset: f64| {
        Series::new(
            (0..len)
                .map(|i| (i as f64 * 0.7).sin() + 10.0 + offset)
                .collect(),
        )
        .unwrap()
    };
    let columns = Columns::new(vec![column(0.5), column(-0.5), column(0.0)]).unwrap();

    IndicatorRequest::with_columns(IndicatorKind::Cci, columns, period)
}

fn assert_same(left: &IndicatorResult, right: &IndicatorResult) {
    assert_eq!(left.index, right.index);

    match (&left.status, &right.status) {
        (IndicatorStatus::Success(a), IndicatorStatus::Success(b)) => {
            assert_eq!(a.len(), b.len());

            for (x, y) in a.values().iter().zip(b.values()) {
                assert!((x.is_nan() && y.is_nan()) || x == y);
            }
        }
        (IndicatorStatus::Error(a), IndicatorStatus::Error(b)) => {
            assert_eq!(a, b);
        }
        _ => panic!("statuses differ at index {}", left.index),
    }
}

#[test]
fn sequential_handles_empty_batch() {
    assert!(execute_sequential(&[]).is_empty());
}

#[tokio::test]
async fn sequential_matches_concurrent_results_and_errors() {
    let requests = vec![
        request(IndicatorKind::Sma, 100, 20),
        request(IndicatorKind::Rsi, 100, 14),
        request(IndicatorKind::Sma, 10, 0),
        request(IndicatorKind::Rsi, 5, 14),
        request(IndicatorKind::Sma, 50, 60),
        request(IndicatorKind::Rsi, 1_000, 14),
    ];

    let sequential = execute_sequential(&requests);
    let concurrent = execute_batch(requests).await;

    assert_eq!(sequential.len(), concurrent.len());

    for (left, right) in sequential.iter().zip(&concurrent) {
        assert_same(left, right);
    }

    assert!(sequential[0].is_success());
    assert!(sequential[2].is_error());
    assert!(sequential[3].is_error());
    assert!(sequential[4].is_error());
}

#[test]
fn parallel_matches_sequential_on_a_multi_thread_pool() {
    // Mixed sizes, periods and failures, enough to be split across workers.
    let requests: Vec<_> = (0..64)
        .map(|i| {
            let kind = if i % 2 == 0 {
                IndicatorKind::Sma
            } else {
                IndicatorKind::Rsi
            };
            let period = if i % 7 == 0 { 5_000 } else { 3 + i % 20 };
            request(kind, 200 + 37 * i, period)
        })
        .collect();
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(4)
        .build()
        .unwrap();

    let sequential = execute_sequential(&requests);
    let parallel = pool.install(|| execute_parallel(&requests));

    assert_eq!(sequential.len(), parallel.len());
    for (left, right) in sequential.iter().zip(&parallel) {
        assert_same(left, right);
    }
    assert!(sequential.iter().any(IndicatorResult::is_error));
}

#[test]
fn parallel_matches_sequential_on_multi_column_requests() {
    // CCI mixed with single-column requests, including failures.
    let requests: Vec<_> = (0..48)
        .map(|i| match i % 3 {
            0 => cci_request(100 + 29 * i, if i % 9 == 0 { 5_000 } else { 2 + i % 20 }),
            1 => request(IndicatorKind::Sma, 100 + 29 * i, 3 + i % 20),
            _ => request(IndicatorKind::Rsi, 100 + 29 * i, 3 + i % 20),
        })
        .collect();
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(4)
        .build()
        .unwrap();

    let sequential = execute_sequential(&requests);
    let parallel = pool.install(|| execute_parallel(&requests));

    assert_eq!(sequential.len(), parallel.len());
    for (left, right) in sequential.iter().zip(&parallel) {
        assert_same(left, right);
    }
    assert!(sequential[0].is_error());
    assert!(sequential[3].is_success());
}
