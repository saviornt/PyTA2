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
