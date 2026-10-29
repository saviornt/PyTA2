//! Engine execution: ordering, error isolation and the async front door.

use pyta_core::{Columns, PytaError, Series};
use pyta_engine::{
    IndicatorKind, IndicatorRequest, IndicatorStatus, Params, execute_batch, execute_direct,
};

const NAN: f64 = f64::NAN;

/// The parameters of a one-period indicator.
fn params(kind: IndicatorKind, period: usize) -> Params {
    match kind {
        IndicatorKind::Atr => Params::Atr { period },
        IndicatorKind::Cci => Params::Cci { period },
        IndicatorKind::Donchian => Params::Donchian { period },
        IndicatorKind::Ema => Params::Ema { period },
        IndicatorKind::Rsi => Params::Rsi { period },
        IndicatorKind::Sma => Params::Sma { period },
        IndicatorKind::Wma => Params::Wma { period },
        IndicatorKind::Dema => Params::Dema { period },
        IndicatorKind::Tema => Params::Tema { period },
        IndicatorKind::Bbands => Params::Bbands { period, k: 2.0 },
        IndicatorKind::Stddev => Params::Stddev { period, k: 1.0 },
        IndicatorKind::Keltner => Params::Keltner {
            period,
            atr_period: period,
            k: 2.0,
        },
        IndicatorKind::Macd => panic!("MACD takes three periods"),
    }
}

fn request(kind: IndicatorKind, values: Vec<f64>, period: usize) -> IndicatorRequest {
    IndicatorRequest::new(Series::new(values).unwrap(), params(kind, period))
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

    IndicatorRequest::with_columns(Columns::new(columns).unwrap(), params(kind, period))
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

fn macd_request(values: Vec<f64>, fast: usize, slow: usize, signal: usize) -> IndicatorRequest {
    IndicatorRequest::new(
        Series::new(values).unwrap(),
        Params::Macd { fast, slow, signal },
    )
}

#[test]
fn the_kind_comes_from_the_params() {
    let series = Series::new(vec![1.0, 2.0]).unwrap();
    let cases = [
        (Params::Atr { period: 2 }, IndicatorKind::Atr),
        (Params::Bbands { period: 2, k: 2.0 }, IndicatorKind::Bbands),
        (Params::Cci { period: 2 }, IndicatorKind::Cci),
        (Params::Donchian { period: 2 }, IndicatorKind::Donchian),
        (Params::Ema { period: 2 }, IndicatorKind::Ema),
        (
            Params::Keltner {
                period: 2,
                atr_period: 1,
                k: 2.0,
            },
            IndicatorKind::Keltner,
        ),
        (
            Params::Macd {
                fast: 2,
                slow: 3,
                signal: 1,
            },
            IndicatorKind::Macd,
        ),
        (Params::Rsi { period: 2 }, IndicatorKind::Rsi),
        (Params::Sma { period: 2 }, IndicatorKind::Sma),
        (Params::Stddev { period: 2, k: 1.0 }, IndicatorKind::Stddev),
        (Params::Wma { period: 2 }, IndicatorKind::Wma),
        (Params::Dema { period: 2 }, IndicatorKind::Dema),
        (Params::Tema { period: 2 }, IndicatorKind::Tema),
    ];

    for (params, kind) in cases {
        assert_eq!(params.kind(), kind);
        assert_eq!(IndicatorRequest::new(series.clone(), params).kind(), kind);
    }
}

#[test]
fn ema_runs_through_the_engine() {
    let request = request(IndicatorKind::Ema, vec![1.0, 2.0, 3.0, 4.0, 5.0], 3);

    let output = execute_direct(&request).unwrap();

    assert_values(output.values(), &[NAN, NAN, 2.0, 3.0, 4.0]);
}

#[tokio::test]
async fn wma_runs_through_the_engine_and_reports_its_errors() {
    // Period 3, weights 1, 2, 3 over 6: (1 + 4 + 9) / 6, then (2 + 6 + 12) / 6
    // and (3 + 8 + 15) / 6.
    let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
    let requests = vec![
        request(IndicatorKind::Wma, values.clone(), 3),
        request(IndicatorKind::Wma, values.clone(), 0),
        request(IndicatorKind::Wma, values, 6),
    ];

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            assert_values(
                output.values(),
                &[NAN, NAN, 14.0 / 6.0, 20.0 / 6.0, 26.0 / 6.0],
            );
        }
        IndicatorStatus::Error(error) => panic!("expected WMA success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::PeriodExceedsLength {
            period: 6,
            length: 5,
        }
    );
}

