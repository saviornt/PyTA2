//! Forwards PyTA's Rust `log` records to Python's `logging`.
//!
//! Python's `logging` is PyTA's one logging system. Rust code uses the `log`
//! macros with targets such as `pyta::planner`, and this bridge hands each
//! record to the Python logger of the same dotted name (`pyta.planner`), so
//! Rust and Python messages share one stream and one configuration. It stands
//! in for the `pyo3-log` crate, which does not support PyO3 0.30 yet.
//!
//! Levels: `log`'s global maximum level is an atomic that every macro checks
//! first. It is set from Python when the module loads and refreshed at the
//! start of each batch call (see [`refresh_max_level`]), so disabled logging
//! costs one atomic load per log statement. A record that passes is checked
//! again against its own logger with `isEnabledFor`, which also honors
//! `logging.disable()`.

use log::{Level, LevelFilter, Log, Metadata, Record};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::PyTuple;

/// PyTA's Rust log targets and the Python loggers they map to.
const TARGETS: [(&str, &str); 3] = [
    ("pyta::engine", "pyta.engine"),
    ("pyta::planner", "pyta.planner"),
    ("pyta::bridge", "pyta.bridge"),
];

/// The Python logger objects for `TARGETS`, looked up once.
static LOGGERS: [PyOnceLock<Py<PyAny>>; 3] =
    [PyOnceLock::new(), PyOnceLock::new(), PyOnceLock::new()];

/// Installs the bridge and reads the current Python levels.
///
/// Called once when `pyta._native` is imported.
pub(crate) fn init(py: Python<'_>) {
    static BRIDGE: Bridge = Bridge;

    // Fails only if the bridge is already installed, which is fine.
    let _ = log::set_logger(&BRIDGE);
    refresh_max_level(py);
}

/// Sets `log`'s maximum level from the PyTA Rust loggers' Python levels, so
/// disabled statements are skipped without touching Python.
///
/// This runs on every batch call, so it asks only the cheap question Python
/// caches the answer to: is any of them enabled for DEBUG (or TRACE)? If not,
/// the maximum is INFO, and the few records at INFO or above are checked
/// exactly in [`Bridge::log`]. (PyTA's Rust code logs at DEBUG and ERROR.)
pub(crate) fn refresh_max_level(py: Python<'_>) {
    let any_enabled_for = |level: Level| {
        (0..TARGETS.len()).any(|index| {
            cached_logger(py, index)
                .and_then(|logger| is_enabled_for(&logger, level))
                .unwrap_or(false)
        })
    };

    let max_level = if !any_enabled_for(Level::Debug) {
        LevelFilter::Info
    } else if any_enabled_for(Level::Trace) {
        LevelFilter::Trace
    } else {
        LevelFilter::Debug
    };

    log::set_max_level(max_level);
}

struct Bridge;

impl Log for Bridge {
    fn enabled(&self, metadata: &Metadata<'_>) -> bool {
        Python::attach(|py| {
            logger(py, metadata.target())
                .and_then(|logger| is_enabled_for(&logger, metadata.level()))
                .unwrap_or(false)
        })
    }

    fn log(&self, record: &Record<'_>) {
        // Takes the GIL, so PyTA only logs outside the kernels and their
        // loops, from the thread that called into Rust.
        Python::attach(|py| {
            if let Err(error) = emit(py, record) {
                error.write_unraisable(py, None);
            }
        });
    }

    fn flush(&self) {}
}

/// Hands `record` to its Python logger, keeping the Rust file and line.
fn emit(py: Python<'_>, record: &Record<'_>) -> PyResult<()> {
    let logger = logger(py, record.target())?;

    if !is_enabled_for(&logger, record.level())? {
        return Ok(());
    }

    let python_record = logger.call_method1(
        intern!(py, "makeRecord"),
        (
            logger.getattr(intern!(py, "name"))?,
            python_level(record.level()),
            record.file().unwrap_or("<rust>"),
            record.line().unwrap_or(0),
            record.args().to_string(),
            PyTuple::empty(py),
            py.None(),
            record.module_path(),
        ),
    )?;
    logger.call_method1(intern!(py, "handle"), (python_record,))?;

    Ok(())
}

fn is_enabled_for(logger: &Bound<'_, PyAny>, level: Level) -> PyResult<bool> {
    logger
        .call_method1(intern!(logger.py(), "isEnabledFor"), (python_level(level),))?
        .is_truthy()
}

/// The Python logger for a Rust target: `pyta::planner` becomes `pyta.planner`.
fn logger<'py>(py: Python<'py>, target: &str) -> PyResult<Bound<'py, PyAny>> {
    match TARGETS.iter().position(|(rust, _)| *rust == target) {
        Some(index) => cached_logger(py, index),
        None => get_logger(py, &target.replace("::", ".")),
    }
}

fn cached_logger(py: Python<'_>, index: usize) -> PyResult<Bound<'_, PyAny>> {
    LOGGERS[index]
        .get_or_try_init(py, || get_logger(py, TARGETS[index].1).map(Bound::unbind))
        .map(|logger| logger.bind(py).clone())
}

fn get_logger<'py>(py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
    py.import("logging")?.call_method1("getLogger", (name,))
}

/// Python's numeric level for a Rust level. Python has no TRACE; 5 sits below
/// DEBUG, as is conventional.
fn python_level(level: Level) -> u8 {
    match level {
        Level::Error => 40,
        Level::Warn => 30,
        Level::Info => 20,
        Level::Debug => 10,
        Level::Trace => 5,
    }
}

#[cfg(test)]
mod tests {
    use log::Level;

    use super::python_level;

    #[test]
    fn rust_levels_map_to_python_levels() {
        let levels = [
            Level::Error,
            Level::Warn,
            Level::Info,
            Level::Debug,
            Level::Trace,
        ];

        assert_eq!(levels.map(python_level), [40, 30, 20, 10, 5]);
    }
}
