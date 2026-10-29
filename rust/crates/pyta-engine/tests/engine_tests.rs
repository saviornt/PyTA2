//! Engine execution: ordering, error isolation and the async front door.

use pyta_core::{Columns, PytaError, Series};
use pyta_engine::{
    IndicatorKind, IndicatorRequest, IndicatorStatus, Params, execute_batch, execute_direct,
};

const NAN: f64 = f64::NAN;

/// The parameters of a one-period indicator.
fn params(kind: IndicatorKind, period: usize) -> Params {
    match kind {
        IndicatorKind::Adx => Params::Adx { period },
        IndicatorKind::Aroon => Params::Aroon { period },
        IndicatorKind::Atr => Params::Atr { period },
        IndicatorKind::Cci => Params::Cci { period },
        IndicatorKind::Donchian => Params::Donchian { period },
        IndicatorKind::Ema => Params::Ema { period },
        IndicatorKind::Ichimoku => Params::Ichimoku {
            tenkan: period,
            kijun: period,
            senkou: period,
        },
        IndicatorKind::Roc => Params::Roc { period },
        IndicatorKind::Rsi => Params::Rsi { period },
        IndicatorKind::Sma => Params::Sma { period },
        IndicatorKind::Willr => Params::Willr { period },
        IndicatorKind::Wma => Params::Wma { period },
        IndicatorKind::Dema => Params::Dema { period },
        IndicatorKind::Tema => Params::Tema { period },
        IndicatorKind::Kama => Params::Kama { period },
        IndicatorKind::Bbands => Params::Bbands { period, k: 2.0 },
        IndicatorKind::Stddev => Params::Stddev { period, k: 1.0 },
        IndicatorKind::Stoch => Params::Stoch {
            k: period,
            k_smooth: period,
            d: period,
        },
        IndicatorKind::Keltner => Params::Keltner {
            period,
            atr_period: period,
            k: 2.0,
        },
        IndicatorKind::Macd => panic!("MACD takes three periods"),
        IndicatorKind::Sar => panic!("SAR takes no period"),
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
        (Params::Adx { period: 2 }, IndicatorKind::Adx),
        (Params::Aroon { period: 2 }, IndicatorKind::Aroon),
        (Params::Atr { period: 2 }, IndicatorKind::Atr),
        (Params::Bbands { period: 2, k: 2.0 }, IndicatorKind::Bbands),
        (Params::Cci { period: 2 }, IndicatorKind::Cci),
        (Params::Donchian { period: 2 }, IndicatorKind::Donchian),
        (Params::Ema { period: 2 }, IndicatorKind::Ema),
        (Params::Willr { period: 2 }, IndicatorKind::Willr),
        (Params::Roc { period: 1 }, IndicatorKind::Roc),
        (
            Params::Ichimoku {
                tenkan: 1,
                kijun: 2,
                senkou: 2,
            },
            IndicatorKind::Ichimoku,
        ),
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
        (
            Params::Sar {
                acceleration: 0.02,
                maximum: 0.2,
            },
            IndicatorKind::Sar,
        ),
        (Params::Sma { period: 2 }, IndicatorKind::Sma),
        (Params::Stddev { period: 2, k: 1.0 }, IndicatorKind::Stddev),
        (
            Params::Stoch {
                k: 2,
                k_smooth: 1,
                d: 1,
            },
            IndicatorKind::Stoch,
        ),
        (Params::Wma { period: 2 }, IndicatorKind::Wma),
        (Params::Dema { period: 2 }, IndicatorKind::Dema),
        (Params::Tema { period: 2 }, IndicatorKind::Tema),
        (Params::Kama { period: 2 }, IndicatorKind::Kama),
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

#[tokio::test]
async fn kama_runs_through_the_engine_and_reports_its_errors() {
    // Period 2 on a flat series: seeded with the price, KAMA stays on it.
    let values = vec![5.0; 4];
    let requests = vec![
        request(IndicatorKind::Kama, values.clone(), 2),
        request(IndicatorKind::Kama, values.clone(), 0),
        request(IndicatorKind::Kama, values, 4),
    ];

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            assert_values(output.values(), &[NAN, NAN, 5.0, 5.0]);
        }
        IndicatorStatus::Error(error) => panic!("expected KAMA success, got {error:?}"),
    }
    assert_eq!(*error_of(&results[1]), PytaError::InvalidPeriod);
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 5,
            length: 4,
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
async fn aroon_runs_through_the_engine_with_three_outputs_and_reports_its_errors() {
    // Period 2 (factor 50), windows of 3 rows. Row 2: highest high on row
    // 1, lowest low on row 0; row 3: both on row 3.
    let high: &[f64] = &[10.0, 12.0, 11.0, 13.0];
    let low: &[f64] = &[7.0, 9.0, 9.5, 8.0];
    let requests = vec![
        columns_request(IndicatorKind::Aroon, &[high, low], 2),
        columns_request(IndicatorKind::Aroon, &[high, low], 1),
        columns_request(IndicatorKind::Aroon, &[high, low], 4),
        request(IndicatorKind::Aroon, high.to_vec(), 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [up, down, osc] = direct.outputs() else {
        panic!("expected three outputs, got {}", direct.output_count());
    };
    assert_values(up, &[NAN, NAN, 50.0, 100.0]);
    assert_values(down, &[NAN, NAN, 0.0, 100.0]);
    assert_values(osc, &[NAN, NAN, 50.0, 0.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected Aroon success, got {error:?}"),
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
        PytaError::InsufficientData {
            required: 5,
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
async fn roc_runs_through_the_engine_and_reports_its_errors() {
    // Period 2: (12 / 10 - 1) * 100, (11 / 0 -> 0), (15 / 12 - 1) * 100.
    let values = vec![10.0, 0.0, 12.0, 11.0, 15.0];
    let requests = vec![
        request(IndicatorKind::Roc, values.clone(), 2),
        request(IndicatorKind::Roc, values.clone(), 0),
        request(IndicatorKind::Roc, values.clone(), 5),
        columns_request(IndicatorKind::Roc, &[&values, &values], 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    assert_values(
        direct.values(),
        &[
            NAN,
            NAN,
            (12.0 / 10.0 - 1.0) * 100.0,
            0.0,
            (15.0 / 12.0 - 1.0) * 100.0,
        ],
    );

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => assert_values(output.values(), direct.values()),
        IndicatorStatus::Error(error) => panic!("expected ROC success, got {error:?}"),
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
            expected: 1,
            actual: 2,
        }
    );
}

#[tokio::test]
async fn willr_runs_through_the_engine_and_reports_its_errors() {
    // Period 2. Row 1: highest 12, lowest 9, close 11 -> -100/3; row 2:
    // highest 13, lowest 10, close 13 -> -0; row 3: highest 13, lowest 8,
    // close 8 -> -100.
    let high: &[f64] = &[10.0, 12.0, 13.0, 11.0];
    let low: &[f64] = &[9.0, 10.0, 11.0, 8.0];
    let close: &[f64] = &[9.5, 11.0, 13.0, 8.0];
    let requests = vec![
        columns_request(IndicatorKind::Willr, &[high, low, close], 2),
        columns_request(IndicatorKind::Willr, &[high, low, close], 1),
        columns_request(IndicatorKind::Willr, &[high, low, close], 5),
        request(IndicatorKind::Willr, close.to_vec(), 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    assert_values(direct.values(), &[NAN, 1.0 / 3.0 * -100.0, -0.0, -100.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => assert_values(output.values(), direct.values()),
        IndicatorStatus::Error(error) => panic!("expected Williams %R success, got {error:?}"),
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
        PytaError::PeriodExceedsLength {
            period: 5,
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

/// A Parabolic SAR request on high and low.
fn sar_request(columns: &[&[f64]], acceleration: f64, maximum: f64) -> IndicatorRequest {
    let columns = columns
        .iter()
        .map(|values| Series::new(values.to_vec()).unwrap())
        .collect();

    IndicatorRequest::with_columns(
        Columns::new(columns).unwrap(),
        Params::Sar {
            acceleration,
            maximum,
        },
    )
}

#[tokio::test]
async fn sar_runs_through_the_engine_and_reports_its_errors() {
    // Acceleration 0.25, maximum 0.5 (exact in binary): long from SAR 8,
    // EP 12; row 2 writes 9, and row 3's low 9 == SAR reverses to the EP 14
    // raised to the row's high 15 (see the kernel tests).
    let high: &[f64] = &[10.0, 12.0, 14.0, 15.0];
    let low: &[f64] = &[8.0, 9.0, 10.0, 9.0];
    let requests = vec![
        sar_request(&[high, low], 0.25, 0.5),
        sar_request(&[high, low], 0.3, 0.2),
        sar_request(&[high, low], 0.02, 0.0),
        sar_request(&[&high[..1], &low[..1]], 0.02, 0.2),
        IndicatorRequest::new(
            Series::new(high.to_vec()).unwrap(),
            Params::Sar {
                acceleration: 0.02,
                maximum: 0.2,
            },
        ),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    assert_eq!(direct.output_count(), 1);
    assert_values(direct.values(), &[NAN, 8.0, 9.0, 15.0]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => assert_values(output.values(), direct.values()),
        IndicatorStatus::Error(error) => panic!("expected SAR success, got {error:?}"),
    }
    assert_eq!(
        *error_of(&results[1]),
        PytaError::ParametersOutOfOrder {
            lower: "acceleration",
            lower_value: 0.3,
            upper: "maximum",
            upper_value: 0.2,
        }
    );
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InvalidFloatParameter {
            name: "maximum",
            value: 0.0,
        }
    );
    assert_eq!(
        *error_of(&results[3]),
        PytaError::InsufficientData {
            required: 2,
            length: 1,
        }
    );
    assert_eq!(
        *error_of(&results[4]),
        PytaError::ColumnCount {
            expected: 2,
            actual: 1,
        }
    );
}

#[tokio::test]
async fn adx_runs_through_the_engine_with_three_outputs_and_reports_its_errors() {
    // Period 2: row 1 seeds +DM 2 and TR 3; row 2 gives sums 2 and 4.5
    // (+DI 100 * 2 / 4.5, -DI 0, DX 100); row 3 gives +1, -2 and 6.25
    // (+DI 16, -DI 32, DX 100 / 3), so the first ADX is their mean.
    let high: &[f64] = &[10.0, 12.0, 13.0, 12.0];
    let low: &[f64] = &[8.0, 9.0, 10.0, 8.0];
    let close: &[f64] = &[9.0, 11.0, 12.0, 9.0];
    let requests = vec![
        columns_request(IndicatorKind::Adx, &[high, low, close], 2),
        columns_request(IndicatorKind::Adx, &[high, low, close], 1),
        columns_request(IndicatorKind::Adx, &[high, low, close], 3),
        request(IndicatorKind::Adx, close.to_vec(), 2),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [adx, plus_di, minus_di] = direct.outputs() else {
        panic!("expected three outputs, got {}", direct.output_count());
    };
    // Written in the kernel's order of operations, so they compare exactly.
    let (plus, minus) = (100.0 * (1.0 / 6.25), 100.0 * (2.0 / 6.25));
    let dx = 100.0 * ((minus - plus) / (minus + plus));
    assert_values(adx, &[NAN, NAN, NAN, (100.0 + dx) / 2.0]);
    assert_values(plus_di, &[NAN, NAN, 100.0 * (2.0 / 4.5), plus]);
    assert_values(minus_di, &[NAN, NAN, 0.0, minus]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected ADX success, got {error:?}"),
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
#[tokio::test]
async fn ichimoku_runs_through_the_engine_with_five_outputs_and_reports_its_errors() {
    // tenkan 1, kijun 2, senkou 3: midpoints of 1-, 2- and 3-row windows.
    let high: &[f64] = &[11.0, 12.0, 13.0, 12.0];
    let low: &[f64] = &[9.0, 10.0, 11.0, 8.0];
    let close: &[f64] = &[10.0, 11.0, 12.0, 9.0];
    let ichimoku = |tenkan, kijun, senkou| {
        IndicatorRequest::with_columns(
            columns_of(&[high, low, close]),
            Params::Ichimoku {
                tenkan,
                kijun,
                senkou,
            },
        )
    };
    let requests = vec![
        ichimoku(1, 2, 3),
        ichimoku(1, 0, 3),
        ichimoku(1, 2, 5),
        request(IndicatorKind::Ichimoku, close.to_vec(), 1),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [tenkan, kijun, senkou_a, senkou_b, chikou] = direct.outputs() else {
        panic!("expected five outputs, got {}", direct.output_count());
    };
    assert_values(tenkan, &[10.0, 11.0, 12.0, 10.0]);
    assert_values(kijun, &[NAN, 10.5, 11.5, 10.5]);
    assert_values(senkou_a, &[NAN, 10.75, 11.75, 10.25]);
    assert_values(senkou_b, &[NAN, NAN, 11.0, 10.5]);
    assert_values(chikou, close);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected Ichimoku success, got {error:?}"),
    }
    assert_eq!(
        *error_of(&results[1]),
        PytaError::InvalidParameter {
            name: "kijun",
            minimum: 1,
            value: 0,
        }
    );
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 5,
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

/// Validated columns from slices, in the given order.
fn columns_of(values: &[&[f64]]) -> Columns {
    Columns::new(
        values
            .iter()
            .map(|column| Series::new(column.to_vec()).unwrap())
            .collect(),
    )
    .unwrap()
}

/// The high, low and close columns of `tests/fixtures/ohlcv_daily.csv`
/// (300 real SPY sessions).
fn spy() -> [Vec<f64>; 3] {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../tests/fixtures/ohlcv_daily.csv");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));
    let mut columns = [Vec::new(), Vec::new(), Vec::new()];

    // Rows are date,open,high,low,close,volume after the comments and header.
    for line in text.lines().filter(|line| !line.starts_with('#')).skip(1) {
        let fields: Vec<&str> = line.split(',').collect();
        for (column, field) in columns.iter_mut().zip(&fields[2..5]) {
            column.push(field.parse().unwrap());
        }
    }
    columns
}

/// Asserts equality bit for bit, NaN matching NaN.
fn assert_bits(actual: &[f64], expected: &[f64], what: &str) {
    assert_eq!(actual.len(), expected.len(), "{what}: length");
    for (row, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            a.to_bits() == e.to_bits() || (a.is_nan() && e.is_nan()),
            "{what}, row {row}: {a} vs {e}"
        );
    }
}

#[test]
fn ichimoku_lines_are_donchian_middles_on_spy() {
    // The approved reference: tenkan-sen, kijun-sen and senkou span B are
    // Donchian's middle line over 9, 26 and 52 rows, bit for bit; senkou
    // span A is their average and the chikou span is close.
    let [high, low, close] = spy();
    let ichimoku = execute_direct(&IndicatorRequest::with_columns(
        columns_of(&[&high, &low, &close]),
        Params::Ichimoku {
            tenkan: 9,
            kijun: 26,
            senkou: 52,
        },
    ))
    .unwrap();
    let donchian_middle = |period| {
        let output = execute_direct(&IndicatorRequest::with_columns(
            columns_of(&[&high, &low]),
            Params::Donchian { period },
        ))
        .unwrap();
        output.outputs()[1].clone()
    };
    let [tenkan, kijun, senkou_a, senkou_b, chikou] = ichimoku.outputs() else {
        panic!("expected five outputs, got {}", ichimoku.output_count());
    };

    let expected_tenkan = donchian_middle(9);
    let expected_kijun = donchian_middle(26);
    let mut expected_senkou_a = vec![NAN; close.len()];
    for row in 25..close.len() {
        expected_senkou_a[row] = (expected_tenkan[row] + expected_kijun[row]) / 2.0;
    }

    assert_bits(tenkan, &expected_tenkan, "tenkan");
    assert_bits(kijun, &expected_kijun, "kijun");
    assert_bits(senkou_a, &expected_senkou_a, "senkou_a");
    assert_bits(senkou_b, &donchian_middle(52), "senkou_b");
    assert_bits(chikou, &close, "chikou");
}

#[tokio::test]
async fn stoch_runs_through_the_engine_with_two_outputs_and_reports_its_errors() {
    // k 3, k_smooth 1, d 2: raw %K 75, 50, 75, 80 from row 2; %D the mean
    // of two.
    let high: &[f64] = &[11.0, 12.0, 13.0, 12.0, 14.0, 15.0];
    let low: &[f64] = &[9.0, 10.0, 11.0, 10.0, 11.0, 12.0];
    let close: &[f64] = &[10.0, 11.0, 12.0, 11.5, 13.0, 14.0];
    let stoch = |k, k_smooth, d| {
        IndicatorRequest::with_columns(
            columns_of(&[high, low, close]),
            Params::Stoch { k, k_smooth, d },
        )
    };
    let requests = vec![
        stoch(3, 1, 2),
        stoch(3, 0, 2),
        stoch(3, 3, 3),
        request(IndicatorKind::Stoch, close.to_vec(), 1),
    ];

    let direct = execute_direct(&requests[0]).unwrap();
    let [stoch_k, stoch_d] = direct.outputs() else {
        panic!("expected two outputs, got {}", direct.output_count());
    };
    assert_values(stoch_k, &[NAN, NAN, 75.0, 50.0, 75.0, 80.0]);
    assert_values(stoch_d, &[NAN, NAN, NAN, 62.5, 62.5, 77.5]);

    let results = execute_batch(requests).await;

    match &results[0].status {
        IndicatorStatus::Success(output) => {
            for (got, want) in output.outputs().iter().zip(direct.outputs()) {
                assert_values(got, want);
            }
        }
        IndicatorStatus::Error(error) => panic!("expected Stochastic success, got {error:?}"),
    }
    assert_eq!(
        *error_of(&results[1]),
        PytaError::InvalidParameter {
            name: "k_smooth",
            minimum: 1,
            value: 0,
        }
    );
    assert_eq!(
        *error_of(&results[2]),
        PytaError::InsufficientData {
            required: 7,
            length: 6,
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
