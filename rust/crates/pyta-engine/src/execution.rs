use std::any::Any;
use std::panic::{AssertUnwindSafe, catch_unwind};

use pyta_core::{IndicatorOutput, PytaError, PytaResult};

use crate::dispatch::dispatch;
use crate::requests::IndicatorRequest;

/// Executes one indicator request on the calling thread.
///
/// A panic inside the kernel is caught, logged at ERROR (target
/// `pyta::engine`), and reported as `PytaError::ExecutionFailed`.
///
/// # Errors
///
/// The kernel's own error for invalid parameters (for example a period
/// longer than the series), or `ExecutionFailed` if it panicked.
pub fn execute_direct(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    run_caught(request, || dispatch(request))
}

/// Runs `calculate`, turning a panic into a logged `ExecutionFailed`.
fn run_caught(
    request: &IndicatorRequest,
    calculate: impl FnOnce() -> PytaResult<IndicatorOutput>,
) -> PytaResult<IndicatorOutput> {
    catch_unwind(AssertUnwindSafe(calculate)).unwrap_or_else(|payload| {
        // Panics are bugs, so this path is never hot; logging here may take
        // the GIL from a worker thread, which the bridge allows.
        log::error!(
            target: "pyta::engine",
            "{:?} kernel panicked on {} values: {}",
            request.params,
            request.input.len(),
            panic_message(payload.as_ref()),
        );
        Err(PytaError::ExecutionFailed)
    })
}

/// The message a panic was raised with, if it was a string.
fn panic_message(payload: &(dyn Any + Send)) -> &str {
    payload
        .downcast_ref::<&str>()
        .copied()
        .or_else(|| payload.downcast_ref::<String>().map(String::as_str))
        .unwrap_or("non-string panic payload")
}

#[cfg(test)]
mod tests {
    use log::Level;
    use pyta_core::{PytaError, Series};

    use super::run_caught;
    use crate::requests::{IndicatorRequest, Params};
    use crate::test_log::capture;

    #[test]
    fn a_panic_becomes_execution_failed_and_is_logged_at_error() {
        let request = IndicatorRequest::new(
            Series::new(vec![1.0; 3]).unwrap(),
            Params::Sma { period: 2 },
        );
        let mut result = None;

        let records = capture(|| result = Some(run_caught(&request, || panic!("kernel bug"))));

        assert_eq!(result, Some(Err(PytaError::ExecutionFailed)));
        assert_eq!(
            records,
            [(
                Level::Error,
                "pyta::engine".to_owned(),
                "Sma { period: 2 } kernel panicked on 3 values: kernel bug".to_owned()
            )]
        );
    }

    #[test]
    fn a_successful_request_logs_nothing() {
        let request = IndicatorRequest::new(
            Series::new(vec![1.0; 3]).unwrap(),
            Params::Sma { period: 2 },
        );

        let records = capture(|| {
            run_caught(&request, || crate::dispatch::dispatch(&request)).unwrap();
        });

        assert!(records.is_empty());
    }
}
