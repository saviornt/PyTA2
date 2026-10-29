//! WMA kernel: TA-Lib weighting, warm-up, edge cases, rebuilds and magnitude
//! limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::wma;

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
fn wma_weights_the_oldest_value_by_one_and_the_newest_by_period() {
    // Period 3, divisor 6: (1*1 + 2*2 + 3*4) / 6 = 17/6 and
    // (1*2 + 2*4 + 3*10) / 6 = 40/6.
    let input = Series::new(vec![1.0, 2.0, 4.0, 10.0]).unwrap();

    let result = wma(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 17.0 / 6.0, 40.0 / 6.0]);
}

#[test]
fn wma_of_a_ramp_lags_by_a_third_of_the_window() {
    // For a ramp, the WMA of period n lags the newest value by (n - 1) / 3.
    let input = Series::new((1..=10).map(f64::from).collect()).unwrap();

    let result = wma(&input, 4).unwrap();

    assert!(result.values()[..3].iter().all(|value| value.is_nan()));
    for (index, value) in result.values().iter().enumerate().skip(3) {
        let expected = (index + 1) as f64 - 1.0;
        assert!((value - expected).abs() < 1e-12, "{index}: {value}");
    }
}

#[test]
fn wma_period_one_is_an_exact_copy() {
    let input = Series::new(vec![1.0, 1e-20, -3.0e6, 0.1]).unwrap();

    let result = wma(&input, 1).unwrap();

    assert_eq!(result.values(), input.values());
}

#[test]
fn wma_period_equal_to_length_returns_one_average() {
    // (1*1 + 2*2 + 3*6) / 6 = 23/6.
    let input = Series::new(vec![1.0, 2.0, 6.0]).unwrap();

    let result = wma(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 23.0 / 6.0]);
}

#[test]
fn wma_of_a_constant_is_that_constant() {
    let input = Series::new(vec![7.25; 200]).unwrap();

    let result = wma(&input, 10).unwrap();

    assert!(result.values()[..9].iter().all(|value| value.is_nan()));
    assert!(result.values()[9..].iter().all(|value| *value == 7.25));
}

#[test]
fn wma_matches_a_direct_weighted_sum_across_rebuilds() {
    // Period 3 rebuilds every 24 rows; 200 rows cross several rebuilds.
    let values: Vec<f64> = (0..200)
        .map(|i| (f64::from(i) * 0.37).sin() * 5.0 + 100.0)
        .collect();
    let input = Series::new(values.clone()).unwrap();

    let result = wma(&input, 3).unwrap();

    for (index, value) in result.values().iter().enumerate().skip(2) {
        let expected = (values[index - 2] + 2.0 * values[index - 1] + 3.0 * values[index]) / 6.0;
        assert!(
            (value - expected).abs() <= 1e-12 * expected.abs(),
            "{index}"
        );
    }
}

#[test]
fn wma_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(wma(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn wma_rejects_a_period_longer_than_the_input() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(
        wma(&input, 4),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn wma_has_one_output() {
    let input = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(wma(&input, 2).unwrap().output_count(), 1);
}

#[test]
fn wma_stays_finite_at_the_magnitude_limit() {
    let constant = Series::new(vec![MAX_ABS_INPUT; 64]).unwrap();
    let alternating = Series::new(
        (0..64)
            .map(|i| {
                if i % 2 == 0 {
                    MAX_ABS_INPUT
                } else {
                    -MAX_ABS_INPUT
                }
            })
            .collect(),
    )
    .unwrap();

    for input in [constant, alternating] {
        let result = wma(&input, 30).unwrap();

        assert!(result.values()[29..].iter().all(|value| value.is_finite()));
    }
}
