//! Engine execution: ordering, error isolation and the async front door.

use pyta_core::{Columns, PytaError, Series};
use pyta_engine::{IndicatorKind, IndicatorRequest, IndicatorStatus, execute_batch};

const NAN: f64 = f64::NAN;

fn request(kind: IndicatorKind, values: Vec<f64>, period: usize) -> IndicatorRequest {
    IndicatorRequest::new(kind, Series::new(values).unwrap(), period)
}

fn assert_values(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || a == e,
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
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
            assert_values(output.values(), &[NAN, 15.0, 25.0]);
        }
        IndicatorStatus::Error(error) => {
            panic!("Expected SMA success, got {error:?}");
        }
    }

    match &results[1].status {
        IndicatorStatus::Success(output) => {
            assert_values(output.values(), &[NAN, NAN, 100.0, 100.0]);
        }
        IndicatorStatus::Error(error) => {
            panic!("Expected RSI success, got {error:?}");
        }
    }

    match &results[2].status {
        IndicatorStatus::Success(output) => {
            assert_values(output.values(), &[NAN, NAN, 10.0]);
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
        request(IndicatorKind::Rsi, vec![1.0, 2.0, 3.0], 3),
        request(IndicatorKind::Sma, vec![1.0, 2.0, 3.0], 2),
    ];

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 4);
    assert!(results[0].is_error());
    assert!(results[1].is_error());
    assert!(results[2].is_error());
    assert!(results[3].is_success());

    let expected = [
        PytaError::InvalidPeriod,
        PytaError::InvalidPeriod,
        PytaError::InsufficientData {
            required: 4,
            length: 3,
        },
    ];

    for (result, expected_error) in results.iter().zip(expected) {
        match &result.status {
            IndicatorStatus::Error(error) => assert_eq!(*error, expected_error),
            IndicatorStatus::Success(_) => {
                panic!("Expected request {} to fail", result.index);
            }
        }
    }
}

#[tokio::test]
async fn batch_results_keep_original_indices() {
    let requests = (0..200)
        .map(|index| {
            request(
                IndicatorKind::Sma,
                vec![index as f64, index as f64 + 2.0, index as f64 + 4.0],
                2,
            )
        })
        .collect();

    let results = execute_batch(requests).await;

    assert_eq!(results.len(), 200);

    for (expected_index, result) in results.iter().enumerate() {
        assert_eq!(result.index, expected_index);
        assert!(result.is_success());
    }
}

fn columns_request(kind: IndicatorKind, columns: &[&[f64]], period: usize) -> IndicatorRequest {
    let columns = columns
        .iter()
        .map(|values| Series::new(values.to_vec()).unwrap())
        .collect();

    IndicatorRequest::with_columns(kind, Columns::new(columns).unwrap(), period)
}

fn error_of(result: &pyta_engine::IndicatorResult) -> &PytaError {
    match &result.status {
        IndicatorStatus::Error(error) => error,
        IndicatorStatus::Success(_) => panic!("expected request {} to fail", result.index),
    }
}

#[tokio::test]
async fn multi_column_requests_run_beside_single_column_ones() {
    // Typical prices 1, 2, 3, 7: CCI(3) is 100 twice (see the kernel tests).
    let requests = vec![
        columns_request(
            IndicatorKind::Cci,
            &[&[3.0, 6.0, 9.0, 21.0], &[0.0; 4], &[0.0; 4]],
            3,
        ),
        request(IndicatorKind::Sma, vec![10.0, 20.0, 30.0], 2),
        columns_request(
            IndicatorKind::Cci,
            &[&[1.0, 2.0], &[1.0, 2.0], &[1.0, 2.0]],
            0,
        ),
        columns_request(
            IndicatorKind::Cci,
            &[&[1.0, 2.0], &[1.0, 2.0], &[1.0, 2.0]],
            3,
        ),
    ];

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            let values = output.values();
            assert!(values[..2].iter().all(|value| value.is_nan()));
            assert!(values[2..].iter().all(|value| (value - 100.0).abs() < 1e-9));
        }
        IndicatorStatus::Error(error) => panic!("expected CCI success, got {error:?}"),
    }
    assert!(results[1].is_success());
    assert_eq!(*error_of(&results[2]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[3]),
        PytaError::InsufficientData {
            required: 3,
            length: 2,
        }
    );
}

#[tokio::test]
async fn input_with_the_wrong_number_of_columns_is_an_error() {
    let requests = vec![
        request(IndicatorKind::Cci, vec![1.0, 2.0, 3.0], 2),
        columns_request(IndicatorKind::Cci, &[&[1.0, 2.0], &[1.0, 2.0]], 2),
        columns_request(IndicatorKind::Sma, &[&[1.0, 2.0], &[1.0, 2.0]], 2),
        // One column is a valid single-column input.
        columns_request(IndicatorKind::Sma, &[&[10.0, 20.0, 30.0]], 2),
    ];

    let results = execute_batch(requests).await;

    let expected = [(3, 1), (3, 2), (1, 2)];
    for (result, (expected, actual)) in results.iter().zip(expected) {
        assert_eq!(
            *error_of(result),
            PytaError::ColumnCount { expected, actual }
        );
    }
    assert!(results[3].is_success());
}
