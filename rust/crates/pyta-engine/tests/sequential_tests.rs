use pyta_core::Series;
use pyta_engine::{
    IndicatorKind, IndicatorRequest, IndicatorResult, IndicatorStatus, execute_batch,
    execute_sequential,
};

fn request(kind: IndicatorKind, len: usize, period: usize) -> IndicatorRequest {
    let values = (0..len).map(|i| (i as f64 * 0.7).sin() + 10.0).collect();

    IndicatorRequest::new(kind, Series::new(values).unwrap(), period)
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
