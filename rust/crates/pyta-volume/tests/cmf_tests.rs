//! Chaikin Money Flow kernel: formula, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volume::cmf;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn cmf_of([high, low, close, volume]: [&[f64]; 4], period: usize) -> Vec<f64> {
    cmf(
        &series(high),
        &series(low),
        &series(close),
        &series(volume),
        period,
    )
    .unwrap()
    .into_values()
}

// Multipliers 1/2, 0, 1, 0 (one-price bar), -1/2, 1/2; money-flow volumes
// 50, 0, 300, 0, -250, 0.
const HIGH: [f64; 6] = [10.0, 11.0, 12.0, 12.0, 13.0, 14.0];
const LOW: [f64; 6] = [8.0, 9.0, 10.0, 12.0, 11.0, 12.0];
const CLOSE: [f64; 6] = [9.5, 10.0, 12.0, 12.0, 11.5, 13.5];
const VOLUME: [f64; 6] = [100.0, 200.0, 300.0, 400.0, 500.0, 0.0];

#[test]
fn cmf_matches_a_hand_calculation() {
    let output = cmf_of([&HIGH, &LOW, &CLOSE, &VOLUME], 3);

    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(
        output[2..],
        [350.0 / 600.0, 300.0 / 900.0, 50.0 / 1200.0, -250.0 / 900.0]
    );
}

#[test]
fn cmf_has_input_length_and_period_minus_one_warm_up() {
    // From period 2 every window has volume (period 1 is tested below).
    for period in 2..=6 {
        let output = cmf_of([&HIGH, &LOW, &CLOSE, &VOLUME], period);

        assert_eq!(output.len(), 6);
        assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn cmf_of_period_1_is_the_multiplier_where_there_is_volume() {
    let output = cmf_of([&HIGH, &LOW, &CLOSE, &VOLUME], 1);

    assert_eq!(output[..5], [0.5, 0.0, 1.0, 0.0, -0.5]);
    assert!(output[5].is_nan(), "row 5 has no volume");
}

#[test]
fn cmf_is_nan_for_a_window_without_volume_and_recovers_after_it() {
    let volume = [10.0, 0.0, 0.0, 0.0, 20.0, 0.0];
    let output = cmf_of([&HIGH, &LOW, &CLOSE, &volume], 3);

    // Rows 2 (10 of volume at 1/2 -> 1/2), 3 (none), 4 (20 at -1/2).
    assert_eq!(output[2], 0.5);
    assert!(output[3].is_nan());
    assert_eq!(output[4], -0.5);
    assert_eq!(output[5], -0.5);
}

#[test]
fn cmf_of_one_price_bars_is_zero() {
    let flat = [7.0; 4];
    let output = cmf_of([&flat, &flat, &flat, &[5.0; 4]], 2);

    assert!(output[1..].iter().all(|value| *value == 0.0));
}

#[test]
fn cmf_is_one_with_every_close_at_its_high_and_minus_one_at_its_low() {
    let high = [11.0, 12.0, 13.0];
    let low = [9.0, 10.0, 11.0];

    assert_eq!(cmf_of([&high, &low, &high, &[3.0; 3]], 2)[1..], [1.0, 1.0]);
    assert_eq!(cmf_of([&high, &low, &low, &[3.0; 3]], 2)[1..], [-1.0, -1.0]);
}

#[test]
fn cmf_rejects_a_zero_period() {
    assert_eq!(
        cmf(
            &series(&HIGH),
            &series(&LOW),
            &series(&CLOSE),
            &series(&VOLUME),
            0
        ),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn cmf_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..5];
    for [high, low, close, volume] in [
        [short, &LOW, &CLOSE, &VOLUME],
        [&HIGH, short, &CLOSE, &VOLUME],
        [&HIGH, &LOW, short, &VOLUME],
        [&HIGH, &LOW, &CLOSE, short],
    ] {
        assert_eq!(
            cmf(
                &series(high),
                &series(low),
                &series(close),
                &series(volume),
                3
            ),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn cmf_needs_period_rows() {
    let columns = [&HIGH, &LOW, &CLOSE, &VOLUME].map(|values| series(values));
    let [high, low, close, volume] = &columns;

    assert_eq!(
        cmf(high, low, close, volume, 7),
        Err(PytaError::PeriodExceedsLength {
            period: 7,
            length: 6,
        })
    );
    // Exactly `period` rows give one value, on the last row.
    let output = cmf(high, low, close, volume, 6).unwrap().into_values();
    assert!(output[..5].iter().all(|value| value.is_nan()));
    assert_eq!(output[5], 100.0 / 1500.0);
}

#[test]
fn cmf_keeps_its_precision_after_a_huge_window_leaves() {
    // A window of 1e15-sized volumes followed by small ones: plain running
    // sums would keep a rounding residue of the large values.
    let mut volume = vec![1.0e15 + 1.0; 5];
    volume.extend([1.0, 2.0, 3.0]);
    let high = [12.0; 8];
    let low = [10.0; 8];
    let close = [11.5; 8];
    let output = cmf_of([&high, &low, &close, &volume], 3);

    // Multiplier 1/2 on every row: every window gives exactly 1/2.
    assert!(output[2..].iter().all(|value| *value == 0.5), "{output:?}");
}

#[test]
fn cmf_stays_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 3];
    let low = [-MAX_ABS_INPUT; 3];
    let close = [0.0; 3];
    let output = cmf_of([&high, &low, &close, &[MAX_ABS_INPUT; 3]], 2);

    assert_eq!(output[1..], [0.0, 0.0]);
}
