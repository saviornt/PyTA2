//! DEMA kernel: TA-Lib seeding, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::dema;

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
fn dema_has_no_lag_on_a_ramp() {
    // Period 3 (k = 0.5): EMA1 of 1, 2, 3, ... is seeded with 2 at index 2
    // and lags the price by 1; EMA2 is seeded with (2 + 3 + 4) / 3 = 3 at
    // index 4 and lags EMA1 by 1; 2 * EMA1 - EMA2 is the price itself.
    let input = Series::new((1..=8).map(f64::from).collect()).unwrap();

    let result = dema(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, NAN, NAN, 5.0, 6.0, 7.0, 8.0]);
}

#[test]
fn dema_is_not_an_ema_of_an_ema() {
    // A step from 0 to 10 after the warm-up: DEMA overshoots it (2 * EMA1 -
    // EMA2 > EMA1 while EMA1 leads EMA2), which no EMA of an EMA can do.
    let mut values = vec![0.0; 10];
    values.extend([10.0; 10]);
    let input = Series::new(values).unwrap();

    let result = dema(&input, 3).unwrap();

    assert!(result.values()[..4].iter().all(|value| value.is_nan()));
    assert!(result.values()[4..10].iter().all(|value| *value == 0.0));
    // Index 10: EMA1 = 5, EMA2 = 2.5, DEMA = 7.5; index 11: 7.5, 5, 10.
    assert_eq!(result.values()[10], 7.5);
    assert_eq!(result.values()[11], 10.0);
    assert!(result.values()[12] > 10.0);
}

#[test]
fn dema_period_one_is_an_exact_copy() {
    let input = Series::new(vec![1.0, 1e-20, -3.0e6, 0.1, -0.0]).unwrap();

    let result = dema(&input, 1).unwrap();

    assert_eq!(result.values(), input.values());
    assert!(result.values()[4].is_sign_negative());
}

#[test]
fn dema_needs_two_periods_less_one_values() {
    // Period 3 needs 5 values and gives one.
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0, 5.0]).unwrap();

    let result = dema(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, NAN, NAN, 5.0]);
}

#[test]
fn dema_of_a_constant_is_that_constant() {
    let input = Series::new(vec![7.25; 200]).unwrap();

    let result = dema(&input, 10).unwrap();

    assert!(result.values()[..18].iter().all(|value| value.is_nan()));
    assert!(result.values()[18..].iter().all(|value| *value == 7.25));
}

#[test]
fn dema_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(dema(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn dema_rejects_too_little_data() {
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0]).unwrap();

    assert_eq!(
        dema(&input, 3),
        Err(PytaError::InsufficientData {
            required: 5,
            length: 4,
        })
    );
}

#[test]
fn dema_reports_a_huge_period_without_overflow() {
    let input = Series::new(vec![1.0, 2.0]).unwrap();

    assert_eq!(
        dema(&input, usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX - 1,
            length: 2,
        })
    );
}

#[test]
fn dema_has_one_output() {
    let input = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(dema(&input, 2).unwrap().output_count(), 1);
}

#[test]
fn dema_stays_finite_at_the_magnitude_limit() {
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
        let result = dema(&input, 30).unwrap();

        assert!(result.values()[58..].iter().all(|value| value.is_finite()));
    }
}
