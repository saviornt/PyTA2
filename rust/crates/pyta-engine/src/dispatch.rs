use pyta_common::{
    ADX_NS_PER_ELEMENT, AROON_NS_PER_ELEMENT, ATR_NS_PER_ELEMENT, BBANDS_NS_PER_ELEMENT,
    BBANDS_NS_PER_WINDOW_VALUE, CCI_NS_PER_ELEMENT, CCI_NS_PER_WINDOW_VALUE, DEMA_NS_PER_ELEMENT,
    DONCHIAN_NS_PER_ELEMENT, EMA_NS_PER_ELEMENT, ICHIMOKU_NS_PER_ELEMENT, KAMA_NS_PER_ELEMENT,
    KELTNER_NS_PER_ELEMENT, MACD_NS_PER_ELEMENT, RSI_NS_PER_ELEMENT, SAR_NS_PER_ELEMENT,
    SMA_NS_PER_ELEMENT, STDDEV_NS_PER_ELEMENT, STDDEV_NS_PER_WINDOW_VALUE, TEMA_NS_PER_ELEMENT,
    WMA_NS_PER_ELEMENT,
};
use pyta_core::{IndicatorOutput, PytaResult};
use pyta_momentum::{cci, rsi};
use pyta_trend::{adx, aroon, dema, ema, ichimoku, kama, macd, sar, sma, tema, wma};
use pyta_volatility::{atr, bbands, donchian, keltner, stddev};

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
        Params::Adx { period } => {
            let [high, low, close] = input.columns()?;
            adx(high, low, close, period)
        }
        Params::Aroon { period } => {
            let [high, low] = input.columns()?;
            aroon(high, low, period)
        }
        Params::Atr { period } => {
            let [high, low, close] = input.columns()?;
            atr(high, low, close, period)
        }
        Params::Bbands { period, k } => bbands(input.series()?, period, k),
        Params::Cci { period } => {
            let [high, low, close] = input.columns()?;
            cci(high, low, close, period)
        }
        Params::Dema { period } => dema(input.series()?, period),
        Params::Donchian { period } => {
            let [high, low] = input.columns()?;
            donchian(high, low, period)
        }
        Params::Ema { period } => ema(input.series()?, period),
        Params::Ichimoku {
            tenkan,
            kijun,
            senkou,
        } => {
            let [high, low, close] = input.columns()?;
            ichimoku(high, low, close, tenkan, kijun, senkou)
        }
        Params::Kama { period } => kama(input.series()?, period),
        Params::Keltner {
            period,
            atr_period,
            k,
        } => {
            let [high, low, close] = input.columns()?;
            keltner(high, low, close, period, atr_period, k)
        }
        Params::Macd { fast, slow, signal } => macd(input.series()?, fast, slow, signal),
        Params::Rsi { period } => rsi(input.series()?, period),
        Params::Sar {
            acceleration,
            maximum,
        } => {
            let [high, low] = input.columns()?;
            sar(high, low, acceleration, maximum)
        }
        Params::Sma { period } => sma(input.series()?, period),
        Params::Stddev { period, k } => stddev(input.series()?, period, k),
        Params::Tema { period } => tema(input.series()?, period),
        Params::Wma { period } => wma(input.series()?, period),
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
/// algorithms, such as CCI, STDDEV and BBANDS) in its estimate. Cost scales with rows, not
/// rows times columns or outputs: a multi-column or multi-output constant is
/// measured per row.
pub(crate) fn estimated_cost_ns(request: &IndicatorRequest) -> f64 {
    let ns_per_element = match request.params {
        Params::Adx { .. } => ADX_NS_PER_ELEMENT,
        Params::Aroon { .. } => AROON_NS_PER_ELEMENT,
        Params::Atr { .. } => ATR_NS_PER_ELEMENT,
        Params::Bbands { period, .. } => {
            BBANDS_NS_PER_ELEMENT + BBANDS_NS_PER_WINDOW_VALUE * period as f64
        }
        Params::Cci { period } => CCI_NS_PER_ELEMENT + CCI_NS_PER_WINDOW_VALUE * period as f64,
        Params::Dema { .. } => DEMA_NS_PER_ELEMENT,
        Params::Donchian { .. } => DONCHIAN_NS_PER_ELEMENT,
        Params::Ema { .. } => EMA_NS_PER_ELEMENT,
        Params::Ichimoku { .. } => ICHIMOKU_NS_PER_ELEMENT,
        Params::Kama { .. } => KAMA_NS_PER_ELEMENT,
        Params::Keltner { .. } => KELTNER_NS_PER_ELEMENT,
        Params::Macd { .. } => MACD_NS_PER_ELEMENT,
        Params::Rsi { .. } => RSI_NS_PER_ELEMENT,
        Params::Sar { .. } => SAR_NS_PER_ELEMENT,
        Params::Sma { .. } => SMA_NS_PER_ELEMENT,
        Params::Stddev { period, .. } => {
            STDDEV_NS_PER_ELEMENT + STDDEV_NS_PER_WINDOW_VALUE * period as f64
        }
        Params::Tema { .. } => TEMA_NS_PER_ELEMENT,
        Params::Wma { .. } => WMA_NS_PER_ELEMENT,
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
    fn ema_family_wma_and_macd_costs_do_not_depend_on_their_periods() {
        assert_eq!(
            cost(Params::Ema { period: 5 }),
            cost(Params::Ema { period: 200 })
        );
        assert_eq!(
            cost(Params::Dema { period: 5 }),
            cost(Params::Dema { period: 200 })
        );
        assert_eq!(
            cost(Params::Kama { period: 5 }),
            cost(Params::Kama { period: 200 })
        );
        assert_eq!(
            cost(Params::Adx { period: 5 }),
            cost(Params::Adx { period: 200 })
        );
        assert_eq!(
            cost(Params::Tema { period: 5 }),
            cost(Params::Tema { period: 200 })
        );
        assert_eq!(
            cost(Params::Wma { period: 5 }),
            cost(Params::Wma { period: 200 })
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

    #[test]
    fn stddev_cost_grows_with_its_period_but_not_with_k() {
        assert!(
            cost(Params::Stddev { period: 50, k: 1.0 })
                > cost(Params::Stddev { period: 5, k: 1.0 })
        );
        assert_eq!(
            cost(Params::Stddev { period: 5, k: 1.0 }),
            cost(Params::Stddev { period: 5, k: 3.0 })
        );
    }

    #[test]
    fn bbands_cost_grows_with_its_period_but_not_with_k() {
        assert!(
            cost(Params::Bbands { period: 50, k: 2.0 })
                > cost(Params::Bbands { period: 5, k: 2.0 })
        );
        assert_eq!(
            cost(Params::Bbands { period: 20, k: 1.0 }),
            cost(Params::Bbands { period: 20, k: 3.0 })
        );
    }

    #[test]
    fn sar_cost_does_not_depend_on_its_parameters() {
        assert_eq!(
            cost(Params::Sar {
                acceleration: 0.02,
                maximum: 0.2
            }),
            cost(Params::Sar {
                acceleration: 0.01,
                maximum: 0.5
            })
        );
    }

    #[test]
    fn aroon_cost_does_not_depend_on_its_period() {
        // The rolling extremes are O(n) whatever the window.
        assert_eq!(
            cost(Params::Aroon { period: 5 }),
            cost(Params::Aroon { period: 200 })
        );
    }

    #[test]
    fn ichimoku_cost_does_not_depend_on_its_windows() {
        // Three rolling-extreme midpoints, each O(n) whatever the window.
        assert_eq!(
            cost(Params::Ichimoku {
                tenkan: 2,
                kijun: 3,
                senkou: 5
            }),
            cost(Params::Ichimoku {
                tenkan: 9,
                kijun: 26,
                senkou: 52
            })
        );
    }

    #[test]
    fn donchian_cost_does_not_depend_on_its_period() {
        // The rolling extremes are O(n) whatever the window.
        assert_eq!(
            cost(Params::Donchian { period: 5 }),
            cost(Params::Donchian { period: 200 })
        );
    }

    #[test]
    fn keltner_cost_does_not_depend_on_its_parameters() {
        // One EMA pass and one ATR pass, O(n) whatever the periods.
        assert_eq!(
            cost(Params::Keltner {
                period: 5,
                atr_period: 5,
                k: 1.0
            }),
            cost(Params::Keltner {
                period: 200,
                atr_period: 100,
                k: 3.0
            })
        );
    }
}
