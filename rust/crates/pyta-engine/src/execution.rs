use std::panic::{AssertUnwindSafe, catch_unwind};

use pyta_core::{IndicatorOutput, PytaError, PytaResult};

use crate::dispatch::dispatch;
use crate::requests::IndicatorRequest;

/// Executes one indicator request on the calling thread.
///
/// A panic inside the kernel is caught and reported as `PytaError::ExecutionFailed`.
pub fn execute_direct(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    catch_unwind(AssertUnwindSafe(|| dispatch(request))).unwrap_or(Err(PytaError::ExecutionFailed))
}
