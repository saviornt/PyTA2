//! A `log` logger for unit tests that captures records per thread.
//!
//! Tests run in parallel and the logger is global, so each test reads back
//! only the records its own thread logged.

use std::sync::{Mutex, Once, PoisonError};
use std::thread::{self, ThreadId};

use log::{Level, LevelFilter, Log, Metadata, Record};

/// A captured record: level, target and message.
pub(crate) type Captured = (Level, String, String);

static RECORDS: Mutex<Vec<(ThreadId, Captured)>> = Mutex::new(Vec::new());

struct Capture;

impl Log for Capture {
    fn enabled(&self, _: &Metadata<'_>) -> bool {
        true
    }

    fn log(&self, record: &Record<'_>) {
        let captured = (
            record.level(),
            record.target().to_owned(),
            record.args().to_string(),
        );
        RECORDS
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push((thread::current().id(), captured));
    }

    fn flush(&self) {}
}

/// Runs `f` with every level enabled and returns the records it logged.
pub(crate) fn capture(f: impl FnOnce()) -> Vec<Captured> {
    static INIT: Once = Once::new();
    INIT.call_once(|| {
        log::set_logger(&Capture).expect("no other logger in unit tests");
        log::set_max_level(LevelFilter::Trace);
    });

    let id = thread::current().id();
    f();

    let mut records = RECORDS.lock().unwrap_or_else(PoisonError::into_inner);
    let (mine, others) = records.drain(..).partition(|(thread, _)| *thread == id);
    *records = others;

    mine.into_iter().map(|(_, captured)| captured).collect()
}
