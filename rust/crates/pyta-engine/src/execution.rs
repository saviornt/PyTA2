use std::panic::{AssertUnwindSafe, catch_unwind};

use pyta_core::{IndicatorOutput, PytaError, PytaResult};
use tokio::sync::oneshot;

use crate::dispatch::dispatch;
use crate::requests::IndicatorRequest;

/// Executes one indicator request on Rayon's worker pool.
///
/// A panic inside the kernel is caught and reported as `PytaError::ExecutionFailed`.
pub fn execute_direct(request: &IndicatorRequest) -> PytaResult<IndicatorOutput> {
    catch_unwind(AssertUnwindSafe(|| dispatch(request))).unwrap_or(Err(PytaError::ExecutionFailed))
}

/// Executes one request on Rayon's worker pool, delivering the result
/// through a oneshot channel. Used by batch execution.
pub(crate) async fn execute(request: IndicatorRequest) -> PytaResult<IndicatorOutput> {
    let (sender, receiver) = oneshot::channel();

    rayon::spawn(move || {
        let _ = sender.send(execute_direct(&request));
    });

    receiver.await.map_err(|_| PytaError::ExecutionFailed)?
}
