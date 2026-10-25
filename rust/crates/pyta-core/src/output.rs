/// Output from an indicator calculation.
///
/// `None` represents a position where the indicator has no valid result,
/// such as during its warm-up period.

#[derive(Debug, Clone, PartialEq)]
pub struct IndicatorOutput {
    values: Vec<Option<f64>>,
}

impl IndicatorOutput {
    pub fn new(values: Vec<Option<f64>>) -> Self {
        Self { values }
    }

    pub fn values(&self) -> &[Option<f64>] {
        &self.values
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }
}
