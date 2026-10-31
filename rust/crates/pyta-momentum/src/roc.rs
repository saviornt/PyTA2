use pyta_core::kernels::rate_of_change;
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Rate of Change (ROC), as TA-Lib 0.8.3's `TA_ROC`.
///
/// Each value from index `period` on is `(value / earlier - 1) * 100`, with
/// `earlier` the value `period` rows before: the percentage change over
/// `period` rows (`pyta_core::kernels::rate_of_change`, shared with Volume
/// ROC). The first
/// `period` positions are `NaN` (warm-up). At least `period + 1` values are
/// required.
///
/// Edge case: when the earlier value is zero relative to the current one
/// (`|earlier| <= 1e-14 * |value|`, an exact 0 included) the result is 0,
/// so every value is finite. TA-Lib tests only an exact 0, which gives a
/// huge value or an infinity on a tiny non-zero base.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than `period + 1`
/// values.
pub fn roc(input: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let values = input.values();
    let length = values.len();
    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_add(1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    Ok(IndicatorOutput::new(rate_of_change(values, period)))
}
