use pyta_core::{PytaError, Series};
use pyta_engine::{
    execute_batch, IndicatorKind, IndicatorRequest, IndicatorStatus,
};

fn request(
    kind: IndicatorKind,
    values: Vec<f64>,
    period: usize,
) -> IndicatorRequest {
    IndicatorRequest::new(kind, Series::new(values).unwrap(), period)
}

#[tokio::test]
async fn empty_batch_returns_no_results() {
    let results = execute_batch(Vec::new()).await;

    assert!(results.is_empty());
}

#[tokio::test]
async fn batch_preserves_input_order() {
    let requests = vec![
        request(IndicatorKind::Sma, vec![10.0, 20.0, 30.0], 2),
        request(IndicatorKind::Rsi, vec![1.0, 2.0, 3.0, 4.0], 2),
        request(IndicatorKind::Sma, vec![5.0, 10.0, 15.0], 3),
    ];

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 3);

    for (expected_index, result) in results.iter().enumerate() {
        assert_eq!(result.index, expected_index);
        assert!(result.is_success());
    }

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            assert_eq!(
                output.values(),
                &[None, Some(15.0), Some(25.0)]
            );
        }
        IndicatorStatus::Error(error) => {
            panic!("Expected SMA success, got {error:?}");
        }
    }

    match &results[1].status {
        IndicatorStatus::Success(output) => {
            assert_eq!(output.len(), 4);
            assert_eq!(output.values()[0], None);
            assert_eq!(output.values()[1], None);
            assert_eq!(output.values()[2], Some(100.0));
        }
        IndicatorStatus::Error(error) => {
            panic!("Expected RSI success, got {error:?}");
        }
    }

    match &results[2].status {
        IndicatorStatus::Success(output) => {
            assert_eq!(output.values(), &[None, None, Some(10.0)]);
        }
        IndicatorStatus::Error(error) => {
            panic!("Expected SMA success, got {error:?}");
        }
    }
}

#[tokio::test]
async fn failed_request_does_not_cancel_other_requests() {
    let requests = vec![
        request(IndicatorKind::Sma, vec![10.0, 20.0, 30.0], 2),
        request(IndicatorKind::Sma, vec![10.0, 20.0, 30.0], 4),
        request(IndicatorKind::Rsi, vec![1.0, 2.0, 3.0, 4.0], 2),
    ];

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 3);

    assert_eq!(results[0].index, 0);
    assert!(results[0].is_success());

    assert_eq!(results[1].index, 1);
    assert!(results[1].is_error());

    match &results[1].status {
        IndicatorStatus::Error(error) => {
            assert_eq!(
                *error,
                PytaError::PeriodExceedsLength {
                    period: 4,
                    length: 3,
                }
            );
        }
        IndicatorStatus::Success(_) => {
            panic!("Expected the invalid SMA request to fail");
        }
    }

    assert_eq!(results[2].index, 2);
    assert!(results[2].is_success());
}

#[tokio::test]
async fn batch_records_multiple_independent_errors() {
    let requests = vec![
        request(IndicatorKind::Sma, vec![1.0, 2.0, 3.0], 0),
        request(IndicatorKind::Rsi, vec![1.0, 2.0, 3.0], 0),
        request(IndicatorKind::Sma, vec![1.0, 2.0, 3.0], 2),
    ];

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 3);
    assert!(results[0].is_error());
    assert!(results[1].is_error());
    assert!(results[2].is_success());

    match &results[0].status {
        IndicatorStatus::Error(error) => {
            assert_eq!(*error, PytaError::InvalidPeriod);
        }
        IndicatorStatus::Success(_) => {
            panic!("Expected the first request to fail");
        }
    }

    match &results[1].status {
        IndicatorStatus::Error(error) => {
            assert_eq!(*error, PytaError::InvalidPeriod);
        }
        IndicatorStatus::Success(_) => {
            panic!("Expected the second request to fail");
        }
    }
}

#[tokio::test]
async fn batch_results_keep_original_indices() {
    let requests = (0..20)
        .map(|index| {
            request(
                IndicatorKind::Sma,
                vec![index as f64, index as f64 + 2.0, index as f64 + 4.0],
                2,
            )
        })
        .collect();

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 20);

    for (expected_index, result) in results.iter().enumerate() {
        assert_eq!(result.index, expected_index);
        assert!(result.is_success());
    }
}
