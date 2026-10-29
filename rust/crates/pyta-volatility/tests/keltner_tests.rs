//! Keltner Channels kernel: formula, outputs, warm-ups, parameters and edge cases.

use std::path::Path;

use pyta_common::MAX_ABS_INPUT;
use pyta_core::kernels::ema;
use pyta_core::{PytaError, Series};
use pyta_volatility::{atr, keltner};

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// Upper, middle and lower channels.
fn channels_of(
    [high, low, close]: [&[f64]; 3],
    period: usize,
    atr_period: usize,
    k: f64,
) -> [Vec<f64>; 3] {
    let outputs = keltner(
        &series(high),
        &series(low),
        &series(close),
        period,
        atr_period,
        k,
    )
    .unwrap()
    .into_outputs();
    outputs.try_into().expect("three outputs")
}

/// The high, low and close columns of `tests/fixtures/ohlcv_daily.csv`
/// (300 real SPY sessions).
fn spy() -> [Vec<f64>; 3] {
    let path =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../tests/fixtures/ohlcv_daily.csv");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));
    let mut columns = [Vec::new(), Vec::new(), Vec::new()];

    // Rows are date,open,high,low,close,volume after the comments and header.
    for line in text.lines().filter(|line| !line.starts_with('#')).skip(1) {
        let fields: Vec<&str> = line.split(',').collect();
        for (column, field) in columns.iter_mut().zip(&fields[2..5]) {
            column.push(field.parse().unwrap());
        }
    }
    columns
}

/// Asserts equality bit for bit, NaN matching NaN.
fn assert_bits(actual: &[f64], expected: &[f64], what: &str) {
    assert_eq!(actual.len(), expected.len(), "{what}: length");
    for (row, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            a.to_bits() == e.to_bits() || (a.is_nan() && e.is_nan()),
            "{what}, row {row}: {a} vs {e}"
        );
    }
}

// Seven rows; true ranges from row 1: 2, 2, 2, 3, 3, 2.
const HIGH: [f64; 7] = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0];
const LOW: [f64; 7] = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0];
const CLOSE: [f64; 7] = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0];

