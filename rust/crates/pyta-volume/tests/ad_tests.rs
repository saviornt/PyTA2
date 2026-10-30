//! Accumulation/Distribution kernel: formula, length and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volume::ad;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn ad_of([high, low, close, volume]: [&[f64]; 4]) -> Vec<f64> {
    ad(&series(high), &series(low), &series(close), &series(volume))
        .unwrap()
        .values()
        .to_vec()
}

// Multipliers: close at the high (1), at the low (-1), a quarter of the way
// up (-0.5), a one-price bar (0), halfway (0).
const HIGH: [f64; 5] = [12.0, 12.0, 14.0, 10.0, 12.0];
const LOW: [f64; 5] = [10.0, 10.0, 10.0, 10.0, 8.0];
const CLOSE: [f64; 5] = [12.0, 10.0, 11.0, 10.0, 10.0];
const VOLUME: [f64; 5] = [100.0, 40.0, 200.0, 500.0, 300.0];

#[test]
fn ad_matches_a_hand_calculation() {
    // +100, -40, -100, nothing (one-price bar), 0 (halfway).
    assert_eq!(
        ad_of([&HIGH, &LOW, &CLOSE, &VOLUME]),
        [100.0, 60.0, -40.0, -40.0, -40.0]
    );
}

#[test]
fn ad_has_the_input_length_and_no_warm_up() {
    let output = ad_of([&HIGH, &LOW, &CLOSE, &VOLUME]);

    assert_eq!(output.len(), HIGH.len());
    assert!(output.iter().all(|value| value.is_finite()));
}

#[test]
fn ad_of_one_row_is_its_money_flow_volume() {
    // Close three quarters of the way up: multiplier 0.5.
    assert_eq!(ad_of([&[14.0], &[10.0], &[13.0], &[80.0]]), [40.0]);
}

#[test]
fn ad_adds_nothing_for_a_one_price_bar_or_zero_volume() {
    let flat = [7.0; 3];
    assert_eq!(ad_of([&flat, &flat, &flat, &[9.0; 3]]), [0.0; 3]);

    assert_eq!(
        ad_of([&HIGH, &LOW, &CLOSE, &[0.0; 5]]),
        [0.0; 5],
        "zero volume adds nothing"
    );
}

#[test]
fn ad_follows_talibs_order_of_operations() {
    // `((close - low) - (high - close)) / (high - low) * volume`, not the
    // algebraically equal `(2 * close - high - low) / ...`.
    let (high, low, close, volume) = (0.3, 0.1, 0.25, 7.0);
    let expected = (close - low - (high - close)) / (high - low) * volume;

    assert_eq!(
        ad_of([&[high], &[low], &[close], &[volume]])[0].to_bits(),
        f64::to_bits(expected)
    );
}

#[test]
fn ad_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..4];
    for [high, low, close, volume] in [
        [short, &LOW, &CLOSE, &VOLUME],
        [&HIGH, short, &CLOSE, &VOLUME],
        [&HIGH, &LOW, short, &VOLUME],
        [&HIGH, &LOW, &CLOSE, short],
    ] {
        assert_eq!(
            ad(&series(high), &series(low), &series(close), &series(volume)),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn ad_stays_finite_at_the_magnitude_limit_with_closes_inside_their_bars() {
    // Each step is at most the row's volume.
    let high = [MAX_ABS_INPUT; 3];
    let low = [-MAX_ABS_INPUT; 3];
    let close = [MAX_ABS_INPUT; 3];
    let output = ad_of([&high, &low, &close, &[MAX_ABS_INPUT; 3]]);

    assert_eq!(
        output,
        [MAX_ABS_INPUT, 2.0 * MAX_ABS_INPUT, 3.0 * MAX_ABS_INPUT]
    );
}
