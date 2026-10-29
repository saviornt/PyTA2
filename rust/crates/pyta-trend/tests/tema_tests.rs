//! TEMA kernel: TA-Lib seeding, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::tema;

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
fn tema_has_no_lag_on_a_ramp() {
    // Period 3 (k = 0.5) on 1, 2, 3, ...: EMA1, EMA2 and EMA3 lag the price
    // by 1, 2 and 3 (EMA3 is seeded with (3 + 4 + 5) / 3 = 4 at index 6), so
    // EMA3 + 3 * (EMA1 - EMA2) is the price itself.
    let input = Series::new((1..=10).map(f64::from).collect()).unwrap();

    let result = tema(&input, 3).unwrap();

    assert_values(
        result.values(),
        &[NAN, NAN, NAN, NAN, NAN, NAN, 7.0, 8.0, 9.0, 10.0],
    );
}

#[test]
fn tema_overshoots_a_step() {
    // A step from 0 to 10 after the warm-up. Index 10: EMA1 = 5, EMA2 = 2.5,
    // EMA3 = 1.25, TEMA = 1.25 + (15 - 7.5) = 8.75; index 11: 7.5, 5, 3.125,
    // TEMA = 3.125 + (22.5 - 15) = 10.625, past the new level.
    let mut values = vec![0.0; 10];
    values.extend([10.0; 10]);
    let input = Series::new(values).unwrap();

    let result = tema(&input, 3).unwrap();

    assert!(result.values()[..6].iter().all(|value| value.is_nan()));
    assert!(result.values()[6..10].iter().all(|value| *value == 0.0));
    assert_eq!(result.values()[10], 8.75);
    assert_eq!(result.values()[11], 10.625);
}

#[test]
fn tema_period_one_is_an_exact_copy() {
    let input = Series::new(vec![1.0, 1e-20, -3.0e6, 0.1, -0.0]).unwrap();

    let result = tema(&input, 1).unwrap();

    assert_eq!(result.values(), input.values());
    assert!(result.values()[4].is_sign_negative());
}

#[test]
fn tema_needs_three_periods_less_two_values() {
    // Period 3 needs 7 values and gives one.
    let input = Series::new((1..=7).map(f64::from).collect()).unwrap();

    let result = tema(&input, 3).unwrap();

    assert_values(result.values(), &[NAN, NAN, NAN, NAN, NAN, NAN, 7.0]);
}

#[test]
fn tema_of_a_constant_is_that_constant() {
    let input = Series::new(vec![7.25; 200]).unwrap();

    let result = tema(&input, 10).unwrap();

    assert!(result.values()[..27].iter().all(|value| value.is_nan()));
    assert!(result.values()[27..].iter().all(|value| *value == 7.25));
}

#[test]
fn tema_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(tema(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn tema_rejects_too_little_data() {
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0]).unwrap();

    assert_eq!(
        tema(&input, 3),
        Err(PytaError::InsufficientData {
            required: 7,
            length: 6,
        })
    );
}

#[test]
fn tema_reports_a_huge_period_without_overflow() {
    let input = Series::new(vec![1.0, 2.0]).unwrap();

    assert_eq!(
        tema(&input, usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX - 2,
            length: 2,
        })
    );
}

#[test]
fn tema_has_one_output() {
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0]).unwrap();

    assert_eq!(tema(&input, 2).unwrap().output_count(), 1);
}

#[test]
fn tema_stays_finite_at_the_magnitude_limit() {
    let constant = Series::new(vec![MAX_ABS_INPUT; 128]).unwrap();
    let alternating = Series::new(
        (0..128)
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
        let result = tema(&input, 30).unwrap();

        assert!(result.values()[87..].iter().all(|value| value.is_finite()));
    }
}
