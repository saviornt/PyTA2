//! Ichimoku Cloud kernel: formula, outputs, warm-ups, parameters and edge cases.

use std::path::Path;

use pyta_common::MAX_ABS_INPUT;
use pyta_core::kernels::{rolling_max, rolling_min};
use pyta_core::{PytaError, Series};
use pyta_trend::ichimoku;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// Tenkan-sen, kijun-sen, senkou span A, senkou span B and chikou span.
fn lines_of(
    [high, low, close]: [&[f64]; 3],
    tenkan: usize,
    kijun: usize,
    senkou: usize,
) -> [Vec<f64>; 5] {
    let outputs = ichimoku(
        &series(high),
        &series(low),
        &series(close),
        tenkan,
        kijun,
        senkou,
    )
    .unwrap()
    .into_outputs();
    outputs.try_into().expect("five outputs")
}

/// Donchian Channels' middle line, written as `donchian` writes it:
/// `(rolling max + rolling min) / 2`.
fn donchian_middle(high: &[f64], low: &[f64], period: usize) -> Vec<f64> {
    let (upper, lower) = (rolling_max(high, period), rolling_min(low, period));
    upper
        .iter()
        .zip(&lower)
        .map(|(top, bottom)| (top + bottom) / 2.0)
        .collect()
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

// Seven rows.
const HIGH: [f64; 7] = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0];
const LOW: [f64; 7] = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0];
const CLOSE: [f64; 7] = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0];

