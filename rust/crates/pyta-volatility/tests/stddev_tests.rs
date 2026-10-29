//! STDDEV kernel: formula, warm-up, parameters, edge cases and precision.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volatility::stddev;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn stddev_of(values: &[f64], period: usize, k: f64) -> Vec<f64> {
    stddev(&series(values), period, k).unwrap().into_values()
}

/// Population standard deviation of each window, two-pass, with the mean
/// taken as `sum / period`: the textbook form PyTA's kernel must match.
fn two_pass(values: &[f64], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; values.len()];
    for (index, window) in values.windows(period).enumerate() {
        let mean = window.iter().sum::<f64>() / period as f64;
        let squares: f64 = window.iter().map(|v| (v - mean) * (v - mean)).sum();
        output[index + period - 1] = (squares / period as f64).sqrt();
    }
    output
}

// Windows of 4: [2, 4, 4, 4] mean 3.5, variance 0.75;
// [4, 4, 4, 5] mean 4.25, variance 0.1875; [4, 4, 5, 5] mean 4.5,
// variance 0.25; [4, 5, 5, 7] mean 5.25, variance 1.1875;
// [5, 5, 7, 9] mean 6.5, variance 2.75.
const VALUES: [f64; 8] = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];

#[test]
fn stddev_preserves_input_length_and_warmup_alignment() {
    let result = stddev_of(&VALUES, 4, 1.0);

    assert_eq!(result.len(), 8);
    assert!(result[..3].iter().all(|value| value.is_nan()));
    assert!(result[3..].iter().all(|value| value.is_finite()));
}

#[test]
fn stddev_matches_a_hand_calculation() {
    let result = stddev_of(&VALUES, 4, 1.0);
    let expected = [0.75_f64, 0.1875, 0.25, 1.1875, 2.75].map(f64::sqrt);

    for (got, want) in result[3..].iter().zip(expected) {
        assert!((got - want).abs() <= 1e-15, "{got} vs {want}");
    }
}

#[test]
fn stddev_is_the_population_deviation() {
    // The whole series: mean 5, squared deviations sum to 32, so the
    // population deviation is sqrt(32 / 8) = 2 (the sample one would be
    // sqrt(32 / 7)).
    let result = stddev_of(&VALUES, 8, 1.0);

    assert_eq!(result[7], 2.0);
}

#[test]
fn stddev_multiplies_by_k() {
    let one = stddev_of(&VALUES, 4, 1.0);
    let two_and_a_half = stddev_of(&VALUES, 4, 2.5);

    for (a, b) in one[3..].iter().zip(&two_and_a_half[3..]) {
        assert_eq!(*b, a * 2.5);
    }
}

#[test]
fn stddev_rejects_a_period_below_two() {
    for period in [0, 1] {
        assert_eq!(
            stddev(&series(&VALUES), period, 1.0),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn stddev_rejects_a_k_that_is_not_a_finite_positive_number() {
    for k in [0.0, -0.0, -1.0, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(
            stddev(&series(&VALUES), 4, k),
            Err(PytaError::InvalidFloatParameter {
                name: "k",
                value: k
            })
        );
    }

    assert!(matches!(
        stddev(&series(&VALUES), 4, f64::NAN),
        Err(PytaError::InvalidFloatParameter { name: "k", value }) if value.is_nan()
    ));
}

#[test]
fn stddev_checks_the_period_before_k() {
    assert!(matches!(
        stddev(&series(&VALUES), 1, -1.0),
        Err(PytaError::InvalidParameter { .. })
    ));
}

#[test]
fn stddev_rejects_a_period_longer_than_the_series() {
    assert_eq!(
        stddev(&series(&[1.0, 2.0, 3.0]), 4, 1.0),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn stddev_accepts_minimum_data() {
    let result = stddev_of(&[1.0, 3.0], 2, 1.0);

    assert!(result[0].is_nan());
    assert_eq!(result[1], 1.0);
}

#[test]
fn stddev_is_exactly_zero_for_a_flat_series() {
    // 0.1 and 101.37 are not exact in binary, so the window's mean can miss
    // the repeated value by one unit in the last place; the result is still
    // exactly 0, as TA-Lib's is.
    for level in [0.1, 101.37, 1.0e-200, -7.3e12, 0.0] {
        let result = stddev_of(&[level; 30], 7, 2.0);

        assert!(
            result[6..].iter().all(|value| *value == 0.0),
            "level {level}: {:?}",
            &result[6..]
        );
    }
}

#[test]
fn stddev_does_not_round_a_real_spread_to_zero() {
    // A one-cent spread on a price of 100,000 (relative 1e-7) and a tick of
    // 1e-8 on 100 (relative 1e-10) are far above the zero tolerance.
    for (level, step) in [(1.0e5, 0.01), (100.0, 1.0e-8)] {
        let values: Vec<f64> = (0..10).map(|i| level + step * f64::from(i % 2)).collect();
        let result = stddev_of(&values, 4, 1.0);

        for value in &result[3..] {
            assert!((value / (step / 2.0) - 1.0).abs() < 1e-5, "{value}");
        }
    }
}

#[test]
fn stddev_keeps_its_precision_on_a_large_offset_with_a_small_spread() {
    // 1e5 + 1e-3 * noise: a running sum of squares (TA-Lib's form before
    // 0.8.3) cancels catastrophically here; the centred kernel matches a
    // two-pass reference.
    let mut state = 0x9E37_79B9_7F4A_7C15_u64;
    let values: Vec<f64> = (0..2_000)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            1.0e5 + 1.0e-3 * ((state >> 11) as f64 / (1_u64 << 53) as f64 - 0.5)
        })
        .collect();

    for period in [5, 20, 100] {
        let actual = stddev_of(&values, period, 1.0);
        let expected = two_pass(&values, period);

        for (index, (a, e)) in actual.iter().zip(&expected).enumerate().skip(period - 1) {
            assert!(
                (a - e).abs() <= 1e-9 * e,
                "period {period}, index {index}: {a} vs {e}"
            );
        }
    }
}

#[test]
fn stddev_is_finite_at_the_magnitude_limit() {
    let values = [MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, -MAX_ABS_INPUT];
    let result = stddev_of(&values, 2, 1.0);

    for value in &result[1..] {
        assert!((value / MAX_ABS_INPUT - 1.0).abs() <= 1e-15, "{value}");
    }
}
