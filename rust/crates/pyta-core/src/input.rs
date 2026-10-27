// Numeric series and OHLCV input structures

use crate::error::{PytaError, PytaResult};

/// A validated, non-empty series of finite numerical values.
#[derive(Debug, Clone, PartialEq)]
pub struct Series {
    values: Vec<f64>,
}

/// Elements checked per validation block. A block is small enough to
/// stay in L1 cache between the check and the copy.
const BLOCK: usize = 64;

/// Returns `true` if every value in `block` is finite.
///
/// Branch-free so the compiler can vectorize it. `|x| <= f64::MAX` is
/// false for infinities and NaN, and it compiles to packed float
/// compares even on baseline x86-64 (SSE2), which has no 64-bit integer
/// compare. That makes it faster than checking the exponent bits.
#[inline]
fn block_is_finite(block: &[f64]) -> bool {
    block
        .iter()
        .fold(true, |finite, value| finite & (value.abs() <= f64::MAX))
}

/// Builds the error for the first non-finite value in a block that failed
/// [`block_is_finite`]; `offset` is the block's index in the series.
#[cold]
fn non_finite_error(block: &[f64], offset: usize) -> PytaError {
    let index = block
        .iter()
        .position(|value| !value.is_finite())
        .unwrap_or_default();
    PytaError::NonFiniteValue {
        index: offset + index,
    }
}

impl Series {
    /// Creates a series after validating its values.
    pub fn new(values: Vec<f64>) -> PytaResult<Self> {
        if values.is_empty() {
            return Err(PytaError::EmptyInput);
        }

        for (number, block) in values.chunks(BLOCK).enumerate() {
            if !block_is_finite(block) {
                return Err(non_finite_error(block, number * BLOCK));
            }
        }

        Ok(Self { values })
    }

    /// Copies and validates `values` in a single pass.
    ///
    /// Equivalent to `Series::new(values.to_vec())`, but each block is
    /// validated while it is still in cache, so validation costs almost
    /// nothing on top of the copy. Use this when the caller does not own
    /// the data, such as at the Python boundary.
    pub fn from_slice(values: &[f64]) -> PytaResult<Self> {
        if values.is_empty() {
            return Err(PytaError::EmptyInput);
        }

        let mut copy = Vec::with_capacity(values.len());
        for (number, block) in values.chunks(BLOCK).enumerate() {
            if !block_is_finite(block) {
                return Err(non_finite_error(block, number * BLOCK));
            }
            copy.extend_from_slice(block);
        }

        Ok(Self { values: copy })
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
