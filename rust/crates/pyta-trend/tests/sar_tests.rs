//! Parabolic SAR kernel: TA-Lib's first direction and seeds, reversals
//! (ties included), the acceleration cap, warm-up, errors and magnitude
//! limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::sar;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn sar_of(high: &[f64], low: &[f64], acceleration: f64, maximum: f64) -> Vec<f64> {
    sar(&series(high), &series(low), acceleration, maximum)
        .unwrap()
        .values()
        .to_vec()
}

/// Asserts equal values, with NaN only where `expected` has NaN.
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
fn sar_follows_the_hand_calculation() {
    // Acceleration 0.25 and maximum 0.5, so every step is exact in binary.
    // Row 1 rises (+DM 2, -DM 0): long, SAR low[0] = 8, EP high[1] = 12.
    // Row 1: writes 8; next SAR 8 + 0.25 * (12 - 8) = 9 (row 1 is its own
    //   previous row, so the clamp to the lows 9 and 9 changes nothing).
    // Row 2: writes 9; new high 14: EP 14, AF 0.5; 9 + 0.5 * 5 = 11.5,
    //   clamped to the lows 9 and 10: 9.
    // Row 3: low 9 == SAR 9 reverses (a tie reverses): SAR = EP 14, raised
    //   to the highs 14 and 15: writes 15; AF 0.25, EP low 9;
    //   15 + 0.25 * (9 - 15) = 13.5, raised to 15.
    // Row 4: writes 15; low 11 is no new extreme; 13.5, raised to 15.
    // Row 5: writes 15; new low 7: EP 7, AF 0.5; 15 + 0.5 * -8 = 11, raised
    //   to the highs 13 and 12: 13.
    // Row 6: writes 13; new low 6: EP 6, AF 0.75 capped at 0.5;
    //   13 + 0.5 * -7 = 9.5, raised to 12.
    // Row 7: high 12 == SAR 12 reverses to long: SAR = EP 6, kept under the
    //   lows 6 and 10: writes 6; AF 0.25, EP 12; 6 + 0.25 * 6 = 7.5, lowered
    //   to 6.
    // Row 8: low 6 == SAR 6 reverses to short: EP 12, raised to the highs 12
    //   and 13: writes 13.
    let high = [10.0, 12.0, 14.0, 15.0, 13.0, 12.0, 12.0, 12.0, 13.0];
    let low = [8.0, 9.0, 10.0, 9.0, 11.0, 7.0, 6.0, 10.0, 6.0];

    let values = sar_of(&high, &low, 0.25, 0.5);

    assert_values(
        &values,
        &[f64::NAN, 8.0, 9.0, 15.0, 15.0, 15.0, 13.0, 6.0, 13.0],
    );
}

#[test]
fn a_falling_low_starts_short() {
    // -DM 1 beats +DM -0.2: short, SAR high[0] 10, EP low[1] 8. Row 1's
    // high 9.8 stays under 10, so it writes 10; the next SAR moves towards
    // the EP and stays above the highs 9.8 and 9.8. Row 2 writes it.
    let values = sar_of(&[10.0, 9.8, 9.5], &[9.0, 8.0, 7.5], 0.02, 0.2);

    assert_values(&values, &[f64::NAN, 10.0, 0.02 * (8.0 - 10.0) + 10.0]);
}

#[test]
fn a_tie_between_the_moves_starts_long() {
    // +DM and -DM both 1: TA-Lib's -DM is 0 on a tie, so long with SAR
    // low[0] 9 and EP high[1] 11. Row 1's low 8 reverses at once, writing
    // the EP 11; a short start would have written low[1] 8 instead.
    let values = sar_of(&[10.0, 11.0], &[9.0, 8.0], 0.02, 0.2);

    assert_values(&values, &[f64::NAN, 11.0]);
}

