use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::sma;

const NAN: f64 = f64::NAN;

fn assert_values(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || a == e,
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

#[test]
fn sma_calculates_rolling_averages() {
    let input = Series::new(vec![10.0, 20.0, 30.0, 40.0, 50.0]).unwrap();

    let result = sma(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 20.0, 30.0, 40.0]);
}

#[test]
fn sma_period_one_returns_original_values() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    let result = sma(&input, 1).unwrap();

    assert_values(result.values(), &[10.0, 20.0, 30.0]);
}

#[test]
fn sma_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(sma(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn sma_rejects_period_greater_than_input_length() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(
        sma(&input, 4),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn sma_accepts_period_equal_to_input_length() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    let result = sma(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 20.0]);
}

#[test]
fn sma_preserves_input_length() {
    let input = Series::new(vec![2.0, 4.0, 6.0, 8.0]).unwrap();

    let result = sma(&input, 2).unwrap();

    assert_eq!(result.len(), input.len());
}

#[test]
fn sma_matches_naive_mean_on_long_series() {
    let period = 50;
    let data: Vec<f64> = (0..20_000)
        .map(|i| 1.0e8 + (i as f64 * 0.37).sin() * 1.0e3)
        .collect();
    let input = Series::new(data.clone()).unwrap();

    let result = sma(&input, period).unwrap();

    for index in (period - 1)..data.len() {
        let naive = data[index + 1 - period..=index].iter().sum::<f64>() / period as f64;
        let actual = result.values()[index];

        assert!(
            (actual - naive).abs() <= naive.abs() * 1e-12,
            "drift at {index}: got {actual}, expected {naive}"
        );
    }
}

#[test]
fn sma_is_exact_at_the_magnitude_limit() {
    let limit = MAX_ABS_INPUT;
    let input = Series::new(vec![limit, limit, -limit, -limit, limit]).unwrap();

    let result = sma(&input, 2).unwrap();

    assert_values(result.values(), &[NAN, limit, 0.0, -limit, 0.0]);
}

#[test]
fn sma_stays_finite_for_long_windows_at_the_magnitude_limit() {
    let period = 10_000;
    let data: Vec<f64> = (0..3 * period)
        .map(|i| {
            if i % 3 == 0 {
                -MAX_ABS_INPUT
            } else {
                MAX_ABS_INPUT
            }
        })
        .collect();
    let input = Series::new(data.clone()).unwrap();

    let result = sma(&input, period).unwrap();

    for index in (period - 1)..data.len() {
        let actual = result.values()[index];
        let naive = data[index + 1 - period..=index]
            .iter()
            .map(|value| value / period as f64)
            .sum::<f64>();

        assert!(actual.is_finite(), "non-finite output at {index}");
        assert!(
            (actual - naive).abs() <= MAX_ABS_INPUT * 1e-12,
            "drift at {index}: got {actual}, expected {naive}"
        );
    }
}

#[test]
fn inputs_that_would_overflow_the_window_sum_are_rejected() {
    // Before the limit, these returned `inf` and `NaN` after warm-up.
    assert_eq!(
        Series::new(vec![f64::MAX, f64::MAX]),
        Err(PytaError::ValueOutOfRange { index: 0 })
    );
    assert_eq!(
        Series::new(vec![1.0, 1e308, 1e308, -1e308]),
        Err(PytaError::ValueOutOfRange { index: 1 })
    );
    assert_eq!(
        Series::new(vec![1.0, MAX_ABS_INPUT.next_up()]),
        Err(PytaError::ValueOutOfRange { index: 1 })
    );
}
