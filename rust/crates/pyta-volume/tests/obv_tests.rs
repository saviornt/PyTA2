//! On-Balance Volume kernel: formula, length and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volume::obv;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn obv_of(close: &[f64], volume: &[f64]) -> Vec<f64> {
    obv(&series(close), &series(volume))
        .unwrap()
        .values()
        .to_vec()
}

#[test]
fn obv_adds_on_a_rise_subtracts_on_a_fall_and_holds_on_a_tie() {
    // Row 0 starts at its volume; then up, down, equal, up.
    let close = [10.0, 11.0, 10.5, 10.5, 12.0];
    let volume = [100.0, 200.0, 300.0, 400.0, 500.0];

    assert_eq!(obv_of(&close, &volume), [100.0, 300.0, 0.0, 0.0, 500.0]);
}

#[test]
fn obv_has_the_input_length_and_no_warm_up() {
    let close = [1.0, 3.0, 2.0, 2.0, 5.0, 4.0, 4.5];
    let volume = [7.0; 7];
    let output = obv_of(&close, &volume);

    assert_eq!(output.len(), close.len());
    assert!(output.iter().all(|value| value.is_finite()));
}

#[test]
fn obv_of_one_row_is_its_volume() {
    assert_eq!(obv_of(&[42.0], &[1234.0]), [1234.0]);
}

#[test]
fn obv_of_flat_prices_keeps_the_first_volume() {
    assert_eq!(obv_of(&[5.0; 4], &[3.0, 8.0, 9.0, 1.0]), [3.0; 4]);
}

#[test]
fn obv_with_zero_volume_rows_changes_nothing_on_them() {
    let close = [1.0, 2.0, 3.0, 2.0];
    let volume = [0.0, 0.0, 5.0, 0.0];

    assert_eq!(obv_of(&close, &volume), [0.0, 0.0, 5.0, 5.0]);
}

#[test]
fn obv_rejects_columns_of_different_lengths() {
    assert_eq!(
        obv(&series(&[1.0, 2.0, 3.0]), &series(&[1.0, 2.0])),
        Err(PytaError::LengthMismatch)
    );
    assert_eq!(
        obv(&series(&[1.0, 2.0]), &series(&[1.0, 2.0, 3.0])),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn obv_stays_finite_at_the_magnitude_limit() {
    // Each row adds at most `MAX_ABS_INPUT`; the total stays far below
    // `f64::MAX`.
    let close = [1.0, 2.0, 3.0, 4.0];
    let output = obv_of(&close, &[MAX_ABS_INPUT; 4]);

    assert_eq!(output[3], 4.0 * MAX_ABS_INPUT);
}
