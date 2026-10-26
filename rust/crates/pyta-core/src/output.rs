/// Output from an indicator calculation.
///
/// Positions where the indicator has no valid result, such as the
/// warm-up period, are `f64::NAN`. Because `NaN != NaN`, compare
/// outputs element-wise with `is_nan()` rather than with `==`.
#[derive(Debug, Clone, PartialEq)]
pub struct IndicatorOutput {
    values: Vec<f64>,
}

impl IndicatorOutput {
    pub fn new(values: Vec<f64>) -> Self {
        Self { values }
    }

    pub fn values(&self) -> &[f64] {
        &self.values
    }

    /// Consumes the output, returning its values without copying.
    pub fn into_values(self) -> Vec<f64> {
        self.values
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }
}
