use pyta_core::{Ohlcv, PytaError, Series};

#[test]
fn series_accepts_valid_values() {
    let series = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(series.len(), 3);
    assert_eq!(series.values(), &[1.0, 2.0, 3.0]);
}

#[test]
fn series_rejects_empty_input() {
    let result = Series::new(vec![]);

    assert_eq!(result, Err(PytaError::EmptyInput));
}

#[test]
fn series_rejects_nan() {
    let result = Series::new(vec![1.0, f64::NAN, 3.0]);

    assert_eq!(result, Err(PytaError::NonFiniteValue { index: 1 }));
}

#[test]
fn series_rejects_infinity() {
    let result = Series::new(vec![1.0, f64::INFINITY]);

    assert_eq!(result, Err(PytaError::NonFiniteValue { index: 1 }));
}

#[test]
fn ohlcv_rejects_mismatched_lengths() {
    let short = Series::new(vec![1.0]).unwrap();
    let long = Series::new(vec![1.0, 2.0]).unwrap();

    let result = Ohlcv::new(short.clone(), long, short.clone(), short.clone(), short);

    assert_eq!(result, Err(PytaError::LengthMismatch));
}
