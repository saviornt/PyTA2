//! Aroon kernel: outputs, warm-ups, the window of `period + 1` rows, ties,
//! TA-Lib's oscillator expression, edge cases, errors and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_trend::aroon;

const NAN: f64 = f64::NAN;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// Aroon Up, Aroon Down and the oscillator.
fn lines_of(high: &[f64], low: &[f64], period: usize) -> [Vec<f64>; 3] {
    let outputs = aroon(&series(high), &series(low), period)
        .unwrap()
        .into_outputs();
    outputs.try_into().expect("three outputs")
}

/// Aroon by its definition: rescan each window of `period + 1` rows, ties
/// to the later row, and write TA-Lib's expressions, clamped to the range.
fn reference_lines(high: &[f64], low: &[f64], period: usize) -> [Vec<f64>; 3] {
    let length = high.len();
    let factor = 100.0 / period as f64;
    let [mut up, mut down, mut osc] = [vec![NAN; period], vec![NAN; period], vec![NAN; period]];
    for today in period..length {
        let window = today - period..=today;
        let highest = window
            .clone()
            .reduce(|best, i| if high[i] >= high[best] { i } else { best })
            .unwrap();
        let lowest = window
            .reduce(|best, i| if low[i] <= low[best] { i } else { best })
            .unwrap();
        up.push((factor * (period - (today - highest)) as f64).min(100.0));
        down.push((factor * (period - (today - lowest)) as f64).min(100.0));
        osc.push((factor * (highest as f64 - lowest as f64)).clamp(-100.0, 100.0));
    }
    [up, down, osc]
}

