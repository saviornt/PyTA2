//! Compares sequential execution against the parallel batch engine.
//!
//! Each workload runs at several input sizes in four arms:
//! - `sequential`: `execute_sequential`, the function `auto` uses when it stays sequential.
//! - `parallel`: `execute_parallel` (Rayon), the function `auto` uses for parallel work.
//! - `batch`: `execute_batch`, the async front door that hands the batch to Rayon in one hop.
//! - `auto`: the planner's choice between `sequential` and `parallel`.
//!
//! `few_requests` covers 3 to 10 requests and `many_datasets` 10 to 1,000, where the
//! planner's choice matters most.
//!
//! Inputs are fully finite seeded random walks, because `Series::new`
//! rejects NaN and infinity.

use criterion::{BatchSize, BenchmarkId, Criterion, SamplingMode, criterion_group, criterion_main};
use pyta_common::{
    FEW_REQUEST_COUNTS, FEW_REQUEST_SIZES, LARGE_INPUT_LEN, LARGE_SAMPLE_SIZE, MANY_DATASET_COUNTS,
    MANY_DATASET_SIZES, SAMPLE_SIZE, WORKLOAD_SIZES,
};
use pyta_core::{Columns, Series};
use pyta_engine::{
    IndicatorKind, IndicatorRequest, Params, execute_batch, execute_parallel, execute_sequential,
    should_parallelize,
};
use tokio::runtime::Builder;

const DS1_SEED: u64 = 0x9E37_79B9_7F4A_7C15;
const DS2_SEED: u64 = 0xD1B5_4A32_D192_ED03;

#[derive(Clone, Copy)]
enum Dataset {
    One,
    Two,
}

struct Workload {
    name: &'static str,
    jobs: &'static [(IndicatorKind, Dataset)],
}

const WORKLOADS: &[Workload] = &[
    Workload {
        name: "1_sma_ds1",
        jobs: &[(IndicatorKind::Sma, Dataset::One)],
    },
    Workload {
        name: "2_rsi_ds1",
        jobs: &[(IndicatorKind::Rsi, Dataset::One)],
    },
    Workload {
        name: "3_sma_rsi_ds1",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Rsi, Dataset::One),
        ],
    },
    Workload {
        name: "4_sma_sma_ds1_ds2",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Sma, Dataset::Two),
        ],
    },
    Workload {
        name: "5_rsi_rsi_ds1_ds2",
        jobs: &[
            (IndicatorKind::Rsi, Dataset::One),
            (IndicatorKind::Rsi, Dataset::Two),
        ],
    },
    Workload {
        name: "6_sma_rsi_ds1_ds2",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Rsi, Dataset::One),
            (IndicatorKind::Sma, Dataset::Two),
            (IndicatorKind::Rsi, Dataset::Two),
        ],
    },
];

/// The parameters each indicator is benchmarked with.
fn params(kind: IndicatorKind) -> Params {
    match kind {
        IndicatorKind::Ad => Params::Ad,
        IndicatorKind::Adx => Params::Adx { period: 14 },
        IndicatorKind::Aroon => Params::Aroon { period: 14 },
        IndicatorKind::Atr => Params::Atr { period: 14 },
        IndicatorKind::Bbands => Params::Bbands { period: 20, k: 2.0 },
        IndicatorKind::Cci => Params::Cci { period: 14 },
        IndicatorKind::Stoch => Params::Stoch {
            k: 14,
            k_smooth: 3,
            d: 3,
        },
        IndicatorKind::Willr => Params::Willr { period: 14 },
        IndicatorKind::Roc => Params::Roc { period: 10 },
        IndicatorKind::Mfi => Params::Mfi { period: 14 },
        IndicatorKind::Obv => Params::Obv,
        IndicatorKind::Trix => Params::Trix { period: 30 },
        IndicatorKind::Ultosc => Params::Ultosc {
            short: 7,
            medium: 14,
            long: 28,
        },
        IndicatorKind::Donchian => Params::Donchian { period: 20 },
        IndicatorKind::Ema => Params::Ema { period: 20 },
        IndicatorKind::Ichimoku => Params::Ichimoku {
            tenkan: 9,
            kijun: 26,
            senkou: 52,
        },
        IndicatorKind::Keltner => Params::Keltner {
            period: 20,
            atr_period: 10,
            k: 2.0,
        },
        IndicatorKind::Macd => Params::Macd {
            fast: 12,
            slow: 26,
            signal: 9,
        },
        IndicatorKind::Rsi => Params::Rsi { period: 14 },
        IndicatorKind::Sma => Params::Sma { period: 20 },
        IndicatorKind::Stddev => Params::Stddev { period: 5, k: 1.0 },
        IndicatorKind::Wma => Params::Wma { period: 30 },
        IndicatorKind::Dema => Params::Dema { period: 30 },
        IndicatorKind::Tema => Params::Tema { period: 30 },
        IndicatorKind::Kama => Params::Kama { period: 30 },
        IndicatorKind::Sar => Params::Sar {
            acceleration: 0.02,
            maximum: 0.2,
        },
    }
}

