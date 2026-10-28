//! RSI kernel: formula, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::rsi;

#[test]
fn rsi_preserves_input_length_and_warmup_alignment() {
    let close = Series::new(vec![10.0, 11.0, 12.0, 13.0, 12.0]).unwrap();

    let result = rsi(&close, 3).unwrap();

    assert_eq!(result.len(), 5);
    assert!(result.values()[..3].iter().all(|value| value.is_nan()));
    assert_eq!(result.values()[3], 100.0);

    let final_value = result.values()[4];
    assert!(final_value.is_finite());
    assert!(final_value < 100.0);
}

#[test]
fn rsi_rejects_zero_period() {
    let close = Series::new(vec![10.0, 11.0, 12.0]).unwrap();

    assert_eq!(rsi(&close, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn rsi_rejects_insufficient_data() {
    let close = Series::new(vec![10.0, 11.0, 12.0]).unwrap();

    assert_eq!(
        rsi(&close, 3),
        Err(PytaError::InsufficientData {
            required: 4,
            length: 3,
        })
    );
}

#[test]
fn rsi_accepts_minimum_data() {
    let close = Series::new(vec![10.0, 11.0, 12.0, 13.0]).unwrap();

    let result = rsi(&close, 3).unwrap();

    assert_eq!(result.values()[3], 100.0);
}

#[test]
fn rsi_returns_zero_for_constant_prices() {
    let close = Series::new(vec![10.0, 10.0, 10.0, 10.0]).unwrap();

    let result = rsi(&close, 2).unwrap();

    assert_eq!(result.values()[2], 0.0);
    assert_eq!(result.values()[3], 0.0);
}

#[test]
fn rsi_returns_one_hundred_when_there_are_no_losses() {
    let close = Series::new(vec![1.0, 2.0, 3.0, 4.0, 5.0]).unwrap();

    let result = rsi(&close, 2).unwrap();

    assert_eq!(result.values()[2], 100.0);
    assert_eq!(result.values()[4], 100.0);
}

#[test]
fn rsi_returns_zero_when_there_are_no_gains() {
    let close = Series::new(vec![5.0, 4.0, 3.0, 2.0, 1.0]).unwrap();

    let result = rsi(&close, 2).unwrap();

    assert_eq!(result.values()[2], 0.0);
    assert_eq!(result.values()[4], 0.0);
}

/// Textbook Wilder RSI, used as a check on the optimized kernel.
fn reference_rsi(prices: &[f64], period: usize) -> Vec<f64> {
    let n = period as f64;
    let mut output = vec![f64::NAN; prices.len()];
    let (mut gain_sum, mut loss_sum) = (0.0, 0.0);

    for i in 1..=period {
        let change = prices[i] - prices[i - 1];
        gain_sum += change.max(0.0);
        loss_sum += (-change).max(0.0);
    }

    let value = |gain: f64, loss: f64| {
        if gain == 0.0 {
            0.0
        } else if loss == 0.0 {
            100.0
        } else {
            100.0 - 100.0 / (1.0 + gain / loss)
        }
    };

    let (mut avg_gain, mut avg_loss) = (gain_sum / n, loss_sum / n);
    output[period] = value(avg_gain, avg_loss);

    for i in (period + 1)..prices.len() {
        let change = prices[i] - prices[i - 1];
        avg_gain = (avg_gain * (n - 1.0) + change.max(0.0)) / n;
        avg_loss = (avg_loss * (n - 1.0) + (-change).max(0.0)) / n;
        output[i] = value(avg_gain, avg_loss);
    }

    output
}

#[test]
fn rsi_matches_textbook_formula_on_long_series() {
    let data: Vec<f64> = (0..50_000)
        .map(|i| 100.0 + (i as f64 * 0.013).sin() * 20.0 + (i as f64 * 0.31).cos() * 3.0)
        .collect();
    let close = Series::new(data.clone()).unwrap();

    let actual = rsi(&close, 14).unwrap();
    let expected = reference_rsi(&data, 14);

    for (index, (a, e)) in actual.values().iter().zip(&expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || (a - e).abs() <= 1e-9,
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

#[test]
fn rsi_handles_price_changes_at_the_magnitude_limit() {
    let limit = MAX_ABS_INPUT;
    let close = Series::new(vec![limit, -limit, limit]).unwrap();

    let result = rsi(&close, 1).unwrap();

    assert!(result.values()[0].is_nan());
    assert_eq!(&result.values()[1..], &[0.0, 100.0]);
}

#[test]
fn rsi_is_scale_invariant_at_the_magnitude_limit() {
    let unit: Vec<f64> = (0..5_000)
        .map(|i| (i as f64 * 0.7).sin() * 0.6 + (i as f64 * 0.05).cos() * 0.4)
        .collect();
    let scaled: Vec<f64> = unit.iter().map(|value| value * MAX_ABS_INPUT).collect();
    assert!(
        scaled
            .iter()
            .any(|value| value.abs() > 0.99 * MAX_ABS_INPUT)
    );

    let expected = rsi(&Series::new(unit).unwrap(), 14).unwrap();
    let actual = rsi(&Series::new(scaled).unwrap(), 14).unwrap();

    for (index, (a, e)) in actual.values().iter().zip(expected.values()).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan() && index < 14) || (a - e).abs() <= 1e-9,
            "mismatch at {index}: got {a}, expected {e}"
        );
    }
}

#[test]
fn inputs_that_would_overflow_the_price_change_are_rejected() {
    // Before the limit, this returned `NaN` after warm-up.
    assert_eq!(
        Series::new(vec![1e308, -1e308, 1e308]),
        Err(PytaError::ValueOutOfRange { index: 0 })
    );
    assert_eq!(
        Series::new(vec![1.0, -MAX_ABS_INPUT.next_up()]),
        Err(PytaError::ValueOutOfRange { index: 1 })
    );
}

#[test]
fn rsi_period_one_follows_each_change() {
    let close = Series::new(vec![10.0, 11.0, 10.5, 10.5, 12.0]).unwrap();

    let result = rsi(&close, 1).unwrap();

    assert!(result.values()[0].is_nan());
    assert_eq!(&result.values()[1..], [100.0, 0.0, 0.0, 100.0]);
}

#[test]
fn rsi_period_of_length_minus_one_gives_one_value() {
    let close = Series::new(vec![10.0, 11.0, 10.0, 12.0]).unwrap();

    let result = rsi(&close, 3).unwrap();

    // Gains 1 + 2, losses 1: RSI = 100 * 3 / (3 + 1).
    assert!(result.values()[..3].iter().all(|value| value.is_nan()));
    assert!((result.values()[3] - 75.0).abs() < 1e-12);
}

#[test]
fn rsi_of_tiny_values_matches_rsi_of_their_scaled_up_copy() {
    let base = [1.0, 3.0, 2.0, 5.0, 4.0, 4.5, 6.0];
    let tiny: Vec<f64> = base.iter().map(|value| value * 1e-300).collect();

    let tiny = rsi(&Series::new(tiny).unwrap(), 3).unwrap();
    let base = rsi(&Series::new(base.to_vec()).unwrap(), 3).unwrap();

    for (a, b) in tiny.values().iter().zip(base.values()).skip(3) {
        assert!((a - b).abs() < 1e-9, "{a} vs {b}");
    }
}
