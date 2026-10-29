//! ATR kernel: formula, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volatility::atr;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn atr_of(high: &[f64], low: &[f64], close: &[f64], period: usize) -> Vec<f64> {
    atr(&series(high), &series(low), &series(close), period)
        .unwrap()
        .into_values()
}

// True ranges of these rows (row 0 has none):
// row 1: max(12 - 9, |12 - 10|, |9 - 10|) = 3
// row 2: max(11 - 10, |11 - 11|, |10 - 11|) = 1
// row 3: max(14 - 12, |14 - 10|, |12 - 10|) = 4 (gap up from close 10)
// row 4: max(13 - 11, |13 - 13|, |11 - 13|) = 2
const HIGH: [f64; 5] = [11.0, 12.0, 11.0, 14.0, 13.0];
const LOW: [f64; 5] = [9.0, 9.0, 10.0, 12.0, 11.0];
const CLOSE: [f64; 5] = [10.0, 11.0, 10.0, 13.0, 12.0];

#[test]
fn atr_preserves_input_length_and_warmup_alignment() {
    let result = atr_of(&HIGH, &LOW, &CLOSE, 2);

    assert_eq!(result.len(), 5);
    assert!(result[..2].iter().all(|value| value.is_nan()));
    assert!(result[2..].iter().all(|value| value.is_finite()));
}

#[test]
fn atr_matches_a_hand_calculation() {
    // Seed at row 2: (3 + 1) / 2 = 2; row 3: (2 + 4) / 2 = 3;
    // row 4: (3 + 2) / 2 = 2.5.
    let result = atr_of(&HIGH, &LOW, &CLOSE, 2);

    assert_eq!(&result[2..], &[2.0, 3.0, 2.5]);
}

#[test]
fn atr_with_period_one_is_the_true_range() {
    let result = atr_of(&HIGH, &LOW, &CLOSE, 1);

    assert!(result[0].is_nan());
    assert_eq!(&result[1..], &[3.0, 1.0, 4.0, 2.0]);
}

#[test]
fn atr_rejects_zero_period() {
    let close = series(&[1.0, 2.0]);

    assert_eq!(
        atr(&close, &close, &close, 0),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn atr_rejects_insufficient_data() {
    let close = series(&[1.0, 2.0, 3.0]);

    assert_eq!(
        atr(&close, &close, &close, 3),
        Err(PytaError::InsufficientData {
            required: 4,
            length: 3,
        })
    );
}

#[test]
fn atr_accepts_minimum_data() {
    let result = atr_of(&HIGH[..3], &LOW[..3], &CLOSE[..3], 2);

    assert!(result[..2].iter().all(|value| value.is_nan()));
    assert_eq!(result[2], 2.0);
}

#[test]
fn atr_rejects_columns_of_different_lengths() {
    let short = series(&[1.0, 2.0]);
    let long = series(&[1.0, 2.0, 3.0]);

    assert_eq!(atr(&long, &short, &long, 1), Err(PytaError::LengthMismatch));
    assert_eq!(atr(&long, &long, &short, 1), Err(PytaError::LengthMismatch));
}

#[test]
fn atr_is_zero_for_a_flat_series() {
    let flat = [5.0; 6];
    let result = atr_of(&flat, &flat, &flat, 3);

    assert_eq!(&result[3..], &[0.0, 0.0, 0.0]);
}

#[test]
fn atr_is_zero_when_high_equals_low_and_close_is_unchanged() {
    // A real price level, no range and no gap: every true range is 0.
    let price = [101.25; 5];
    let result = atr_of(&price, &price, &price, 2);

    assert!(result[2..].iter().all(|value| *value == 0.0));
}

#[test]
fn atr_measures_a_gap_when_high_equals_low() {
    // No range inside any row, but the close moves by 2 each row.
    let price = [10.0, 12.0, 14.0, 16.0];
    let result = atr_of(&price, &price, &price, 2);

    assert_eq!(&result[2..], &[2.0, 2.0]);
}

#[test]
fn atr_decays_towards_zero_after_movement_stops() {
    let mut close = vec![10.0, 20.0];
    close.extend([20.0; 20]);
    let result = atr_of(&close, &close, &close, 3);

    // Seed (10 + 0 + 0) / 3, then multiplied by 2/3 each row.
    let mut expected = 10.0 / 3.0;
    for value in &result[3..] {
        assert!(
            (value - expected).abs() <= 1e-12 * expected,
            "{value} vs {expected}"
        );
        expected *= 2.0 / 3.0;
    }
}

#[test]
fn atr_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 4];
    let low = [-MAX_ABS_INPUT; 4];
    let close = [MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, -MAX_ABS_INPUT];

    let result = atr_of(&high, &low, &close, 2);

    assert!(result[2..].iter().all(|value| value.is_finite()));
}
