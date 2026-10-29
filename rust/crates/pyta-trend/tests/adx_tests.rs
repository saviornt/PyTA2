//! ADX kernel: outputs, warm-ups, TA-Lib's seeding and zero guards, edge
//! cases, errors and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::adx;

const NAN: f64 = f64::NAN;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// ADX, +DI and -DI.
fn lines_of([high, low, close]: [&[f64]; 3], period: usize) -> [Vec<f64>; 3] {
    let outputs = adx(&series(high), &series(low), &series(close), period)
        .unwrap()
        .into_outputs();
    outputs.try_into().expect("three outputs")
}

/// ADX by its definition, one line at a time: the directional movements
/// and true ranges first, then each Wilder sum, then the DIs, then DX and
/// ADX, with TA-Lib's guards.
fn reference_lines(high: &[f64], low: &[f64], close: &[f64], period: usize) -> [Vec<f64>; 3] {
    let length = close.len();
    let inverse = 1.0 / period as f64;
    let mut plus_dm = vec![0.0; length];
    let mut minus_dm = vec![0.0; length];
    let mut range = vec![0.0; length];
    for i in 1..length {
        let up = high[i] - high[i - 1];
        let down = low[i - 1] - low[i];
        plus_dm[i] = if up > 0.0 && up > down { up } else { 0.0 };
        minus_dm[i] = if down > 0.0 && down > up { down } else { 0.0 };
        range[i] = (high[i] - low[i])
            .max((high[i] - close[i - 1]).abs())
            .max((low[i] - close[i - 1]).abs());
    }
    let smooth = |values: &[f64]| {
        let mut sums = vec![NAN; length];
        let mut sum: f64 = values[1..period].iter().sum();
        for i in period..length {
            sum = sum - sum * inverse + values[i];
            sums[i] = sum;
        }
        sums
    };
    let (plus_sum, minus_sum, range_sum) = (smooth(&plus_dm), smooth(&minus_dm), smooth(&range));

    let mut plus_di = vec![NAN; length];
    let mut minus_di = vec![NAN; length];
    let mut dx = vec![None; length];
    for i in period..length {
        if range_sum[i] > 0.0 {
            plus_di[i] = 100.0 * (plus_sum[i] / range_sum[i]);
            minus_di[i] = 100.0 * (minus_sum[i] / range_sum[i]);
            let total = plus_di[i] + minus_di[i];
            if total.abs() >= 1e-14 {
                dx[i] = Some(100.0 * ((plus_di[i] - minus_di[i]).abs() / total));
            }
        } else {
            plus_di[i] = 0.0;
            minus_di[i] = 0.0;
        }
    }

    let first = 2 * period - 1;
    let mut adx = vec![NAN; length];
    let mut average = dx[period..=first].iter().flatten().sum::<f64>() / period as f64;
    adx[first] = average;
    for i in first + 1..length {
        if let Some(dx) = dx[i] {
            average = average - (average - dx) * inverse;
        }
        adx[i] = average;
    }
    [adx, plus_di, minus_di]
}

