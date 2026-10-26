use pyta_core::{IndicatorOutput, PytaResult};
use pyta_momentum::rsi;
use pyta_trend::sma;

use crate::requests::{IndicatorKind, IndicatorRequest};

/// Routes an indicator request to its implementation.
///
/// This function is shared by single-request and batch execution.
pub(crate) fn dispatch(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    match request.kind {
        IndicatorKind::Rsi => rsi(&request.input, request.period),
        IndicatorKind::Sma => sma(&request.input, request.period),
    }
}

/// Estimated single-threaded run time of a request, in nanoseconds.
///
/// Used only by the planner to decide between sequential and concurrent
/// execution, so relative accuracy matters more than absolute accuracy.
/// The figures come from `benches/workloads.rs` on a 16-core development
/// machine.
///
/// This match is exhaustive on purpose: adding an `IndicatorKind` fails
/// to compile until it has a cost. When adding an indicator, benchmark
/// it and include any dependence on `period` (for example O(n * period)
/// algorithms) in its estimate.
pub(crate) fn estimated_cost_ns(request: &IndicatorRequest) -> f64 {
    let ns_per_element = match request.kind {
        IndicatorKind::Sma => 1.8,
        IndicatorKind::Rsi => 5.5,
    };

    request.input.len() as f64 * ns_per_element
}