#[test]
fn ichimoku_returns_five_outputs_with_input_length_and_their_own_warm_ups() {
    // tenkan 2 from row 1, kijun 3 from row 2, senkou A from row 2, senkou
    // B 5 from row 4, chikou from row 0.
    let output = ichimoku(&series(&HIGH), &series(&LOW), &series(&CLOSE), 2, 3, 5).unwrap();
    assert_eq!(output.output_count(), 5);

    for (line, first) in output.outputs().iter().zip([1, 2, 2, 4, 0]) {
        assert_eq!(line.len(), 7);
        assert!(line[..first].iter().all(|value| value.is_nan()));
        assert!(line[first..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn ichimoku_senkou_a_waits_for_the_longer_of_tenkan_and_kijun() {
    // tenkan 4 against kijun 2: senkou span A starts with the tenkan-sen,
    // at row 3, although the kijun-sen starts at row 1.
    let [tenkan, kijun, senkou_a, _, _] = lines_of([&HIGH, &LOW, &CLOSE], 4, 2, 1);

    assert!(kijun[1].is_finite());
    assert!(tenkan[..3].iter().all(|value| value.is_nan()));
    assert!(senkou_a[..3].iter().all(|value| value.is_nan()));
    assert!(senkou_a[3..].iter().all(|value| value.is_finite()));
}

#[test]
fn ichimoku_matches_a_hand_calculation() {
    // tenkan 2: row 2 = (max(12, 13) + min(10, 11)) / 2 = 11.5.
    // kijun 3: row 2 = (13 + 9) / 2 = 11; senkou A row 2 = (11.5 + 11) / 2.
    // senkou 5: row 4 = (max(11..14) + min(9..11)) / 2 = (14 + 9) / 2.
    let [tenkan, kijun, senkou_a, senkou_b, chikou] = lines_of([&HIGH, &LOW, &CLOSE], 2, 3, 5);

    assert_eq!(&tenkan[1..], &[10.5, 11.5, 11.5, 12.0, 13.0, 13.5]);
    assert_eq!(&kijun[2..], &[11.0, 11.5, 12.0, 12.5, 13.0]);
    assert_eq!(&senkou_a[2..], &[11.25, 11.5, 12.0, 12.75, 13.25]);
    assert_eq!(&senkou_b[4..], &[11.5, 12.5, 12.5]);
    assert_eq!(chikou, CLOSE);
}

#[test]
fn ichimoku_lines_are_donchian_middles_on_spy() {
    // The approved reference: each midpoint is Donchian's middle line bit for
    // bit (the engine test checks the same against `donchian` itself);
    // senkou span A is their average and the chikou span is close.
    let [high, low, close] = spy();
    let [tenkan, kijun, senkou_a, senkou_b, chikou] = lines_of([&high, &low, &close], 9, 26, 52);

    let expected_tenkan = donchian_middle(&high, &low, 9);
    let expected_kijun = donchian_middle(&high, &low, 26);
    let expected_senkou_a: Vec<f64> = expected_tenkan
        .iter()
        .zip(&expected_kijun)
        .map(|(conversion, base)| (conversion + base) / 2.0)
        .collect();

    assert_bits(&tenkan, &expected_tenkan, "tenkan");
    assert_bits(&kijun, &expected_kijun, "kijun");
    assert_bits(&senkou_a, &expected_senkou_a, "senkou_a");
    assert_bits(&senkou_b, &donchian_middle(&high, &low, 52), "senkou_b");
    assert_bits(&chikou, &close, "chikou");
}

#[test]
fn ichimoku_with_windows_of_one_is_the_row_midpoint() {
    let [tenkan, kijun, senkou_a, senkou_b, _] = lines_of([&HIGH, &LOW, &CLOSE], 1, 1, 1);
    let midpoints: Vec<f64> = HIGH.iter().zip(&LOW).map(|(h, l)| (h + l) / 2.0).collect();

    for line in [&tenkan, &kijun, &senkou_a, &senkou_b] {
        assert_eq!(line, &midpoints);
    }
}

#[test]
fn ichimoku_accepts_windows_in_any_order() {
    // No ordering between the windows: tenkan longer than kijun and senkou.
    let [tenkan, kijun, senkou_a, senkou_b, _] = lines_of([&HIGH, &LOW, &CLOSE], 5, 3, 2);

    assert_eq!(tenkan[4], 11.5); // (14 + 9) / 2
    assert_eq!(kijun[4], 12.0); // (14 + 10) / 2
    assert_eq!(senkou_a[4], 11.75);
    assert_eq!(senkou_b[1], 10.5); // (12 + 9) / 2
}

#[test]
fn ichimoku_gives_one_level_on_a_flat_series() {
    let level = [105.0; 6];
    let [tenkan, kijun, senkou_a, senkou_b, chikou] = lines_of([&level, &level, &level], 2, 3, 4);

    for line in [&tenkan, &kijun, &senkou_a, &senkou_b, &chikou] {
        assert!(line[3..].iter().all(|value| *value == 105.0));
    }
}

#[test]
fn ichimoku_rejects_a_zero_window_naming_it() {
    for (windows, name) in [
        ((0, 3, 5), "tenkan"),
        ((2, 0, 5), "kijun"),
        ((2, 3, 0), "senkou"),
    ] {
        let (tenkan, kijun, senkou) = windows;
        assert_eq!(
            ichimoku(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                tenkan,
                kijun,
                senkou
            ),
            Err(PytaError::InvalidParameter {
                name,
                minimum: 1,
                value: 0,
            })
        );
    }
}

#[test]
fn ichimoku_rejects_columns_of_unequal_length() {
    for [high, low, close] in [
        [&HIGH[..6], &LOW[..], &CLOSE[..]],
        [&HIGH[..], &LOW[..6], &CLOSE[..]],
        [&HIGH[..], &LOW[..], &CLOSE[..6]],
    ] {
        assert_eq!(
            ichimoku(&series(high), &series(low), &series(close), 2, 3, 5),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn ichimoku_needs_rows_for_its_longest_window() {
    // max(tenkan, kijun, senkou) rows: 8 in each case, one more than given.
    for (tenkan, kijun, senkou) in [(8, 3, 5), (2, 8, 5), (2, 3, 8)] {
        assert_eq!(
            ichimoku(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                tenkan,
                kijun,
                senkou
            ),
            Err(PytaError::InsufficientData {
                required: 8,
                length: 7,
            }),
            "windows {tenkan}, {kijun}, {senkou}"
        );
    }
}

#[test]
fn ichimoku_reports_a_huge_window_without_overflow() {
    assert_eq!(
        ichimoku(
            &series(&HIGH),
            &series(&LOW),
            &series(&CLOSE),
            2,
            3,
            usize::MAX
        ),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 7,
        })
    );
}

#[test]
fn ichimoku_accepts_minimum_data() {
    // max(tenkan, kijun, senkou) = 7 rows: every output has a value on row 6.
    for (tenkan, kijun, senkou) in [(7, 2, 3), (2, 7, 3), (2, 3, 7)] {
        let lines = lines_of([&HIGH, &LOW, &CLOSE], tenkan, kijun, senkou);

        for line in &lines {
            assert!(line[6].is_finite());
        }
    }
}

#[test]
fn ichimoku_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 4];
    let low = [-MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let close = [0.0, 0.0, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let lines = lines_of([&high, &low, &close], 1, 2, 3);

    for line in &lines {
        assert!(line[2..].iter().all(|value| value.is_finite()));
    }
}