fn assert_close(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || (a - e).abs() <= 1.0e-12 * e.abs().max(1.0),
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

/// A bumpy OHLC table whose values are not exact in binary.
fn bumpy(length: usize) -> [Vec<f64>; 3] {
    let close: Vec<f64> = (0..length)
        .map(|i| 100.0 + (i as f64 * 0.7).sin() * 3.1 + i as f64 * 0.13)
        .collect();
    let high = close
        .iter()
        .enumerate()
        .map(|(i, c)| c + 0.4 + (i as f64 * 1.3).cos().abs())
        .collect();
    let low = close
        .iter()
        .enumerate()
        .map(|(i, c)| c - 0.3 - (i as f64 * 0.9).sin().abs())
        .collect();
    [high, low, close]
}

#[test]
fn adx_matches_its_definition() {
    let [high, low, close] = bumpy(150);

    for period in [2, 3, 14, 30] {
        let lines = lines_of([&high, &low, &close], period);
        let expected = reference_lines(&high, &low, &close, period);

        for (actual, expected) in lines.iter().zip(&expected) {
            assert_close(actual, expected);
        }
    }
}

#[test]
fn adx_follows_the_hand_calculation() {
    // Period 2. Row 1: +DM 2, TR 3 (the seeds). Row 2: +DM 1, TR 3, so the
    // sums are 2 - 1 + 1 = 2 and 3 - 1.5 + 3 = 4.5: +DI 100 * 2 / 4.5, -DI 0,
    // DX 100. Row 3: -DM 2, TR 4: sums +1, -2, 6.25: +DI 16, -DI 32,
    // DX 100 * 16 / 48. The first ADX is the mean of the two DX values.
    let high = [10.0, 12.0, 13.0, 12.0];
    let low = [8.0, 9.0, 10.0, 8.0];
    let close = [9.0, 11.0, 12.0, 9.0];

    let [adx, plus_di, minus_di] = lines_of([&high, &low, &close], 2);

    assert_close(&plus_di, &[NAN, NAN, 100.0 * (2.0 / 4.5), 16.0]);
    assert_close(&minus_di, &[NAN, NAN, 0.0, 32.0]);
    assert_close(&adx, &[NAN, NAN, NAN, (100.0 + 100.0 / 3.0) / 2.0]);
}

#[test]
fn adx_has_three_outputs_with_their_own_warm_ups() {
    let [high, low, close] = bumpy(60);
    let period = 14;

    let lines = lines_of([&high, &low, &close], period);

    for line in &lines {
        assert_eq!(line.len(), 60);
    }
    let [adx, plus_di, minus_di] = lines;
    assert!(adx[..2 * period - 1].iter().all(|value| value.is_nan()));
    assert!(adx[2 * period - 1..].iter().all(|value| value.is_finite()));
    for di in [plus_di, minus_di] {
        assert!(di[..period].iter().all(|value| value.is_nan()));
        assert!(di[period..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn adx_needs_twice_its_period() {
    let [high, low, close] = bumpy(20);

    let [adx, ..] = lines_of([&high, &low, &close], 10);

    assert!(adx[..19].iter().all(|value| value.is_nan()));
    assert!(adx[19].is_finite());
}

#[test]
fn a_tie_between_the_moves_counts_neither() {
    // Row 1's high rises 1 and its low falls 1: neither move is larger, so
    // both DMs are 0 (the seeds); row 2 moves only up, so -DI stays 0.
    let high = [10.0, 11.0, 12.0, 13.0];
    let low = [9.0, 8.0, 9.0, 10.0];
    let close = [9.5, 9.5, 11.0, 12.0];

    let [_, plus_di, minus_di] = lines_of([&high, &low, &close], 2);
    let expected = reference_lines(&high, &low, &close, 2);

    assert_close(&plus_di, &expected[1]);
    assert_close(&minus_di, &expected[2]);
    assert_eq!(minus_di[2], 0.0);
}

#[test]
fn a_series_flat_from_its_start_gives_zero() {
    // The true-range sum stays 0: both DIs are 0 and no DX is taken, so
    // the first ADX's mean is 0 and stays there.
    let flat = vec![50.0; 40];

    let [adx, plus_di, minus_di] = lines_of([&flat, &flat, &flat], 14);

    assert!(plus_di[14..].iter().all(|value| *value == 0.0));
    assert!(minus_di[14..].iter().all(|value| *value == 0.0));
    assert!(adx[27..].iter().all(|value| *value == 0.0));
}

#[test]
fn on_a_flat_stretch_the_dis_hold_their_values() {
    // After movement the sums shrink by the same factor each flat row, so
    // the DIs keep (to rounding) their last values and ADX moves towards
    // their DX.
    let [mut high, mut low, mut close] = bumpy(50);
    let last = close[49];
    high.extend([last; 30]);
    low.extend([last; 30]);
    close.extend([last; 30]);

    let [adx, plus_di, minus_di] = lines_of([&high, &low, &close], 14);
    let expected = reference_lines(&high, &low, &close, 14);

    assert_close(&adx, &expected[0]);
    // Row 50 still sees the jump from row 49's range to the flat price.
    for di in [&plus_di, &minus_di] {
        for value in &di[52..] {
            assert!((value - di[51]).abs() <= 1e-9 * di[51].abs().max(1.0));
        }
    }
    let target = 100.0 * (plus_di[79] - minus_di[79]).abs() / (plus_di[79] + minus_di[79]);
    assert!((adx[79] - target).abs() < (adx[55] - target).abs());
}

#[test]
fn adx_rejects_a_period_below_two() {
    let [high, low, close] = bumpy(10);

    for period in [0, 1] {
        assert_eq!(
            adx(&series(&high), &series(&low), &series(&close), period),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn adx_rejects_too_little_data() {
    let [high, low, close] = bumpy(27);

    assert_eq!(
        adx(&series(&high), &series(&low), &series(&close), 14),
        Err(PytaError::InsufficientData {
            required: 28,
            length: 27,
        })
    );
}

#[test]
fn adx_reports_a_huge_period_without_overflow() {
    let [high, low, close] = bumpy(4);

    assert_eq!(
        adx(&series(&high), &series(&low), &series(&close), usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 4,
        })
    );
}

#[test]
fn adx_rejects_columns_of_unequal_length() {
    let [high, low, close] = bumpy(30);

    assert_eq!(
        adx(&series(&high), &series(&low[..29]), &series(&close), 2),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn adx_stays_finite_at_the_magnitude_limit() {
    let swing: Vec<f64> = (0..64)
        .map(|i| {
            if i % 2 == 0 {
                MAX_ABS_INPUT
            } else {
                -MAX_ABS_INPUT
            }
        })
        .collect();
    let constant = vec![MAX_ABS_INPUT; 64];

    for column in [swing, constant] {
        let lines = lines_of([&column, &column, &column], 14);

        for line in &lines {
            assert!(line[27..].iter().all(|value| value.is_finite()));
        }
    }
}
