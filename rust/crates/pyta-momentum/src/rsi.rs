/// Calculates the Relative Strength Index (RSI) for a given series of data using Wilder's smoothing method.
///
/// The period represents the number of price changes used to initialize
/// the average gain and average loss.
///
/// The output has the same length as the input series, with the first 'period'
/// values being None, as they cannot be calculated without sufficient data.
///
/// When both average gain and average loss are zero, the RSI is defined to be 0 to avoid division by zero.
/// When average loss is zero but average gain is positive, the RSI is defined to be 100, indicating a strong upward trend.
/// When the average gain is zero but the average loss is positive, the RSI is defined to be 0, indicating a strong downward trend.
use pyta_core::{IndicatorOutput, PytaResult, Series};

pub fn rsi(close: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(pyta_core::PytaError::InvalidPeriod);
    }
    
    let prices = close.values();

    if period >= prices.len() {
        return Err(pyta_core::PytaError::PeriodExceedsLength {
            period,
            length: prices.len(),
        });
    }

    let mut output = vec![None; prices.len()];

    let mut gain_sum = 0.0;
    let mut loss_sum = 0.0;

    // Calculate the initial average gain and loss over `period` changes.
    for index in 1..=period {
        let change = prices[index] - prices[index - 1];

        if change > 0.0 {
            gain_sum += change;
        } else {
            loss_sum -= change; // loss is positive
        }
    }

    let mut average_gain = gain_sum / period as f64;
    let mut average_loss = loss_sum / period as f64;

    output[period] = Some(calculate_rsi(average_gain, average_loss));

    // Apply Wilder's smoothing method for the rest of the series.
    for index in (period + 1)..prices.len() {
        let change = prices[index] - prices[index - 1];

        let gain = change.max(0.0);
        let loss = (-change).max(0.0);

        average_gain = (average_gain * (period -1) as f64 + gain) / period as f64;
        average_loss = (average_loss * (period -1) as f64 + loss) / period as f64;

        output[index] = Some(calculate_rsi(average_gain, average_loss));
    }
    Ok(IndicatorOutput::new(output))
}

fn calculate_rsi(average_gain: f64, average_loss: f64) -> f64 {
    if average_gain == 0.0 && average_loss == 0.0 {
        return 0.0; // Both gains and losses are zero
    }

    if average_loss == 0.0 {
        return 100.0;
    }

    if average_gain == 0.0 {
        return 0.0;
    }

    let relative_strength = average_gain / average_loss;
    100.0 - (100.0 / (1.0 + relative_strength))
}