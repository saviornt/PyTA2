//! KAMA kernel: TA-Lib seeding, warm-up, flat windows, edge cases and
//! magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::kama;

const NAN: f64 = f64::NAN;
const SLOWEST: f64 = 2.0 / 31.0;
const FASTEST: f64 = 2.0 / 3.0;

/// KAMA by its definition: each window's sum of changes summed afresh (no
/// rolling sum), so a flat window's sum is exactly 0.
fn reference_kama(values: &[f64], period: usize) -> Vec<f64> {
    let mut output = vec![NAN; values.len()];
    let mut previous = values[period - 1];
    for index in period..values.len() {
        let window = &values[index - period..=index];
        let sum: f64 = window
            .windows(2)
            .map(|pair| (pair[1] - pair[0]).abs())
            .sum();
        let net = values[index] - values[index - period];
        let ratio = if sum <= 0.0 || sum <= net {
            1.0
        } else {
            (net / sum).abs().min(1.0)
        };
        let constant = ratio * (FASTEST - SLOWEST) + SLOWEST;
        previous += constant * constant * (values[index] - previous);
        output[index] = previous;
    }
    output
}

fn assert_close(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || (a - e).abs() <= 1.0e-12 * e.abs().max(1.0),
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

/// A bumpy series whose changes are not exact in binary.
fn bumpy(length: usize) -> Vec<f64> {
    (0..length)
        .map(|i| 100.0 + (i as f64 * 0.7).sin() * 3.1 + i as f64 * 0.13)
        .collect()
}

#[test]
fn kama_matches_its_definition() {
    let values = bumpy(120);

    for period in [2, 3, 10, 30] {
        let result = kama(&Series::new(values.clone()).unwrap(), period).unwrap();

        assert_close(result.values(), &reference_kama(&values, period));
    }
}

#[test]
fn kama_is_seeded_with_the_previous_price() {
    // Period 2 on 1, 2, 4: the net change 3 equals the sum of changes, so the
    // efficiency ratio is 1 and SC = (2/3)^2; seeded with 2, KAMA is
    // 2 + (4/9) * 2.
    let input = Series::new(vec![1.0, 2.0, 4.0]).unwrap();

    let result = kama(&input, 2).unwrap();

    assert!(result.values()[..2].iter().all(|value| value.is_nan()));
    assert!((result.values()[2] - (2.0 + 8.0 / 9.0)).abs() < 1.0e-15);
}

#[test]
fn kama_moves_slowly_in_noise() {
    // Alternating prices: the net change over an even period is 0, so the
    // ratio is 0 and SC is the slowest constant squared.
    let values: Vec<f64> = (0..10)
        .map(|i| if i % 2 == 0 { 10.0 } else { 11.0 })
        .collect();
    let input = Series::new(values).unwrap();

    let result = kama(&input, 4).unwrap();

    // Seed 11.0 (index 3), price 10.0 at index 4.
    let expected = 11.0 - SLOWEST * SLOWEST;
    assert!((result.values()[4] - expected).abs() < 1.0e-15);
}

#[test]
fn kama_period_one_is_an_exact_copy() {
    let input = Series::new(vec![1.0, 1e-20, -3.0e6, 0.1, -0.0]).unwrap();

    let result = kama(&input, 1).unwrap();

    assert_eq!(result.values(), input.values());
    assert!(result.values()[4].is_sign_negative());
}

#[test]
fn kama_period_one_works_on_one_value() {
    let input = Series::new(vec![4.5]).unwrap();

    assert_eq!(kama(&input, 1).unwrap().values(), &[4.5]);
}

#[test]
fn kama_needs_one_more_value_than_its_period() {
    let input = Series::new(bumpy(11)).unwrap();

    let result = kama(&input, 10).unwrap();

    assert!(result.values()[..10].iter().all(|value| value.is_nan()));
    assert!(result.values()[10].is_finite());
}

#[test]
fn kama_of_a_constant_is_that_constant() {
    let input = Series::new(vec![7.25; 200]).unwrap();

    let result = kama(&input, 10).unwrap();

    assert!(result.values()[..10].iter().all(|value| value.is_nan()));
    assert!(result.values()[10..].iter().all(|value| *value == 7.25));
}

#[test]
fn a_flat_window_resets_the_rolling_sum() {
    // Changes such as 0.1 are inexact, so the rolling sum keeps residue when
    // the window goes flat; once `period` changes in a row are zero, the sum
    // is reset and the ratio is 1, as when it is summed afresh.
    let mut values = bumpy(40);
    values.extend([103.3; 25]);
    values.extend(bumpy(30));
    let period = 10;

    let result = kama(&Series::new(values.clone()).unwrap(), period).unwrap();

    assert_close(result.values(), &reference_kama(&values, period));
    // In the flat stretch KAMA closes in on the price, never passing it.
    let flat = &result.values()[50..65];
    assert!(
        flat.windows(2)
            .all(|pair| { (pair[1] - 103.3).abs() <= (pair[0] - 103.3).abs() })
    );
}

#[test]
fn kama_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(kama(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn kama_rejects_too_little_data() {
    let input = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(
        kama(&input, 3),
        Err(PytaError::InsufficientData {
            required: 4,
            length: 3,
        })
    );
}

#[test]
fn kama_reports_a_huge_period_without_overflow() {
    let input = Series::new(vec![1.0, 2.0]).unwrap();

    assert_eq!(
        kama(&input, usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 2,
        })
    );
}

#[test]
fn kama_has_one_output() {
    let input = Series::new(vec![1.0, 2.0, 3.0, 4.0]).unwrap();

    assert_eq!(kama(&input, 2).unwrap().output_count(), 1);
}

#[test]
fn kama_stays_finite_at_the_magnitude_limit() {
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
        let result = kama(&input, 30).unwrap();

        assert!(result.values()[30..].iter().all(|value| value.is_finite()));
    }
}