#[test]
fn a_fall_smaller_than_the_rise_starts_long() {
    // -DM would be 0.5 but +DM 2 is larger, so -DM is 0: long with SAR
    // low[0] 9. Row 1's low 8.5 reverses at once, writing the EP high[1] 12.
    let values = sar_of(&[10.0, 12.0], &[9.0, 8.5], 0.02, 0.2);

    assert_values(&values, &[f64::NAN, 12.0]);
}

#[test]
fn sar_has_one_warm_up_row() {
    let high: Vec<f64> = (0..50).map(|i| 101.0 + (i as f64 * 0.4).sin()).collect();
    let low: Vec<f64> = high.iter().map(|h| h - 2.0).collect();

    let values = sar_of(&high, &low, 0.02, 0.2);

    assert_eq!(values.len(), 50);
    assert!(values[0].is_nan());
    assert!(values[1..].iter().all(|value| value.is_finite()));
}

#[test]
fn sar_needs_two_rows() {
    let values = sar_of(&[10.0, 11.0], &[9.0, 10.0], 0.02, 0.2);
    assert_values(&values, &[f64::NAN, 9.0]);

    assert_eq!(
        sar(&series(&[10.0]), &series(&[9.0]), 0.02, 0.2),
        Err(PytaError::InsufficientData {
            required: 2,
            length: 1,
        })
    );
}

#[test]
fn a_flat_series_gives_its_price() {
    // No movement starts long with SAR 50; low 50 <= 50 reverses on row 1
    // (to the EP 50), and every later row reverses again at the same price.
    let flat = [50.0; 10];

    let values = sar_of(&flat, &flat, 0.02, 0.2);

    assert!(values[1..].iter().all(|value| *value == 50.0));
}

#[test]
fn an_acceleration_equal_to_its_maximum_is_valid() {
    let values = sar_of(&[10.0, 12.0, 14.0], &[8.0, 9.0, 10.0], 0.2, 0.2);

    assert_eq!(values.len(), 3);
}

#[test]
fn sar_rejects_parameters_that_are_not_finite_and_positive() {
    let (high, low) = (series(&[10.0, 11.0]), series(&[9.0, 10.0]));

    for bad in [0.0, -0.02, f64::INFINITY] {
        assert_eq!(
            sar(&high, &low, bad, 0.2),
            Err(PytaError::InvalidFloatParameter {
                name: "acceleration",
                value: bad,
            })
        );
        assert_eq!(
            sar(&high, &low, 0.02, bad),
            Err(PytaError::InvalidFloatParameter {
                name: "maximum",
                value: bad,
            })
        );
    }
    assert!(matches!(
        sar(&high, &low, f64::NAN, 0.2),
        Err(PytaError::InvalidFloatParameter { name: "acceleration", value }) if value.is_nan()
    ));
}

#[test]
fn sar_rejects_an_acceleration_above_its_maximum() {
    // TA-Lib lowers the acceleration to the maximum; PyTA reports it.
    assert_eq!(
        sar(&series(&[10.0, 11.0]), &series(&[9.0, 10.0]), 0.3, 0.2),
        Err(PytaError::ParametersOutOfOrder {
            lower: "acceleration",
            lower_value: 0.3,
            upper: "maximum",
            upper_value: 0.2,
            strict: false,
        })
    );
}

#[test]
fn sar_rejects_columns_of_unequal_length() {
    assert_eq!(
        sar(
            &series(&[10.0, 11.0, 12.0]),
            &series(&[9.0, 10.0]),
            0.02,
            0.2
        ),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn sar_stays_finite_at_the_magnitude_limit() {
    let swing: Vec<f64> = (0..64)
        .map(|i| {
            if i % 2 == 0 {
                MAX_ABS_INPUT
            } else {
                -MAX_ABS_INPUT
            }
        })
        .collect();

    for (high, low) in [
        (vec![MAX_ABS_INPUT; 64], swing.clone()),
        (swing.clone(), swing),
    ] {
        let values = sar_of(&high, &low, 0.02, 0.2);

        assert!(values[1..].iter().all(|value| value.is_finite()));
    }
}