#[tokio::test]
async fn dema_runs_through_the_engine_and_reports_its_errors() {
    // Period 3 on a ramp: DEMA has no lag, so from index 4 it is the price.
    let values: Vec<f64> = (1..=6).map(f64::from).collect();
    let requests = vec![
        request(IndicatorKind::Dema, values.clone(), 3),
        request(IndicatorKind::Dema, values.clone(), 0),
        request(IndicatorKind::Dema, values, 4),
    ];

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            assert_values(output.values(), &[NAN, NAN, NAN, NAN, 5.0, 6.0]);
        }
        IndicatorStatus::Error(error) => panic!("expected DEMA success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 7,
            length: 6,
        }
    );
}

#[tokio::test]
async fn tema_runs_through_the_engine_and_reports_its_errors() {
    // Period 3 on a ramp: TEMA has no lag, so from index 6 it is the price.
    let values: Vec<f64> = (1..=8).map(f64::from).collect();
    let requests = vec![
        request(IndicatorKind::Tema, values.clone(), 3),
        request(IndicatorKind::Tema, values.clone(), 0),
        request(IndicatorKind::Tema, values, 4),
    ];

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            assert_values(output.values(), &[NAN, NAN, NAN, NAN, NAN, NAN, 7.0, 8.0]);
        }
        IndicatorStatus::Error(error) => panic!("expected TEMA success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 10,
            length: 8,
        }
    );
}

#[test]
fn macd_runs_through_the_engine_with_three_outputs() {
    // A ramp: the EMAs lag by (period - 1) / 2, so MACD(2, 4, 2) is 1.
    let ramp = (1..=8).map(f64::from).collect();

    let output = execute_direct(&macd_request(ramp, 2, 4, 2)).unwrap();

    let [line, signal, hist] = output.outputs() else {
        panic!("expected three outputs, got {}", output.output_count());
    };
    assert!(line[..3].iter().all(|value| value.is_nan()));
    assert!(line[3..].iter().all(|value| (value - 1.0).abs() < 1e-12));
    assert!(signal[..4].iter().all(|value| value.is_nan()));
    assert!(signal[4..].iter().all(|value| (value - 1.0).abs() < 1e-12));
    assert!(hist[..4].iter().all(|value| value.is_nan()));
    assert!(hist[4..].iter().all(|value| value.abs() < 1e-12));
}

#[tokio::test]
async fn ema_and_macd_errors_are_isolated_in_a_batch() {
    let requests = vec![
        request(IndicatorKind::Ema, vec![1.0, 2.0, 3.0], 0),
        request(IndicatorKind::Ema, vec![1.0, 2.0, 3.0], 4),
        macd_request(vec![1.0; 40], 1, 26, 9),
        macd_request(vec![1.0; 40], 12, 26, 0),
        macd_request(vec![1.0; 33], 12, 26, 9),
        macd_request(vec![1.0; 34], 12, 26, 9),
        request(IndicatorKind::Ema, vec![1.0, 2.0, 3.0], 3),
        // Two columns are not a MACD input.
        IndicatorRequest::with_columns(
            Columns::new(vec![
                Series::new(vec![1.0; 40]).unwrap(),
                Series::new(vec![1.0; 40]).unwrap(),
            ])
            .unwrap(),
            Params::Macd {
                fast: 12,
                slow: 26,
                signal: 9,
            },
        ),
    ];

    let results = execute_batch(requests).await;

    let expected = [
        PytaError::InvalidPeriod,
        PytaError::InsufficientData {
            required: 4,
            length: 3,
        },
        PytaError::InvalidParameter {
            name: "fast",
            minimum: 2,
            value: 1,
        },
        PytaError::InvalidParameter {
            name: "signal",
            minimum: 1,
            value: 0,
        },
        PytaError::InsufficientData {
            required: 34,
            length: 33,
        },
    ];
    for (result, expected) in results.iter().zip(expected) {
        assert_eq!(*error_of(result), expected);
    }
    match &results[5].status {
        IndicatorStatus::Success(output) => assert_eq!(output.output_count(), 3),
        IndicatorStatus::Error(error) => panic!("expected MACD success, got {error:?}"),
    }
    assert!(results[6].is_success());
    assert_eq!(
        *error_of(&results[7]),
        PytaError::ColumnCount {
            expected: 1,
            actual: 2,
        }
    );
}

