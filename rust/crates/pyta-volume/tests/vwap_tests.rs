//! VWAP kernel: formula, leading rows without volume, and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volume::vwap;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn vwap_of([high, low, close, volume]: [&[f64]; 4]) -> Vec<f64> {
    vwap(&series(high), &series(low), &series(close), &series(volume))
        .unwrap()
        .into_values()
}

// Typical prices 10, 11, 12, 12, 14, 14; volumes 0, 0, 100, 300, 0, 200.
const HIGH: [f64; 6] = [11.0, 12.0, 13.0, 14.0, 15.0, 16.0];
const LOW: [f64; 6] = [9.0, 10.0, 11.0, 11.0, 12.0, 13.0];
const CLOSE: [f64; 6] = [10.0, 11.0, 12.0, 11.0, 15.0, 13.0];
const VOLUME: [f64; 6] = [0.0, 0.0, 100.0, 300.0, 0.0, 200.0];

#[test]
fn vwap_matches_a_hand_calculation() {
    // Cumulative TP * volume 1200, 4800, 4800, 7600 over 100, 400, 400, 600.
    let output = vwap_of([&HIGH, &LOW, &CLOSE, &VOLUME]);

    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(output[2..], [12.0, 12.0, 12.0, 7600.0 / 600.0]);
}

#[test]
fn vwap_has_the_input_length_and_starts_with_the_first_volume() {
    let output = vwap_of([&HIGH, &LOW, &CLOSE, &[5.0; 6]]);

    assert_eq!(output.len(), 6);
    assert!(output.iter().all(|value| value.is_finite()));
    assert_eq!(output[0], 10.0);
}

#[test]
fn vwap_is_nan_throughout_without_volume() {
    let output = vwap_of([&HIGH, &LOW, &CLOSE, &[0.0; 6]]);

    assert!(output.iter().all(|value| value.is_nan()));
}

#[test]
fn vwap_of_one_row_is_its_typical_price() {
    assert_eq!(vwap_of([&[12.0], &[9.0], &[10.5], &[3.0]]), [10.5]);
    assert!(vwap_of([&[12.0], &[9.0], &[10.5], &[0.0]])[0].is_nan());
}

#[test]
fn vwap_of_constant_prices_is_that_price() {
    let level = [42.25; 5];
    let output = vwap_of([&level, &level, &level, &[1.0, 7.0, 0.0, 3.0, 9.0]]);

    assert!(output.iter().all(|value| *value == 42.25));
}

#[test]
fn vwap_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..5];
    for [high, low, close, volume] in [
        [short, &LOW, &CLOSE, &VOLUME],
        [&HIGH, short, &CLOSE, &VOLUME],
        [&HIGH, &LOW, short, &VOLUME],
        [&HIGH, &LOW, &CLOSE, short],
    ] {
        assert_eq!(
            vwap(&series(high), &series(low), &series(close), &series(volume)),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn vwap_keeps_its_precision_after_huge_volumes() {
    // A huge first volume at price 10, then many small ones at 20: plain sums
    // would drop the small products below the first one's rounding unit.
    let rows = 1_000;
    let mut price = vec![20.0; rows];
    price[0] = 10.0;
    let mut volume = vec![1.0; rows];
    volume[0] = 1.0e17;
    let output = vwap_of([&price, &price, &price, &volume]);

    let expected = (10.0 * 1.0e17 + 20.0 * 999.0) / (1.0e17 + 999.0);
    assert!(
        (output[rows - 1] - expected).abs() <= 1e-15 * expected,
        "{} != {expected}",
        output[rows - 1]
    );
}

#[test]
fn vwap_is_finite_at_the_magnitude_limit() {
    // Price times volume overflows here (1e290 * 1e290), so the kernel
    // scales the volume by a power of two: the ratios are those of the same
    // data at an ordinary scale.
    let small = [1.0, 2.0, 1.0, 3.0];
    let weights = [1.0, 3.0, 2.0, 5.0];
    let expected = vwap_of([&small, &small, &small, &weights]);

    let large = small.map(|value| value * (MAX_ABS_INPUT / 4.0));
    let output = vwap_of([
        &large,
        &large,
        &large,
        &weights.map(|w| w * (MAX_ABS_INPUT / 8.0)),
    ]);

    for (actual, expected) in output.iter().zip(&expected) {
        let expected = expected * (MAX_ABS_INPUT / 4.0);
        assert!(actual.is_finite());
        assert!(
            (actual - expected).abs() <= 1e-12 * expected.abs(),
            "{actual} != {expected}"
        );
    }
}

#[test]
fn vwap_scales_only_after_an_overflow_and_then_matches_bit_for_bit() {
    // Prices near 1e20 times volumes near 1e290 overflow. A power-of-two
    // scale changes no rounding, so the result is bit for bit that of the
    // same volumes divided by 2^500, which do not overflow.
    let prices = [3.0e20, 5.0e20, 4.0e20, 6.0e20, 7.0e20];
    let volume = [1.0e290, 2.0e289, 3.0e289, 5.0e289, 7.0e289];
    let smaller = volume.map(|value| value / 2.0_f64.powi(500));

    let output = vwap_of([&prices, &prices, &prices, &volume]);
    assert_eq!(output, vwap_of([&prices, &prices, &prices, &smaller]));
    assert!(output.iter().all(|value| value.is_finite()));
}
