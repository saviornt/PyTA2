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