#[tokio::test]
async fn atr_runs_through_the_engine_and_reports_its_errors() {
    // True ranges 3, 1, 4, 2 from row 1: ATR(2) is 2, 3, 2.5 (see the
    // kernel tests).
    let high: &[f64] = &[11.0, 12.0, 11.0, 14.0, 13.0];
    let low: &[f64] = &[9.0, 9.0, 10.0, 12.0, 11.0];
    let close: &[f64] = &[10.0, 11.0, 10.0, 13.0, 12.0];
    let requests = vec![
        columns_request(IndicatorKind::Atr, &[high, low, close], 2),
        columns_request(IndicatorKind::Atr, &[high, low, close], 0),
        columns_request(IndicatorKind::Atr, &[high, low, close], 5),
        request(IndicatorKind::Atr, close.to_vec(), 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    assert_values(direct.values(), &[NAN, NAN, 2.0, 3.0, 2.5]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => assert_values(output.values(), direct.values()),
        IndicatorStatus::Error(error) => panic!("expected ATR success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 6,
            length: 5,
        }
    );
    assert_eq!(
        *error_of(&results[3]),
        PytaError::ColumnCount {
            expected: 3,
            actual: 1,
        }
    );
}

#[tokio::test]
async fn stddev_runs_through_the_engine_and_reports_its_errors() {
    // Windows of 2: deviations 1, 2, 0.5 (half the gap), times k = 2.
    let values = vec![1.0, 3.0, 7.0, 8.0];
    let stddev = |values: Vec<f64>, period: usize, k: f64| {
        IndicatorRequest::new(Series::new(values).unwrap(), Params::Stddev { period, k })
    };
    let requests = vec![
        stddev(values.clone(), 2, 2.0),
        stddev(values.clone(), 1, 1.0),
        stddev(values.clone(), 2, 0.0),
        stddev(values.clone(), 2, f64::NAN),
        stddev(values.clone(), 5, 1.0),
        IndicatorRequest::with_columns(
            Columns::new(vec![
                Series::new(values.clone()).unwrap(),
                Series::new(values).unwrap(),
            ])
            .unwrap(),
            Params::Stddev { period: 2, k: 1.0 },
        ),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    assert_values(direct.values(), &[NAN, 2.0, 4.0, 1.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => assert_values(output.values(), direct.values()),
        IndicatorStatus::Error(error) => panic!("expected STDDEV success, got {error:?}"),
    }
    assert_eq!(
        *error_of(&results[1]),
        PytaError::InvalidParameter {
            name: "period",
            minimum: 2,
            value: 1,
        }
    );
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InvalidFloatParameter {
            name: "k",
            value: 0.0,
        }
    );
    assert!(matches!(
        *error_of(&results[3]),
        PytaError::InvalidFloatParameter { name: "k", value } if value.is_nan()
    ));
    assert_eq!(
        *error_of(&results[4]),
        PytaError::PeriodExceedsLength {
            period: 5,
            length: 4,
        }
    );
    assert_eq!(
        *error_of(&results[5]),
        PytaError::ColumnCount {
            expected: 1,
            actual: 2,
        }
    );
}

#[tokio::test]
async fn bbands_runs_through_the_engine_with_three_outputs_and_reports_its_errors() {
    // Windows of 2: means 2, 5, 7.5 and deviations 1, 2, 0.5, times k = 2.
    let values = vec![1.0, 3.0, 7.0, 8.0];
    let bbands = |values: Vec<f64>, period: usize, k: f64| {
        IndicatorRequest::new(Series::new(values).unwrap(), Params::Bbands { period, k })
    };
    let requests = vec![
        bbands(values.clone(), 2, 2.0),
        bbands(values.clone(), 1, 2.0),
        bbands(values.clone(), 2, -1.0),
        bbands(values, 5, 2.0),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [upper, middle, lower] = direct.outputs() else {
        panic!("expected three outputs, got {}", direct.output_count());
    };
    assert_values(upper, &[NAN, 4.0, 9.0, 8.5]);
    assert_values(middle, &[NAN, 2.0, 5.0, 7.5]);
    assert_values(lower, &[NAN, 0.0, 1.0, 6.5]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected BBANDS success, got {error:?}"),
    }
    assert_eq!(
        *error_of(&results[1]),
        PytaError::InvalidParameter {
            name: "period",
            minimum: 2,
            value: 1,
        }
    );
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InvalidFloatParameter {
            name: "k",
            value: -1.0,
        }
    );
    assert_eq!(
        *error_of(&results[3]),
        PytaError::PeriodExceedsLength {
            period: 5,
            length: 4,
        }
    );
}

#[tokio::test]
async fn donchian_runs_through_the_engine_with_three_outputs_and_reports_its_errors() {
    // Windows of 2: highest highs 12, 12, 14, lowest lows 9, 9, 10.
    let high: &[f64] = &[11.0, 12.0, 11.0, 14.0];
    let low: &[f64] = &[9.0, 9.0, 10.0, 12.0];
    let requests = vec![
        columns_request(IndicatorKind::Donchian, &[high, low], 2),
        columns_request(IndicatorKind::Donchian, &[high, low], 0),
        columns_request(IndicatorKind::Donchian, &[high, low], 5),
        request(IndicatorKind::Donchian, high.to_vec(), 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [upper, middle, lower] = direct.outputs() else {
        panic!("expected three outputs, got {}", direct.output_count());
    };
    assert_values(upper, &[NAN, 12.0, 12.0, 14.0]);
    assert_values(middle, &[NAN, 10.5, 10.5, 12.0]);
    assert_values(lower, &[NAN, 9.0, 9.0, 10.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected Donchian success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::PeriodExceedsLength {
            period: 5,
            length: 4,
        }
    );
    assert_eq!(
        *error_of(&results[3]),
        PytaError::ColumnCount {
            expected: 2,
            actual: 1,
        }
    );
}

#[tokio::test]
async fn keltner_runs_through_the_engine_with_three_outputs_and_reports_its_errors() {
    // period 1 and atr_period 1: the middle is close and the ATR is the true
    // range (2 on rows 1-3), so the bands are close +/- 4 from row 1.
    let high: &[f64] = &[11.0, 12.0, 13.0, 12.0];
    let low: &[f64] = &[9.0, 10.0, 11.0, 10.0];
    let close: &[f64] = &[10.0, 11.0, 12.0, 11.0];
    let requests = vec![
        columns_request(IndicatorKind::Keltner, &[high, low, close], 1),
        columns_request(IndicatorKind::Keltner, &[high, low, close], 0),
        columns_request(IndicatorKind::Keltner, &[high, low, close], 5),
        request(IndicatorKind::Keltner, close.to_vec(), 1),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [upper, middle, lower] = direct.outputs() else {
        panic!("expected three outputs, got {}", direct.output_count());
    };
    assert_values(upper, &[NAN, 15.0, 16.0, 15.0]);
    assert_values(middle, close);
    assert_values(lower, &[NAN, 7.0, 8.0, 7.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected Keltner success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 6,
            length: 4,
        }
    );
    assert_eq!(
        *error_of(&results[3]),
        PytaError::ColumnCount {
            expected: 3,
            actual: 1,
        }
    );
}
