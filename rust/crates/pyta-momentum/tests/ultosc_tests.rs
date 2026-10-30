//! Ultimate Oscillator kernel: formula, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::ultosc;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn ultosc_of([high, low, close]: [&[f64]; 3], [short, medium, long]: [usize; 3]) -> Vec<f64> {
    ultosc(
        &series(high),
        &series(low),
        &series(close),
        short,
        medium,
        long,
    )
    .unwrap()
    .values()
    .to_vec()
}

fn error_of([short, medium, long]: [usize; 3]) -> PytaError {
    ultosc(
        &series(&HIGH),
        &series(&LOW),
        &series(&CLOSE),
        short,
        medium,
        long,
    )
    .unwrap_err()
}

// Seven rows. Rows 1-6: buying pressure 2, 1, 1, 1, 3, 0 and true range 3,
// 2, 3, 2, 4, 2.
const HIGH: [f64; 7] = [10.0, 12.0, 13.0, 11.0, 12.0, 15.0, 14.0];
const LOW: [f64; 7] = [8.0, 9.0, 11.0, 9.0, 10.0, 11.0, 12.0];
const CLOSE: [f64; 7] = [9.0, 11.0, 12.0, 10.0, 11.0, 14.0, 12.0];

#[test]
fn ultosc_has_input_length_and_long_warm_up() {
    for windows in [[1, 2, 3], [2, 3, 5], [1, 3, 6]] {
        let output = ultosc_of([&HIGH, &LOW, &CLOSE], windows);
        let long = windows[2];

        assert_eq!(output.len(), 7);
        assert!(output[..long].iter().all(|value| value.is_nan()));
        assert!(output[long..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn ultosc_matches_a_hand_calculation() {
    // Windows 1, 2, 3. Row 3: 1/3, 2/5, 4/8; row 4: 1/2, 2/5, 3/7; row 5:
    // 3/4, 4/6, 5/9; row 6: 0/2, 3/6, 4/8.
    let output = ultosc_of([&HIGH, &LOW, &CLOSE], [1, 2, 3]);
    let ultosc = |a: f64, b: f64, c: f64| 100.0 * ((4.0 * a + 2.0 * b + c) / 7.0);

    assert!(output[..3].iter().all(|value| value.is_nan()));
    assert_eq!(
        output[3..],
        [
            ultosc(1.0 / 3.0, 2.0 / 5.0, 4.0 / 8.0),
            ultosc(1.0 / 2.0, 2.0 / 5.0, 3.0 / 7.0),
            ultosc(3.0 / 4.0, 4.0 / 6.0, 5.0 / 9.0),
            ultosc(0.0 / 2.0, 3.0 / 6.0, 4.0 / 8.0),
        ]
    );
}

#[test]
fn ultosc_uses_the_previous_close_for_the_true_low_and_range() {
    // Row 1 gaps up: low 20 above the previous close 10, so the true low is
    // 10 and the true range 22 - 10 = 12; close 21 gives pressure 11. Rows 2
    // and 3 tie their low with the previous close: pressure 1, range 2.
    let high = [11.0, 22.0, 23.0, 24.0];
    let low = [9.0, 20.0, 21.0, 22.0];
    let close = [10.0, 21.0, 22.0, 23.0];
    let output = ultosc_of([&high, &low, &close], [1, 2, 3]);

    assert!(output[..3].iter().all(|value| value.is_nan()));
    assert_eq!(
        output[3],
        100.0 * ((4.0 * (1.0 / 2.0) + 2.0 * (2.0 / 4.0) + 13.0 / 16.0) / 7.0)
    );
}

#[test]
fn ultosc_is_zero_on_a_flat_stretch_and_drops_a_flat_window() {
    // TA-Lib 0.8.3: a window whose true ranges sum to 0 drops its term and
    // the divisor stays 7; a fully flat stretch gives 0.
    let level = [105.0; 8];
    let output = ultosc_of([&level, &level, &level], [1, 2, 3]);
    assert!(output[3..].iter().all(|value| *value == 0.0));

    // One move (row 1: pressure 2.5, range 2.5), then flat rows at the
    // previous close. Row 3: the short and medium windows are flat and
    // dropped, the long one holds row 1 -> 100 * (1 / 7). Row 4: all flat.
    let high = [10.0, 12.0, 12.0, 12.0, 12.0];
    let low = [9.0, 11.0, 12.0, 12.0, 12.0];
    let close = [9.5, 12.0, 12.0, 12.0, 12.0];
    let output = ultosc_of([&high, &low, &close], [1, 2, 3]);

    assert_eq!(output[3..], [100.0 * (1.0 / 7.0), 0.0]);
}

#[test]
fn ultosc_rejects_a_zero_window() {
    for (windows, name) in [
        ([0, 2, 3], "short"),
        ([1, 0, 3], "medium"),
        ([1, 2, 0], "long"),
    ] {
        assert_eq!(
            error_of(windows),
            PytaError::InvalidParameter {
                name,
                minimum: 1,
                value: 0,
            }
        );
    }
}

#[test]
fn ultosc_rejects_windows_out_of_order() {
    // TA-Lib sorts them silently; PyTA requires short < medium < long.
    for (windows, lower, upper) in [
        ([2, 2, 3], "short", "medium"),
        ([3, 2, 4], "short", "medium"),
        ([1, 3, 3], "medium", "long"),
        ([1, 4, 3], "medium", "long"),
    ] {
        let [short, medium, long] = windows.map(|value| value as f64);
        let (lower_value, upper_value) = if lower == "short" {
            (short, medium)
        } else {
            (medium, long)
        };
        assert_eq!(
            error_of(windows),
            PytaError::ParametersOutOfOrder {
                lower,
                lower_value,
                upper,
                upper_value,
                strict: true,
            }
        );
    }
    assert_eq!(
        error_of([3, 2, 1]).to_string(),
        "short must be less than medium, got short=3 and medium=2"
    );
}

#[test]
fn ultosc_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..6];
    for [high, low, close] in [
        [short, &LOW, &CLOSE],
        [&HIGH, short, &CLOSE],
        [&HIGH, &LOW, short],
    ] {
        assert_eq!(
            ultosc(&series(high), &series(low), &series(close), 1, 2, 3),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn ultosc_needs_long_plus_1_rows() {
    assert_eq!(
        error_of([1, 2, 7]),
        PytaError::InsufficientData {
            required: 8,
            length: 7,
        }
    );
    assert_eq!(
        error_of([1, 2, usize::MAX]),
        PytaError::InsufficientData {
            required: usize::MAX,
            length: 7,
        }
    );
}

#[test]
fn ultosc_accepts_minimum_data() {
    // `long + 1` rows give one value, on the last row.
    let output = ultosc_of([&HIGH, &LOW, &CLOSE], [2, 4, 6]);

    assert!(output[..6].iter().all(|value| value.is_nan()));
    assert!(output[6].is_finite());
}

#[test]
fn ultosc_stays_between_0_and_100_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 5];
    let low = [-MAX_ABS_INPUT; 5];
    let close = [0.0, MAX_ABS_INPUT, -MAX_ABS_INPUT, 0.0, MAX_ABS_INPUT];
    let output = ultosc_of([&high, &low, &close], [1, 2, 3]);

    for value in &output[3..] {
        assert!((0.0..=100.0).contains(value), "{value}");
    }
}
