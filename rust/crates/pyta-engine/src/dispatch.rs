use pyta_core::{IndicatorOutput, PytaResult};
use pyta_momentum::rsi;
use pyta_trend::sma;

use crate::requests::{IndicatorKind, IndicatorRequest};

/// Routes an indicator request to its implementation.
///
/// This function is shared by single-request and batch execution.
pub(crate) fn dispatch(
    request: &IndicatorRequest,
) -> PytaResult<IndicatorOutput> {
    match request.kind {
        IndicatorKind::Rsi => rsi(&request.input, request.period),
        IndicatorKind::Sma => sma(&request.input, request.period),
    }
}
