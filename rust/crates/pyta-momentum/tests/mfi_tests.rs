//! Money Flow Index kernel: formula, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::mfi;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn mfi_of([high, low, close, volume]: [&[f64]; 4], period: usize) -> Vec<f64> {
    mfi(
        &series(high),
        &series(low),
        &series(close),
        &series(volume),
        period,
    )
    .unwrap()
    .values()
    .to_vec()
}

// Six rows; typical prices 9, 10, 11, 10, 10, 12.
const HIGH: [f64; 6] = [10.0, 11.0, 12.0, 11.0, 11.0, 13.0];
const LOW: [f64; 6] = [8.0, 9.0, 10.0, 9.0, 9.0, 11.0];
const CLOSE: [f64; 6] = [9.0, 10.0, 11.0, 10.0, 10.0, 12.0];
const VOLUME: [f64; 6] = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0];

#[test]
fn mfi_has_input_length_and_period_warm_up() {
    for period in 2..=5 {
        let output = mfi_of([&HIGH, &LOW, &CLOSE, &VOLUME], period);

        assert_eq!(output.len(), 6);
        assert!(output[..period].iter().all(|value| value.is_nan()));
        assert!(output[period..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn mfi_matches_a_hand_calculation() {
    // Flows by row: 1 up 10 * 200 = 2000, 2 up 11 * 300 = 3300, 3 down
    // 10 * 400 = 4000, 4 unchanged (neither), 5 up 12 * 600 = 7200.
    // Period 3: row 3 = 5300 / 9300, row 4 = 3300 / 7300, row 5 = 7200 /
    // 11200.
    let output = mfi_of([&HIGH, &LOW, &CLOSE, &VOLUME], 3);

    assert!(output[..3].iter().all(|value| value.is_nan()));
    assert_eq!(
        output[3..],
        [
            100.0 * (5300.0 / 9300.0),
            100.0 * (3300.0 / 7300.0),
            100.0 * (7200.0 / 11200.0),
        ]
    );
}

#[test]
fn mfi_is_100_with_only_rising_prices_and_0_with_only_falling_ones() {
    let rising = [1.0, 2.0, 3.0, 4.0];
    let falling = [4.0, 3.0, 2.0, 1.0];
    let volume = [10.0; 4];

    assert_eq!(
        mfi_of([&rising, &rising, &rising, &volume], 2)[2..],
        [100.0, 100.0]
    );
    assert_eq!(
        mfi_of([&falling, &falling, &falling, &volume], 2)[2..],
        [0.0, 0.0]
    );
}

#[test]
fn mfi_is_zero_for_a_window_without_money_flow() {
    // TA-Lib 0.8.3: an unchanged typical price is neither positive nor
    // negative, so a flat window (with volume) has no money flow -> 0.
    let level = [105.0; 6];
    let output = mfi_of([&level, &level, &level, &VOLUME], 3);
    assert!(output[3..].iter().all(|value| *value == 0.0));

    // Moving prices without volume give no money flow either.
    let output = mfi_of([&HIGH, &LOW, &CLOSE, &[0.0; 6]], 3);
    assert!(output[3..].iter().all(|value| *value == 0.0));
}

#[test]
fn mfi_treats_a_change_within_rounding_of_its_prices_as_unchanged() {
    // A change of 1e-9 against typical prices near 1e6 is below
    // `1e-14 * (|a| + |b|)` = 2e-8 (`TA_IS_ZERO_SCALED`): no flow, so with a
    // rise before it the window is all positive. Near 1 it is a real fall.
    let prices = [1.0e6, 1.0e6 + 1.0, 1.0e6 + 1.0 - 1.0e-9];
    let output = mfi_of([&prices, &prices, &prices, &[1.0; 3]], 2);
    assert_eq!(output[2], 100.0);

    let prices = [1.0, 2.0, 2.0 - 1.0e-9];
    let output = mfi_of([&prices, &prices, &prices, &[1.0; 3]], 2);
    assert!(output[2] < 100.0, "{}", output[2]);
}

#[test]
fn mfi_resets_its_sums_after_a_window_without_money_flow() {
    // Rows 1-2 move, rows 3-5 are flat: after `period` (3) empty rows the
    // sums are exactly 0, so row 5 is 0 with no add-then-subtract residue,
    // and row 6's single rise gives exactly 100.
    let prices = [0.1, 0.3, 0.7, 0.7, 0.7, 0.7, 0.9];
    let volume = [3.0; 7];
    let output = mfi_of([&prices, &prices, &prices, &volume], 3);

    assert_eq!(output[5], 0.0);
    assert_eq!(output[6], 100.0);
}

#[test]
fn mfi_rejects_a_period_below_2() {
    for period in [0, 1] {
        assert_eq!(
            mfi(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                &series(&VOLUME),
                period
            ),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn mfi_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..5];
    for [high, low, close, volume] in [
        [short, &LOW, &CLOSE, &VOLUME],
        [&HIGH, short, &CLOSE, &VOLUME],
        [&HIGH, &LOW, short, &VOLUME],
        [&HIGH, &LOW, &CLOSE, short],
    ] {
        assert_eq!(
            mfi(
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
fn mfi_needs_period_plus_1_rows() {
    let columns = [&HIGH, &LOW, &CLOSE, &VOLUME].map(|values| series(values));
    let [high, low, close, volume] = &columns;

    assert_eq!(
        mfi(high, low, close, volume, 6),
        Err(PytaError::InsufficientData {
            required: 7,
            length: 6,
        })
    );
    assert_eq!(
        mfi(high, low, close, volume, usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 6,
        })
    );
}

#[test]
fn mfi_accepts_minimum_data() {
    // `period + 1` rows give one value, on the last row: flows +2000,
    // +3300, -4000, neither, +7200 -> 12500 / 16500.
    let output = mfi_of([&HIGH, &LOW, &CLOSE, &VOLUME], 5);

    assert!(output[..5].iter().all(|value| value.is_nan()));
    assert_eq!(output[5], 100.0 * (12500.0 / 16500.0));
}

#[test]
fn mfi_is_finite_at_the_magnitude_limit() {
    // Price times volume overflows here (1e290 * 1e290), so the kernel
    // scales the volume by a power of two: the ratios are those of the
    // same data at an ordinary scale.
    let small = [1.0, 2.0, 1.0, 3.0];
    let expected = mfi_of([&small, &small, &small, &[1.0; 4]], 2);

    let large = small.map(|value| value * (MAX_ABS_INPUT / 4.0));
    let output = mfi_of([&large, &large, &large, &[MAX_ABS_INPUT; 4]], 2);

    for (actual, expected) in output[2..].iter().zip(&expected[2..]) {
        assert!(actual.is_finite());
        assert!((actual - expected).abs() < 1e-12, "{actual} != {expected}");
    }
}

#[test]
fn mfi_scales_only_after_an_overflow_and_then_matches_bit_for_bit() {
    // Prices near 1e20 times volumes near 1e290 overflow. A power-of-two
    // scale changes no rounding, so the result is bit for bit that of the
    // same volumes divided by 2^500, which do not overflow.
    let prices = [3.0e20, 5.0e20, 4.0e20, 6.0e20, 7.0e20];
    let volume = [1.0e290, 2.0e289, 3.0e289, 5.0e289, 7.0e289];
    let smaller = volume.map(|value| value / 2.0_f64.powi(500));

    let output = mfi_of([&prices, &prices, &prices, &volume], 2);
    assert_eq!(
        output[2..],
        mfi_of([&prices, &prices, &prices, &smaller], 2)[2..]
    );
    assert!(output[2..].iter().all(|value| value.is_finite()));
}
