use pyta_core::{IndicatorOutput, PytaError, PytaResult};
use tokio::sync::oneshot;

use crate::dispatch::dispatch;
use crate::requests::IndicatorRequest;

/// Executes one indicator request on Rayon's worker pool.
///
/// The calculation runs outside the Tokio async worker thread.
/// The result is delivered back to the async caller through a
/// Tokio oneshot channel.
pub(crate) async fn execute(
    request: IndicatorRequest,
) -> PytaResult<IndicatorOutput> {
    let (sender, receiver) = oneshot::channel();

    rayon::spawn(move || {
        let result = dispatch(&request);
        let _ = sender.send(result);
    });

    receiver
        .await
        .map_err(|_| PytaError::ExecutionFailed)?
}