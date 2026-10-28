use pyta_common::{
    CCI_NS_PER_ELEMENT, CCI_NS_PER_WINDOW_VALUE, RSI_NS_PER_ELEMENT, SMA_NS_PER_ELEMENT,
};
use pyta_core::{IndicatorOutput, PytaResult};
use pyta_momentum::{cci, rsi};
use pyta_trend::sma;

use crate::requests::{IndicatorKind, IndicatorRequest};

/// Routes an indicator request to its implementation.
///
/// This function is shared by single-request and batch execution. Each arm
/// takes the columns its kernel needs, in slot order; input with the wrong
/// number of columns is a `ColumnCount` error.
pub(crate) fn dispatch(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    let input = &request.input;
    let period = request.period;

    match request.kind {
        IndicatorKind::Cci => {
            let [high, low, close] = input.columns()?;
            cci(high, low, close, period)
        }
        IndicatorKind::Rsi => rsi(input.series()?, period),
        IndicatorKind::Sma => sma(input.series()?, period),
    }
}

/// Estimated single-threaded run time of a request, in nanoseconds.
///
/// Used only by the planner to decide between sequential and concurrent
/// execution, so relative accuracy matters more than absolute accuracy.
/// The figures live in `pyta-common` (`costs.rs`), measured by
/// `benches/workloads.rs` on a 16-core development machine.
///
/// This match is exhaustive on purpose: adding an `IndicatorKind` fails
/// to compile until it has a cost. When adding an indicator, benchmark
/// it and include any dependence on `period` (for example O(n * period)
/// algorithms, such as CCI) in its estimate. Cost scales with rows, not
/// rows times columns: a multi-column constant is measured per row.
pub(crate) fn estimated_cost_ns(request: &IndicatorRequest) -> f64 {
    let ns_per_element = match request.kind {
        IndicatorKind::Cci => CCI_NS_PER_ELEMENT + CCI_NS_PER_WINDOW_VALUE * request.period as f64,
        IndicatorKind::Sma => SMA_NS_PER_ELEMENT,
        IndicatorKind::Rsi => RSI_NS_PER_ELEMENT,
    };

    request.input.len() as f64 * ns_per_element
}
