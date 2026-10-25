use pyta_core::{PytaError, Series};
use pyta_trend::sma;

#[test]
fn sma_calculates_rolling_averages() {
    let input = Series::new(vec![10.0, 20.0, 30.0, 40.0, 50.0]).unwrap();

    let result = sma(&input, 3).unwrap();

    assert_eq!(
        result.values(),
        &[None, None, Some(20.0), Some(30.0), Some(40.0)]
    );
}

#[test]
fn sma_period_one_returns_original_values() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    let result = sma(&input, 1).unwrap();

    assert_eq!(
        result.values(),
        &[Some(10.0), Some(20.0), Some(30.0)]
    );
}

#[test]
fn sma_rejects_zero_period() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(sma(&input, 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn sma_rejects_period_greater_than_input_length() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    assert_eq!(
        sma(&input, 4),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn sma_accepts_period_equal_to_input_length() {
    let input = Series::new(vec![10.0, 20.0, 30.0]).unwrap();

    let result = sma(&input, 3).unwrap();

    assert_eq!(result.values(), &[None, None, Some(20.0)]);
}

#[test]
fn sma_preserves_input_length() {
    let input = Series::new(vec![2.0, 4.0, 6.0, 8.0]).unwrap();

    let result = sma(&input, 2).unwrap();

    assert_eq!(result.len(), input.len());
}
