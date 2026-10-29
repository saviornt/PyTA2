//! EMA kernel: TA-Lib seeding, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::ema;

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
fn ema_seeds_with_the_simple_average_then_smooths() {
    // Period 3: k = 0.5, seed (1 + 2 + 3) / 3 = 2, then 2 + (4 - 2) / 2 = 3,
    // and 3 + (5 - 3) / 2 = 4.
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0, 5.0]).unwrap();

    let result = ema(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 2.0, 3.0, 4.0]);
}

#[test]
fn ema_weights_the_newest_value_by_two_over_period_plus_one() {
    // Period 4: k = 0.4, seed 10, then 10 + (20 - 10) * 0.4 = 14.
    let input = Series::new(vec![10.0, 10.0, 10.0, 10.0, 20.0]).unwrap();

    let result = ema(&input, 4).unwrap();

    assert_values(result.values(), &[NAN, NAN, NAN, 10.0, 14.0]);
}

#[test]
fn ema_period_one_returns_original_values() {
    let input = Series::new(vec![10.0, -20.0, 30.5]).unwrap();

    let result = ema(&input, 1).unwrap();

    assert_values(result.values(), &[10.0, -20.0, 30.5]);
}

#[test]
fn ema_period_equal_to_length_returns_one_average() {
    let input = Series::new(vec![1.0, 2.0, 6.0]).unwrap();

    let result = ema(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, 3.0]);
}

#[test]
fn ema_of_a_constant_is_that_constant() {
    let input = Series::new(vec![7.25; 50]).unwrap();

    let result = ema(&input, 10).unwrap();

    assert!(result.values()[..9].iter().all(|value| value.is_nan()));
    assert!(result.values()[9..].iter().all(|value| *value == 7.25));
}

#[test]
fn ema_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(ema(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn ema_rejects_a_period_longer_than_the_input() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(
        ema(&input, 4),
        Err(PytaError::InsufficientData {
            required: 4,
            length: 3,
        })
    );
}

#[test]
fn ema_has_one_output() {
    let input = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(ema(&input, 2).unwrap().output_count(), 1);
}

#[test]
fn ema_stays_finite_at_the_magnitude_limit() {
    let input = Series::new(vec![
        MAX_ABS_INPUT,
        -MAX_ABS_INPUT,
        MAX_ABS_INPUT,
        -MAX_ABS_INPUT,
    ])
    .unwrap();

    let result = ema(&input, 2).unwrap();

    assert!(result.values()[1..].iter().all(|value| value.is_finite()));
}
