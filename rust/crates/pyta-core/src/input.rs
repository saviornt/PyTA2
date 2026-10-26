// Numeric series and OHLCV input structures

use crate::error::{PytaError, PytaResult};

/// A validated, non-empty series of finite numerical values.
#[derive(Debug, Clone, PartialEq)]
pub struct Series {
    values: Vec<f64>,
}

impl Series {
    /// Creates a series after validating its values.
    pub fn new(values: Vec<f64>) -> PytaResult<Self> {
        if values.is_empty() {
            return Err(PytaError::EmptyInput);
        }

        if let Some(index) = values.iter().position(|value| !value.is_finite()) {
            return Err(PytaError::NonFiniteValue { index });
        }

        Ok(Self { values })
    }

    pub fn values(&self) -> &[f64] {
        &self.values
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }
}

/// OHLCV market data with aligned columns
#[derive(Debug, Clone, PartialEq)]
pub struct Ohlcv {
    pub open: Series,
    pub high: Series,
    pub low: Series,
    pub close: Series,
    pub volume: Series,
}

impl Ohlcv {
    pub fn new(
        open: Series,
        high: Series,
        low: Series,
        close: Series,
        volume: Series,
    ) -> PytaResult<Self> {
        let length = open.len();

        if [high.len(), low.len(), close.len(), volume.len()]
            .iter()
            .any(|&candidate| candidate != length)
        {
            return Err(PytaError::LengthMismatch);
        }

        Ok(Self {
            open,
            high,
            low,
            close,
            volume,
        })
    }

    pub fn len(&self) -> usize {
        self.close.len()
    }

    pub fn is_empty(&self) -> bool {
        self.close.is_empty()
    }
}
