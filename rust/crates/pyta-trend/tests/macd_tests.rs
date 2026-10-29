//! MACD kernel: outputs, warm-up per output, the fast/slow swap and errors.

use pyta_core::{IndicatorOutput, PytaError, Series};
use pyta_trend::macd;

/// A rising ramp 1, 2, 3, ...: an SMA-seeded EMA of it lags by exactly
/// `(period - 1) / 2`, so MACD of a ramp is `(slow - fast) / 2`.
fn ramp(length: usize) -> Series {
    Series::new((1..=length).map(|i| i as f64).collect()).unwrap()
}

fn wave(length: usize) -> Series {
    Series::new(
        (0..length)
            .map(|i| (i as f64 * 0.37).sin() * 5.0 + 100.0)
            .collect(),
    )
    .unwrap()
}

fn outputs(output: &IndicatorOutput) -> [&[f64]; 3] {
    let [line, signal, hist] = output.outputs() else {
        panic!("expected three outputs, got {}", output.output_count());
    };

    [line, signal, hist]
}

fn assert_close(actual: &[f64], expected: f64) {
    for (index, value) in actual.iter().enumerate() {
        assert!(
            (value - expected).abs() <= 1e-12,
            "index {index}: got {value}, expected {expected}"
        );
    }
}

/// Element-wise equality, with NaN equal to NaN.
fn assert_same(left: &[f64], right: &[f64]) {
    assert_eq!(left.len(), right.len());
    for (index, (a, b)) in left.iter().zip(right).enumerate() {
        assert!(
            (a.is_nan() && b.is_nan()) || a == b,
            "index {index}: {a} != {b}"
        );
    }
}

#[test]
fn macd_returns_line_signal_and_histogram() {
    let output = macd(&ramp(10), 2, 4, 2).unwrap();
    let [line, signal, hist] = outputs(&output);

    assert_eq!(output.len(), 10);
    assert_close(&line[3..], 1.0);
    assert_close(&signal[4..], 1.0);
    assert_close(&hist[4..], 0.0);
}

#[test]
fn each_output_has_its_own_warm_up() {
    let (fast, slow, signal_period) = (3, 7, 4);
    let output = macd(&wave(40), fast, slow, signal_period).unwrap();
    let [line, signal, hist] = outputs(&output);

    let line_start = slow - 1;
    let signal_start = slow + signal_period - 2;

    assert!(line[..line_start].iter().all(|value| value.is_nan()));
    assert!(line[line_start..].iter().all(|value| value.is_finite()));
    for series in [signal, hist] {
        assert!(series[..signal_start].iter().all(|value| value.is_nan()));
        assert!(series[signal_start..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn the_histogram_is_macd_minus_signal() {
    let output = macd(&wave(60), 12, 26, 9).unwrap();
    let [line, signal, hist] = outputs(&output);

    for index in 33..60 {
        assert_eq!(hist[index], line[index] - signal[index]);
    }
}

#[test]
fn slow_below_fast_is_swapped() {
    let input = wave(50);

    let swapped = macd(&input, 26, 12, 9).unwrap();
    let ordered = macd(&input, 12, 26, 9).unwrap();

    for (left, right) in swapped.outputs().iter().zip(ordered.outputs()) {
        assert_same(left, right);
    }
}

#[test]
fn equal_fast_and_slow_give_zeros() {
    let output = macd(&wave(30), 5, 5, 3).unwrap();
    let [line, signal, hist] = outputs(&output);

    assert!(line[4..].iter().all(|value| *value == 0.0));
    assert!(signal[6..].iter().all(|value| *value == 0.0));
    assert!(hist[6..].iter().all(|value| *value == 0.0));
}

#[test]
fn constant_input_gives_zeros() {
    let output = macd(&Series::new(vec![7.25; 40]).unwrap(), 12, 26, 9).unwrap();
    let [line, signal, hist] = outputs(&output);

    assert!(line[25..].iter().all(|value| *value == 0.0));
    assert!(signal[33..].iter().all(|value| *value == 0.0));
    assert!(hist[33..].iter().all(|value| *value == 0.0));
}

#[test]
fn the_minimum_input_gives_every_output_one_value() {
    // slow + signal - 1 = 26 + 9 - 1 = 34 values.
    let output = macd(&wave(34), 12, 26, 9).unwrap();
    let [line, signal, hist] = outputs(&output);

    assert_eq!(line.iter().filter(|value| value.is_finite()).count(), 9);
    assert!(signal[33].is_finite() && signal[..33].iter().all(|value| value.is_nan()));
    assert!(hist[33].is_finite() && hist[..33].iter().all(|value| value.is_nan()));
}

#[test]
fn input_shorter_than_slow_plus_signal_minus_one_is_rejected() {
    assert_eq!(
        macd(&wave(33), 12, 26, 9),
        Err(PytaError::InsufficientData {
            required: 34,
            length: 33,
        })
    );
    // The requirement is counted after the swap.
    assert_eq!(
        macd(&wave(33), 26, 12, 9),
        Err(PytaError::InsufficientData {
            required: 34,
            length: 33,
        })
    );
}

#[test]
fn parameters_below_their_minimum_are_rejected_by_name() {
    let input = wave(50);
    let cases = [
        ((1, 26, 9), ("fast", 2, 1)),
        ((12, 1, 9), ("slow", 2, 1)),
        ((12, 0, 9), ("slow", 2, 0)),
        ((12, 26, 0), ("signal", 1, 0)),
        // Checked before the swap, so the name is the one the caller used.
        ((26, 1, 9), ("slow", 2, 1)),
    ];

    for ((fast, slow, signal), (name, minimum, value)) in cases {
        assert_eq!(
            macd(&input, fast, slow, signal),
            Err(PytaError::InvalidParameter {
                name,
                minimum,
                value,
            })
        );
    }
}

#[test]
fn a_signal_period_of_one_equals_the_macd_line() {
    let output = macd(&wave(40), 12, 26, 1).unwrap();
    let [line, signal, hist] = outputs(&output);

    assert_same(line, signal);
    assert!(hist[25..].iter().all(|value| *value == 0.0));
}
