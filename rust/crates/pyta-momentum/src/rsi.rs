use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Relative Strength Index (RSI) using Wilder's smoothing.
///
/// `period` is the number of price changes used to initialize the
/// average gain and average loss, so at least `period + 1` values
/// are required.
///
/// The output has the same length as the input. The first `period`
/// positions are `NaN` (warm-up).
///
/// Edge cases:
/// - Average gain and average loss both zero: RSI is 0.
/// - Average loss zero, average gain positive: RSI is 100.
/// - Average gain zero, average loss positive: RSI is 0.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `InsufficientData` when the input has fewer than
/// `period + 1` values.
pub fn rsi(close: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let prices = close.values();

    if period >= prices.len() {
        return Err(PytaError::InsufficientData {
            required: period + 1,
            length: prices.len(),
        });
    }

    let mut output = vec![f64::NAN; prices.len()];

    let mut gain_sum = 0.0;
    let mut loss_sum = 0.0;

    // Initial average gain and loss over the first `period` changes.
    for index in 1..=period {
        let change = prices[index] - prices[index - 1];

        if change > 0.0 {
            gain_sum += change;
        } else {
            loss_sum -= change; // losses are stored as positive values
        }
    }

    let period_f = period as f64;
    let prior_weight = (period - 1) as f64;

    let mut average_gain = gain_sum / period_f;
    let mut average_loss = loss_sum / period_f;

    output[period] = relative_strength_index(average_gain, average_loss);

    // Wilder's smoothing for the rest of the series.
    for index in (period + 1)..prices.len() {
        let change = prices[index] - prices[index - 1];

        let gain = change.max(0.0);
        let loss = (-change).max(0.0);

        average_gain = (average_gain * prior_weight + gain) / period_f;
        average_loss = (average_loss * prior_weight + loss) / period_f;

        output[index] = relative_strength_index(average_gain, average_loss);
    }

    Ok(IndicatorOutput::new(output))
}

fn relative_strength_index(average_gain: f64, average_loss: f64) -> f64 {
    if average_gain == 0.0 {
        // Covers both "no gains" and "no movement at all".
        return 0.0;
    }

    if average_loss == 0.0 {
        return 100.0;
    }

    let relative_strength = average_gain / average_loss;
    100.0 - (100.0 / (1.0 + relative_strength))
}
