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