#[test]
fn keltner_returns_three_outputs_with_input_length_and_their_own_warm_ups() {
    // period 3: the middle from row 2; atr_period 3: the bands from row 3.
    let output = keltner(&series(&HIGH), &series(&LOW), &series(&CLOSE), 3, 3, 2.0).unwrap();
    let [upper, middle, lower] = output.outputs() else {
        panic!("expected three outputs, got {}", output.output_count());
    };

    assert!(middle[..2].iter().all(|value| value.is_nan()));
    assert!(middle[2..].iter().all(|value| value.is_finite()));
    for band in [upper, lower] {
        assert_eq!(band.len(), 7);
        assert!(band[..3].iter().all(|value| value.is_nan()));
        assert!(band[3..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn keltner_bands_wait_for_the_ema_when_its_period_is_longer() {
    // period 5 (middle from row 4) against atr_period 1 (ATR from row 1):
    // the bands start with the middle, at row 4.
    let [upper, middle, lower] = channels_of([&HIGH, &LOW, &CLOSE], 5, 1, 2.0);

    for line in [&upper, &middle, &lower] {
        assert!(line[..4].iter().all(|value| value.is_nan()));
        assert!(line[4..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn keltner_matches_a_hand_calculation() {
    // EMA 3 (multiplier 1/2): seed (10 + 11 + 12) / 3 = 11, then 11, 12, 13, 13.
    // ATR 3: seed (2 + 2 + 2) / 3 = 2, then (2 * 2 + 3) / 3 = 7/3.
    let [upper, middle, lower] = channels_of([&HIGH, &LOW, &CLOSE], 3, 3, 2.0);

    assert_eq!(&middle[2..], &[11.0, 11.0, 12.0, 13.0, 13.0]);
    assert_eq!((upper[3], lower[3]), (15.0, 7.0));
    assert!((upper[4] - (12.0 + 14.0 / 3.0)).abs() < 1e-12);
    assert!((lower[4] - (12.0 - 14.0 / 3.0)).abs() < 1e-12);
}

#[test]
fn keltner_is_the_ema_plus_and_minus_k_atr_on_spy() {
    // The approved reference: PyTA's own EMA and ATR, both checked against
    // TA-Lib, combined exactly.
    let [high, low, close] = spy();
    let [upper, middle, lower] = channels_of([&high, &low, &close], 20, 10, 2.0);

    let expected_middle = ema(&close, 20);
    let average_range = atr(&series(&high), &series(&low), &series(&close), 10)
        .unwrap()
        .into_values();
    let start = 19;
    let mut expected_upper = vec![f64::NAN; close.len()];
    let mut expected_lower = vec![f64::NAN; close.len()];
    for row in start..close.len() {
        expected_upper[row] = expected_middle[row] + 2.0 * average_range[row];
        expected_lower[row] = expected_middle[row] - 2.0 * average_range[row];
    }

    assert_bits(&middle, &expected_middle, "middle");
    assert_bits(&upper, &expected_upper, "upper");
    assert_bits(&lower, &expected_lower, "lower");
}

#[test]
fn keltner_with_period_one_has_close_as_its_middle() {
    let [_, middle, _] = channels_of([&HIGH, &LOW, &CLOSE], 1, 2, 1.5);

    assert_eq!(middle, CLOSE);
}

#[test]
fn keltner_gives_three_equal_lines_on_a_flat_series() {
    let level = [105.0; 6];
    let [upper, middle, lower] = channels_of([&level, &level, &level], 3, 2, 2.0);

    for row in 2..6 {
        assert_eq!((upper[row], middle[row], lower[row]), (105.0, 105.0, 105.0));
    }
}

#[test]
fn keltner_scales_its_band_width_with_k() {
    let [upper_1, middle, lower_1] = channels_of([&HIGH, &LOW, &CLOSE], 3, 3, 1.0);
    let [upper_3, _, lower_3] = channels_of([&HIGH, &LOW, &CLOSE], 3, 3, 3.0);

    for row in 3..7 {
        let width = upper_1[row] - middle[row];
        assert!((middle[row] - lower_1[row] - width).abs() < 1e-12);
        assert!((upper_3[row] - middle[row] - 3.0 * width).abs() < 1e-12);
        assert!((middle[row] - lower_3[row] - 3.0 * width).abs() < 1e-12);
    }
}

#[test]
fn keltner_rejects_zero_period() {
    assert_eq!(
        keltner(&series(&HIGH), &series(&LOW), &series(&CLOSE), 0, 3, 2.0),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn keltner_rejects_zero_atr_period() {
    assert_eq!(
        keltner(&series(&HIGH), &series(&LOW), &series(&CLOSE), 3, 0, 2.0),
        Err(PytaError::InvalidParameter {
            name: "atr_period",
            minimum: 1,
            value: 0,
        })
    );
}

#[test]
fn keltner_rejects_a_k_that_is_not_a_finite_positive_number() {
    for k in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let error = keltner(&series(&HIGH), &series(&LOW), &series(&CLOSE), 3, 3, k).unwrap_err();

        assert!(
            matches!(error, PytaError::InvalidFloatParameter { name: "k", .. }),
            "k = {k}: {error:?}"
        );
    }
}

#[test]
fn keltner_rejects_columns_of_unequal_length() {
    assert_eq!(
        keltner(
            &series(&HIGH),
            &series(&LOW[..6]),
            &series(&CLOSE),
            3,
            3,
            2.0
        ),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn keltner_needs_enough_rows_for_both_the_ema_and_the_atr() {
    // max(period, atr_period + 1) rows: 8 in each case, one more than given.
    for (period, atr_period, required) in [(3, 7, 8), (8, 3, 8), (7, 7, 8)] {
        assert_eq!(
            keltner(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                period,
                atr_period,
                2.0
            ),
            Err(PytaError::InsufficientData {
                required,
                length: 7,
            }),
            "period {period}, atr_period {atr_period}"
        );
    }
}

#[test]
fn keltner_accepts_minimum_data() {
    // max(period, atr_period + 1) = 7 rows: one value of each output.
    for (period, atr_period) in [(7, 2), (3, 6), (7, 6)] {
        let [upper, middle, lower] = channels_of([&HIGH, &LOW, &CLOSE], period, atr_period, 2.0);

        for line in [&upper, &middle, &lower] {
            assert!(line[6].is_finite());
        }
        assert!(upper[5].is_nan() && lower[5].is_nan());
    }
}

#[test]
fn keltner_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 4];
    let low = [-MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let close = [0.0, 0.0, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let [upper, middle, lower] = channels_of([&high, &low, &close], 2, 1, 2.0);

    for line in [&upper, &middle, &lower] {
        assert!(line[1..].iter().all(|value| value.is_finite()));
    }
}
