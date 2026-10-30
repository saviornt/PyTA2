use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates Joseph Granville's On-Balance Volume (OBV) from close and
/// volume, as TA-Lib 0.8.3's `TA_OBV`.
///
/// OBV starts at the first row's volume. On each later row the volume is
/// added when the close rose from the previous row, subtracted when it fell,
/// and the total is unchanged when the close is equal.
///
/// Returns one output with the input's length and no warm-up: every row has
/// a value, so one row is enough.
///
/// Volume is not checked for sign here (the Python layer rejects negative
/// volume). Every value is at most `MAX_ABS_INPUT` (`1e290`) in magnitude,
/// so the running total stays finite.
///
/// # Errors
///
/// Returns `LengthMismatch` when the columns differ in length.
pub fn obv(close: &Series, volume: &Series) -> PytaResult<IndicatorOutput> {
    let (close, volume) = (close.values(), volume.values());

    if close.len() != volume.len() {
        return Err(PytaError::LengthMismatch);
    }

    let mut output = Vec::with_capacity(close.len());
    // A `Series` is never empty, so row 0 exists.
    let mut total = volume[0];
    let mut previous = close[0];
    output.push(total);

    for (&current, &traded) in close[1..].iter().zip(&volume[1..]) {
        if current > previous {
            total += traded;
        } else if current < previous {
            total -= traded;
        }
        output.push(total);
        previous = current;
    }

    Ok(IndicatorOutput::new(output))
}