/// A request for `kind` on `close`. Multi-column indicators get high and
/// low made by offsetting `close`, in their slot order.
fn request(kind: IndicatorKind, close: Series) -> IndicatorRequest {
    let offset = |by: f64| {
        Series::new(close.values().iter().map(|value| value + by).collect())
            .expect("offset prices are finite")
    };

    match kind {
        IndicatorKind::Adx
        | IndicatorKind::Atr
        | IndicatorKind::Cci
        | IndicatorKind::Ichimoku
        | IndicatorKind::Keltner
        | IndicatorKind::Stoch
        | IndicatorKind::Ultosc
        | IndicatorKind::Willr => {
            let columns = Columns::new(vec![offset(0.5), offset(-0.5), close])
                .expect("columns have equal lengths");
            IndicatorRequest::with_columns(columns, params(kind))
        }
        IndicatorKind::Ad | IndicatorKind::Mfi => {
            // Volume: a positive column of the same shape.
            let volume = offset(1_000.0);
            let columns = Columns::new(vec![offset(0.5), offset(-0.5), close, volume])
                .expect("columns have equal lengths");
            IndicatorRequest::with_columns(columns, params(kind))
        }
        IndicatorKind::Obv => {
            // Volume: a positive column of the same shape.
            let volume = offset(1_000.0);
            let columns = Columns::new(vec![close, volume]).expect("columns have equal lengths");
            IndicatorRequest::with_columns(columns, params(kind))
        }
        IndicatorKind::Aroon | IndicatorKind::Donchian | IndicatorKind::Sar => {
            let columns =
                Columns::new(vec![offset(0.5), offset(-0.5)]).expect("columns have equal lengths");
            IndicatorRequest::with_columns(columns, params(kind))
        }
        IndicatorKind::Bbands
        | IndicatorKind::Ema
        | IndicatorKind::Macd
        | IndicatorKind::Roc
        | IndicatorKind::Trix
        | IndicatorKind::Rsi
        | IndicatorKind::Sma
        | IndicatorKind::Stddev
        | IndicatorKind::Wma
        | IndicatorKind::Dema
        | IndicatorKind::Tema
        | IndicatorKind::Kama => IndicatorRequest::new(close, params(kind)),
    }
}

/// Deterministic, finite, positive "closing prices" (xorshift64 random walk).
fn random_walk(seed: u64, len: usize) -> Series {
    let mut state = seed;
    let mut price = 100.0_f64;

    let values = (0..len)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;

            let unit = (state >> 11) as f64 / (1_u64 << 53) as f64;
            price = (price + (unit - 0.5) * 2.0).max(1.0);
            price
        })
        .collect();

    Series::new(values).expect("generated prices are finite and non-empty")
}

fn build_requests(
    jobs: &[(IndicatorKind, Dataset)],
    one: &Series,
    two: &Series,
) -> Vec<IndicatorRequest> {
    jobs.iter()
        .map(|&(kind, dataset)| {
            let series = match dataset {
                Dataset::One => one,
                Dataset::Two => two,
            };

            request(kind, series.clone())
        })
        .collect()
}

fn workloads(c: &mut Criterion) {
    // Engine log records go to stderr only when RUST_LOG asks for them (for
    // example RUST_LOG=pyta::planner=debug); otherwise logging stays off.
    let _ = env_logger::try_init();

    let runtime = Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("failed to build Tokio runtime");

    let cores = std::thread::available_parallelism().map_or(1, usize::from);
    eprintln!("available_parallelism = {cores}");

    for workload in WORKLOADS {
        let mut group = c.benchmark_group(workload.name);

        for size in WORKLOAD_SIZES {
            group.sample_size(if size >= LARGE_INPUT_LEN {
                LARGE_SAMPLE_SIZE
            } else {
                SAMPLE_SIZE
            });

            let ds1 = random_walk(DS1_SEED, size);
            let ds2 = random_walk(DS2_SEED, size);
            let requests = build_requests(workload.jobs, &ds1, &ds2);

            // All three arms use the same harness so they differ only in the
            // strategy under test: each iteration gets a fresh clone of the
            // requests (made outside the timed section), and results, and the
            // requests when the strategy borrows them, are returned so Criterion
            // drops them outside the timed section. A `sequential` arm built
            // on `iter_with_large_drop` instead kept every output alive for the
            // whole sample, which made it look 10-15% slower than identical code.
            group.bench_function(BenchmarkId::new("sequential", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        let results = execute_sequential(&batch);
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
            });

            group.bench_function(BenchmarkId::new("parallel", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        let results = execute_parallel(&batch);
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
            });

            group.bench_function(BenchmarkId::new("batch", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| runtime.block_on(execute_batch(batch)),
                    BatchSize::LargeInput,
                );
            });

            group.bench_function(BenchmarkId::new("auto", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        let results = if should_parallelize(&batch, rayon::current_num_threads()) {
                            execute_parallel(&batch)
                        } else {
                            execute_sequential(&batch)
                        };
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
            });
        }

        group.finish();
    }
}

