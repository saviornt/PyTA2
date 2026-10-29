use pyta_common::{
    CCI_NS_PER_ELEMENT, CCI_NS_PER_WINDOW_VALUE, EMA_NS_PER_ELEMENT, MACD_NS_PER_ELEMENT,
    RSI_NS_PER_ELEMENT, SMA_NS_PER_ELEMENT,
};
use pyta_core::{IndicatorOutput, PytaResult};
use pyta_momentum::{cci, rsi};
use pyta_trend::{ema, macd, sma};

use crate::requests::{IndicatorRequest, Params};

/// Routes an indicator request to its implementation.
///
/// This function is shared by single-request and batch execution. Each arm
/// destructures its own `Params` variant and takes the columns its kernel
/// needs, in slot order; input with the wrong number of columns is a
/// `ColumnCount` error.
pub(crate) fn dispatch(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    let input = &request.input;

    match request.params {
        Params::Cci { period } => {
            let [high, low, close] = input.columns()?;
            cci(high, low, close, period)
        }
        Params::Ema { period } => ema(input.series()?, period),
        Params::Macd { fast, slow, signal } => macd(input.series()?, fast, slow, signal),
        Params::Rsi { period } => rsi(input.series()?, period),
        Params::Sma { period } => sma(input.series()?, period),
    }
}

/// Estimated single-threaded run time of a request, in nanoseconds.
///
/// Used only by the planner to decide between sequential and concurrent
/// execution, so relative accuracy matters more than absolute accuracy.
/// The figures live in `pyta-common` (`costs.rs`), measured by
/// `benches/workloads.rs` on a 16-core development machine.
///
/// This match is exhaustive on purpose: adding a `Params` variant fails
/// to compile until it has a cost. When adding an indicator, benchmark
/// it and include any dependence on its parameters (for example O(n * period)
/// algorithms, such as CCI) in its estimate. Cost scales with rows, not
/// rows times columns or outputs: a multi-column or multi-output constant is
/// measured per row.
pub(crate) fn estimated_cost_ns(request: &IndicatorRequest) -> f64 {
    let ns_per_element = match request.params {
        Params::Cci { period } => CCI_NS_PER_ELEMENT + CCI_NS_PER_WINDOW_VALUE * period as f64,
        Params::Ema { .. } => EMA_NS_PER_ELEMENT,
        Params::Macd { .. } => MACD_NS_PER_ELEMENT,
        Params::Rsi { .. } => RSI_NS_PER_ELEMENT,
        Params::Sma { .. } => SMA_NS_PER_ELEMENT,
    };

    request.input.len() as f64 * ns_per_element
}

#[cfg(test)]
mod tests {
    use pyta_core::Series;

    use super::estimated_cost_ns;
    use crate::requests::{IndicatorRequest, Params};

    fn cost(params: Params) -> f64 {
        estimated_cost_ns(&IndicatorRequest::new(
            Series::new(vec![1.0; 1_000]).unwrap(),
            params,
        ))
    }

    #[test]
    fn ema_and_macd_costs_do_not_depend_on_their_periods() {
        assert_eq!(
            cost(Params::Ema { period: 5 }),
            cost(Params::Ema { period: 200 })
        );
        assert_eq!(
            cost(Params::Macd {
                fast: 12,
                slow: 26,
                signal: 9
            }),
            cost(Params::Macd {
                fast: 5,
                slow: 200,
                signal: 50
            })
        );
    }

    #[test]
    fn cci_cost_grows_with_its_period() {
        assert!(cost(Params::Cci { period: 50 }) > cost(Params::Cci { period: 5 }));
    }
}