fn assert_bits(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

/// A bumpy high/low pair whose values are not exact in binary.
fn bumpy(length: usize) -> [Vec<f64>; 2] {
    let mid: Vec<f64> = (0..length)
        .map(|i| 100.0 + (i as f64 * 0.7).sin() * 3.1 + i as f64 * 0.13)
        .collect();
    let high = mid
        .iter()
        .enumerate()
        .map(|(i, m)| m + 0.4 + (i as f64 * 1.3).cos().abs())
        .collect();
    let low = mid
        .iter()
        .enumerate()
        .map(|(i, m)| m - 0.3 - (i as f64 * 0.9).sin().abs())
        .collect();
    [high, low]
}

#[test]
fn aroon_matches_its_definition_bit_for_bit() {
    let [high, low] = bumpy(150);

    for period in [2, 3, 7, 14, 25, 149] {
        let lines = lines_of(&high, &low, period);
        let expected = reference_lines(&high, &low, period);

        for (actual, expected) in lines.iter().zip(&expected) {
            assert_bits(actual, expected);
        }
    }
}

#[test]
fn aroon_follows_the_hand_calculation() {
    // Period 2 (factor 50), windows of 3 rows. Row 2: highest high 12 on
    // row 1 (one row ago), lowest low 7 on row 0 (two ago): up 50, down 0,
    // osc 50 * (1 - 0). Row 3: high 13 is today, low 7 left the window and
    // row 3's 8 is the lowest: up 100, down 100, osc 0.
    let high = [10.0, 12.0, 11.0, 13.0];
    let low = [7.0, 9.0, 9.5, 8.0];

    let [up, down, osc] = lines_of(&high, &low, 2);

    assert_bits(&up, &[NAN, NAN, 50.0, 100.0]);
    assert_bits(&down, &[NAN, NAN, 0.0, 100.0]);
    assert_bits(&osc, &[NAN, NAN, 50.0, 0.0]);
}

#[test]
fn the_window_holds_period_plus_one_rows() {
    // Period 3: a high on row 0 is still in row 3's window (up 0) and gone
    // from row 4's; the rising low is always `period` rows old (down 0).
    let high = [20.0, 10.0, 11.0, 12.0, 13.0];
    let low = [1.0, 2.0, 3.0, 4.0, 5.0];

    let [up, down, _] = lines_of(&high, &low, 3);

    assert_eq!(up[3], 0.0);
    assert_eq!(up[4], 100.0);
    assert_eq!(down[3], 0.0);
    assert_eq!(down[4], 0.0);
}

#[test]
fn ties_go_to_the_most_recent_row() {
    // Every high equals every other in the window, so today's row is the
    // highest; the same for the lows.
    let high = [5.0, 7.0, 5.0, 7.0, 7.0, 7.0];
    let low = [1.0, 1.0, 2.0, 1.0, 2.0, 1.0];

    let [up, down, osc] = lines_of(&high, &low, 2);

    // Row 2: highs 5, 7, 5 → row 1; from row 3 a 7 is today's high.
    assert_bits(&up, &[NAN, NAN, 50.0, 100.0, 100.0, 100.0]);
    // Row 2: lows 1, 1, 2 → row 1; row 3: 1 at rows 1 and 3 → row 3.
    assert_bits(&down, &[NAN, NAN, 50.0, 100.0, 50.0, 100.0]);
    assert_bits(&osc, &[NAN, NAN, 0.0, 0.0, 50.0, 0.0]);
}

#[test]
fn a_flat_window_gives_one_hundred_both_ways() {
    let flat = vec![50.0; 30];

    let [up, down, osc] = lines_of(&flat, &flat, 14);

    assert!(up[14..].iter().all(|value| *value == 100.0));
    assert!(down[14..].iter().all(|value| *value == 100.0));
    assert!(osc[14..].iter().all(|value| *value == 0.0));
}

#[test]
fn a_steady_trend_pins_the_outputs() {
    // A falling high is O(n · period) for TA-Lib's lazy rescan; here a rising
    // series has its high today and its low `period` rows ago, and a falling
    // series the reverse.
    let rising: Vec<f64> = (0..40).map(f64::from).collect();
    let falling: Vec<f64> = rising.iter().rev().copied().collect();

    let [up, down, osc] = lines_of(&rising, &rising, 10);
    assert!(up[10..].iter().all(|value| *value == 100.0));
    assert!(down[10..].iter().all(|value| *value == 0.0));
    assert!(osc[10..].iter().all(|value| *value == 100.0));

    let [up, down, osc] = lines_of(&falling, &falling, 10);
    assert!(up[10..].iter().all(|value| *value == 0.0));
    assert!(down[10..].iter().all(|value| *value == 100.0));
    assert!(osc[10..].iter().all(|value| *value == -100.0));
}

#[test]
fn the_oscillator_is_talibs_expression_not_the_difference() {
    // `factor * (highest - lowest)` and `up - down` agree in value, but
    // with factor 100/7 they can round differently; the kernel writes the
    // former, as TA_AROONOSC does.
    let [high, low] = bumpy(200);
    let period = 7;
    let factor = 100.0 / 7.0;

    let [up, down, osc] = lines_of(&high, &low, period);

    for row in period..200 {
        assert!((osc[row] - (up[row] - down[row])).abs() <= 1e-12);
        let steps = (osc[row] / factor).round();
        assert_eq!(osc[row].to_bits(), (factor * steps).to_bits());
    }
}

#[test]
fn aroon_has_three_outputs_with_period_warm_up_rows() {
    let [high, low] = bumpy(60);

    let lines = lines_of(&high, &low, 14);

    for line in &lines {
        assert_eq!(line.len(), 60);
        assert!(line[..14].iter().all(|value| value.is_nan()));
        assert!(line[14..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn aroon_needs_period_plus_one_rows() {
    let [high, low] = bumpy(15);

    let [up, ..] = lines_of(&high, &low, 14);

    assert!(up[..14].iter().all(|value| value.is_nan()));
    assert!(up[14].is_finite());
}

#[test]
fn aroon_rejects_a_period_below_two() {
    let [high, low] = bumpy(10);

    for period in [0, 1] {
        assert_eq!(
            aroon(&series(&high), &series(&low), period),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn aroon_rejects_too_little_data() {
    let [high, low] = bumpy(14);

    assert_eq!(
        aroon(&series(&high), &series(&low), 14),
        Err(PytaError::InsufficientData {
            required: 15,
            length: 14,
        })
    );
}

#[test]
fn aroon_reports_a_huge_period_without_overflow() {
    let [high, low] = bumpy(4);

    assert_eq!(
        aroon(&series(&high), &series(&low), usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 4,
        })
    );
}

#[test]
fn aroon_rejects_columns_of_unequal_length() {
    let [high, low] = bumpy(30);

    assert_eq!(
        aroon(&series(&high), &series(&low[..29]), 2),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn aroon_ignores_the_magnitude_of_its_input() {
    // Only positions matter, so values at the limit change nothing.
    let swing: Vec<f64> = (0..64)
        .map(|i| {
            if i % 3 == 0 {
                MAX_ABS_INPUT
            } else {
                -MAX_ABS_INPUT
            }
        })
        .collect();

    let lines = lines_of(&swing, &swing, 14);
    let expected = reference_lines(&swing, &swing, 14);

    for (actual, expected) in lines.iter().zip(&expected) {
        assert_bits(actual, expected);
    }
}

#[test]
fn a_new_extreme_with_period_eleven_is_clamped_to_one_hundred() {
    // Found by proptest: `(100 / 11) * 11` rounds to 100.00000000000001,
    // which TA-Lib writes; PyTA clamps it so the range holds exactly.
    let rising: Vec<f64> = (0..20).map(f64::from).collect();
    let falling: Vec<f64> = rising.iter().rev().copied().collect();
    let eleven = std::hint::black_box(11.0_f64);
    assert!((100.0 / eleven) * eleven > 100.0);

    let [up, down, osc] = lines_of(&rising, &rising, 11);

    assert!(
        up[11..]
            .iter()
            .all(|value| value.to_bits() == 100.0_f64.to_bits())
    );
    assert!(down[11..].iter().all(|value| *value == 0.0));
    assert!(
        osc[11..]
            .iter()
            .all(|value| value.to_bits() == 100.0_f64.to_bits())
    );

    let [up, down, osc] = lines_of(&falling, &falling, 11);

    assert!(up[11..].iter().all(|value| *value == 0.0));
    assert!(
        down[11..]
            .iter()
            .all(|value| value.to_bits() == 100.0_f64.to_bits())
    );
    assert!(
        osc[11..]
            .iter()
            .all(|value| value.to_bits() == (-100.0_f64).to_bits())
    );
}