/// One indicator over many datasets, comparing every way of running a batch.
///
/// Groups are named `many_<indicator>_x<count>` and sized by points per
/// dataset. Arms:
/// - `sequential`, `parallel`, `batch`, `auto`: as in `workloads`.
fn many_datasets(c: &mut Criterion) {
    let runtime = Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("failed to build Tokio runtime");

    for (kind, label) in [
        (IndicatorKind::Sma, "sma"),
        (IndicatorKind::Rsi, "rsi"),
        (IndicatorKind::Cci, "cci"),
        (IndicatorKind::Stoch, "stoch"),
        (IndicatorKind::Willr, "willr"),
        (IndicatorKind::Roc, "roc"),
        (IndicatorKind::Mfi, "mfi"),
        (IndicatorKind::Obv, "obv"),
        (IndicatorKind::Ad, "ad"),
        (IndicatorKind::Trix, "trix"),
        (IndicatorKind::Ultosc, "ultosc"),
        (IndicatorKind::Ema, "ema"),
        (IndicatorKind::Wma, "wma"),
        (IndicatorKind::Dema, "dema"),
        (IndicatorKind::Tema, "tema"),
        (IndicatorKind::Kama, "kama"),
        (IndicatorKind::Adx, "adx"),
        (IndicatorKind::Aroon, "aroon"),
        (IndicatorKind::Ichimoku, "ichimoku"),
        (IndicatorKind::Sar, "sar"),
        (IndicatorKind::Macd, "macd"),
        (IndicatorKind::Atr, "atr"),
        (IndicatorKind::Stddev, "stddev"),
        (IndicatorKind::Bbands, "bbands"),
        (IndicatorKind::Donchian, "donchian"),
        (IndicatorKind::Keltner, "keltner"),
    ] {
        for count in MANY_DATASET_COUNTS {
            let mut group = c.benchmark_group(format!("many_{label}_x{count}"));

            for size in MANY_DATASET_SIZES {
                if count * size >= LARGE_INPUT_LEN {
                    group.sample_size(LARGE_SAMPLE_SIZE);
                    group.sampling_mode(SamplingMode::Flat);
                } else {
                    group.sample_size(SAMPLE_SIZE);
                    group.sampling_mode(SamplingMode::Auto);
                }

                let requests: Vec<IndicatorRequest> = (0..count)
                    .map(|i| {
                        let series = random_walk(DS1_SEED.wrapping_add(i as u64), size);
                        request(kind, series)
                    })
                    .collect();

                // Same harness for every arm: see `workloads`.
                group.bench_function(BenchmarkId::new("sequential", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_sequential(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("batch", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| runtime.block_on(execute_batch(batch)),
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("auto", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results =
                                if should_parallelize(&batch, rayon::current_num_threads()) {
                                    execute_parallel(&batch)
                                } else {
                                    execute_sequential(&batch)
                                };
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("parallel", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_parallel(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });
            }

            group.finish();
        }
    }
}

/// A handful of requests (3 to 10), where the planner's choice is closest.
///
/// Groups are named `few_<indicators>_x<count>` and sized by points per
/// request; `sma_rsi` alternates the two indicators. Arms are `sequential`,
/// `parallel` and `auto`: `batch` only adds a fixed async hop.
fn few_requests(c: &mut Criterion) {
    let mixes: [(&str, &[IndicatorKind]); 3] = [
        ("sma", &[IndicatorKind::Sma]),
        ("rsi", &[IndicatorKind::Rsi]),
        ("sma_rsi", &[IndicatorKind::Sma, IndicatorKind::Rsi]),
    ];

    for (label, kinds) in mixes {
        for count in FEW_REQUEST_COUNTS {
            let mut group = c.benchmark_group(format!("few_{label}_x{count}"));
            group.sample_size(SAMPLE_SIZE);

            for size in FEW_REQUEST_SIZES {
                let requests: Vec<IndicatorRequest> = (0..count)
                    .map(|i| {
                        let kind = kinds[i % kinds.len()];
                        let series = random_walk(DS1_SEED.wrapping_add(i as u64), size);
                        request(kind, series)
                    })
                    .collect();

                // Same harness for every arm: see `workloads`.
                group.bench_function(BenchmarkId::new("sequential", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_sequential(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("parallel", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_parallel(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("auto", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results =
                                if should_parallelize(&batch, rayon::current_num_threads()) {
                                    execute_parallel(&batch)
                                } else {
                                    execute_sequential(&batch)
                                };
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });
            }

            group.finish();
        }
    }
}

criterion_group!(benches, workloads, many_datasets, few_requests);
criterion_main!(benches);
