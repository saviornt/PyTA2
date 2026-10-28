//! PyTA indicator execution engine.

mod batch;
mod dispatch;
mod execution;
mod planner;
mod requests;
#[cfg(test)]
mod test_log;

pub use batch::{execute_batch, execute_parallel, execute_sequential};
pub use execution::execute_direct;
pub use planner::should_parallelize;
pub use requests::{
    IndicatorInput, IndicatorKind, IndicatorRequest, IndicatorResult, IndicatorStatus,
};
