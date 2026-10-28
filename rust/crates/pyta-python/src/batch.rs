use std::sync::{Arc, Mutex, OnceLock, PoisonError};

use numpy::{IntoPyArray, PyReadonlyArray1};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_core::{IndicatorOutput, PytaError, PytaResult};
use pyta_engine::{
    IndicatorInput, IndicatorKind, IndicatorRequest, IndicatorResult, IndicatorStatus,
    execute_parallel, execute_sequential, should_parallelize,
};
use rayon::{ThreadPool, ThreadPoolBuilder};

use crate::error::to_python_error;
use crate::single::{columns_from, series_from};

/// Number of workers available to this process, computed once.
///
/// `available_parallelism` re-reads OS state on every call, which is far
/// too slow for the planner's hot path.
fn available_workers() -> usize {
    static WORKERS: OnceLock<usize> = OnceLock::new();

    *WORKERS.get_or_init(|| std::thread::available_parallelism().map_or(1, usize::from))
}

/// The Rayon pool for parallel batches, created on first use.
///
/// A forked child does not inherit its parent's worker threads, so work
/// sent to an inherited pool would wait forever. The pool therefore
/// remembers the process that built it and is rebuilt in a child. PyTA has
/// its own pool, rather than Rayon's global one, so this can be done safely.
fn pool() -> Arc<ThreadPool> {
    static POOL: Mutex<Option<(u32, Arc<ThreadPool>)>> = Mutex::new(None);

    let mut slot = POOL.lock().unwrap_or_else(PoisonError::into_inner);
    let pid = std::process::id();

    if let Some((owner, pool)) = slot.as_ref()
        && *owner == pid
    {
        return Arc::clone(pool);
    }

    // Dropping the parent's pool would wait for threads that do not exist.
    if let Some((parent, stale)) = slot.take() {
        log::debug!(
            target: "pyta::bridge",
            "rebuilding the worker pool after fork (parent process {parent}, child {pid})"
        );
        std::mem::forget(stale);
    }

    let pool = Arc::new(
        ThreadPoolBuilder::new()
            .num_threads(available_workers())
            .thread_name(|index| format!("pyta-worker-{index}"))
            .build()
            .expect("failed to start the PyTA worker pool"),
    );
    *slot = Some((pid, Arc::clone(&pool)));
    log::debug!(
        target: "pyta::bridge",
        "started the worker pool with {} threads",
        pool.current_num_threads()
    );

    pool
}

/// Runs a batch sequentially or in parallel, as the planner predicts is faster.
fn run_batch(requests: &[IndicatorRequest]) -> Vec<IndicatorResult> {
    if should_parallelize(requests, available_workers()) {
        pool().install(|| execute_parallel(requests))
    } else {
        execute_sequential(requests)
    }
}

/// Validates every dataset, runs the valid ones as one batch with the GIL
/// released, and returns a list in input order.
///
/// Each entry is a float64 array, or the exception explaining why that
/// dataset failed. A failed dataset never affects the others.
pub(crate) fn compute_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyList>> {
    run_datasets(py, datasets, period, kind, |item| {
        let values = item.extract::<PyReadonlyArray1<f64>>()?;

        Ok(series_from(&values).map(IndicatorInput::Series))
    })
}

/// Like [`compute_batch`], for a multi-column indicator: each dataset is a
/// list of its input columns in slot order.
pub(crate) fn compute_columns_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyList>> {
    run_datasets(py, datasets, period, kind, |item| {
        let columns = item.extract::<Vec<PyReadonlyArray1<f64>>>()?;

        Ok(columns_from(&columns).map(IndicatorInput::Columns))
    })
}

/// The shared batch path: `read` copies and validates one dataset, and a
/// dataset it rejects becomes that dataset's exception.
fn run_datasets<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    kind: IndicatorKind,
    read: impl Fn(&Bound<'py, PyAny>) -> PyResult<PytaResult<IndicatorInput>>,
) -> PyResult<Bound<'py, PyList>> {
    // Picks up logging levels changed since the last call, so the planner and
    // pool records below are skipped cheaply when DEBUG is off.
    crate::log_bridge::refresh_max_level(py);

    let total = datasets.len();
    let mut failures: Vec<Option<PytaError>> = (0..total).map(|_| None).collect();
    let mut positions = Vec::with_capacity(total);
    let mut requests = Vec::with_capacity(total);

    for (position, item) in datasets.iter().enumerate() {
        // Copied once, with validation fused into the copy, so the GIL
        // can be released while another thread mutates the caller's array.
        match read(&item)? {
            Ok(input) => {
                positions.push(position);
                requests.push(IndicatorRequest {
                    kind,
                    input,
                    period,
                });
            }
            Err(error) => failures[position] = Some(error),
        }
    }

    let results = py.detach(move || run_batch(&requests));

    let mut outputs: Vec<Option<IndicatorOutput>> = (0..total).map(|_| None).collect();

    for result in results {
        let position = positions[result.index];

        match result.status {
            IndicatorStatus::Success(output) => outputs[position] = Some(output),
            IndicatorStatus::Error(error) => failures[position] = Some(error),
        }
    }

    let entries = outputs
        .into_iter()
        .zip(failures)
        .map(|(output, failure)| match (output, failure) {
            (Some(output), _) => Ok(output.into_values().into_pyarray(py).into_any()),
            (None, Some(error)) => Ok(to_python_error(error)
                .into_value(py)
                .into_bound(py)
                .into_any()),
            (None, None) => Err(PyRuntimeError::new_err("batch result missing")),
        })
        .collect::<PyResult<Vec<_>>>()?;

    PyList::new(py, entries)
}
