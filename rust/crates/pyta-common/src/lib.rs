//! Tunable constants shared across PyTA.
//!
//! This crate holds values worth adjusting while tuning performance, and
//! parameters shared by benchmarks and tests. It has no dependencies and no
//! logic, so every other PyTA crate may depend on it. Values that define an
//! algorithm (for example RSI's 0 to 100 scale) stay with their formula.
//!
//! Each constant documents what it means and, where it came from a
//! measurement, which benchmark and machine produced it.

pub mod benchmarks;
pub mod costs;
pub mod limits;
pub mod scheduling;

pub use benchmarks::*;
pub use costs::*;
pub use limits::*;
pub use scheduling::*;
