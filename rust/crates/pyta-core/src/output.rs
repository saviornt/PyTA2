use crate::error::{PytaError, PytaResult};

/// Output from an indicator calculation: one or more series of equal
/// length, in the indicator's documented output order.
///
/// Most indicators have one output. A multi-output indicator, such as MACD
/// (`macd`, signal, histogram), has several; their names live in the Python
/// layer, so here they are only positions. The first output is the main one.
///
/// Positions where the indicator has no valid result, such as the
/// warm-up period, are `f64::NAN`, and each output has its own warm-up.
/// Because `NaN != NaN`, compare outputs element-wise with `is_nan()`
/// rather than with `==`.
#[derive(Debug, Clone, PartialEq)]
pub struct IndicatorOutput {
    /// Never empty; every series has the same length.
    outputs: Vec<Vec<f64>>,
}

impl IndicatorOutput {
    /// Wraps the calculated values of a single-output indicator (`NaN`
    /// where there is no result).
    pub fn new(values: Vec<f64>) -> Self {
        Self {
            outputs: vec![values],
        }
    }

    /// Wraps the calculated series of a multi-output indicator, in its
    /// documented output order.
    ///
    /// # Errors
    ///
    /// `LengthMismatch` when `outputs` is empty or the series have
    /// different lengths.
    pub fn with_outputs(outputs: Vec<Vec<f64>>) -> PytaResult<Self> {
        let Some(first) = outputs.first() else {
            return Err(PytaError::LengthMismatch);
        };
        let length = first.len();

        if outputs.iter().any(|output| output.len() != length) {
            return Err(PytaError::LengthMismatch);
        }

        Ok(Self { outputs })
    }

    /// The calculated values of the first (main) output.
    pub fn values(&self) -> &[f64] {
        &self.outputs[0]
    }

    /// Consumes the output, returning the first (main) output's values
    /// without copying; any other outputs are dropped.
    pub fn into_values(self) -> Vec<f64> {
        // Never empty, so the default is never used.
        self.outputs.into_iter().next().unwrap_or_default()
    }

    /// Every output series, in the indicator's documented order.
    pub fn outputs(&self) -> &[Vec<f64>] {
        &self.outputs
    }

    /// Consumes the output, returning every series without copying.
    pub fn into_outputs(self) -> Vec<Vec<f64>> {
        self.outputs
    }

    /// Number of output series (at least 1).
    pub fn output_count(&self) -> usize {
        self.outputs.len()
    }

    /// Number of values in each series (always the input length).
    pub fn len(&self) -> usize {
        self.outputs[0].len()
    }

    /// Whether there are no values.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}
