#!/usr/bin/env bash
# Runs PyTA benchmarks and writes a timestamped report to benches/results/.
#
# The report has a summary at the top (options, environment, and result
# tables) and the full output of every step below it. Run on a quiet machine:
# other load makes timings noisy. See scripts/README.md for details.
set -uo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/benchmark.sh (--single | --batch | --all) [options]

What to run (at least one is required):
  --single           single-dataset calls (direct path)
  --batch            many-dataset calls (batch path)
  --all              both

Options:
  --rust             only the Rust (Criterion) benchmarks
  --python           only the Python benchmarks
  --indicator NAME   only benchmarks for one indicator (for example sma)
  --quick            shorter runs for fast iteration; not comparable with full runs
  -h, --help         show this help
USAGE
}

ORIGINAL_ARGS="$*"

RUN_SINGLE=0
RUN_BATCH=0
RUN_RUST=0
RUN_PYTHON=0
INDICATOR=""
QUICK=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --single) RUN_SINGLE=1 ;;
        --batch) RUN_BATCH=1 ;;
        --all) RUN_SINGLE=1 RUN_BATCH=1 ;;
        --rust) RUN_RUST=1 ;;
        --python) RUN_PYTHON=1 ;;
        --quick) QUICK=1 ;;
        --indicator)
            if [[ $# -lt 2 || $2 == -* ]]; then
                echo "error: --indicator needs a name" >&2
                exit 2
            fi
            INDICATOR=$2
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            echo >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [[ $RUN_SINGLE -eq 0 && $RUN_BATCH -eq 0 ]]; then
    echo "error: choose what to run: --single, --batch, or --all" >&2
    echo >&2
    usage >&2
    exit 2
fi

# No layer flag means both layers.
if [[ $RUN_RUST -eq 0 && $RUN_PYTHON -eq 0 ]]; then
    RUN_RUST=1 RUN_PYTHON=1
fi

if [[ -n $INDICATOR && ! $INDICATOR =~ ^[a-z0-9_]+$ ]]; then
    echo "error: --indicator takes a lowercase name such as sma, got: $INDICATOR" >&2
    exit 2
fi

# Resolve the project root from this script's location.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Plain text only, so the report is readable in any editor.
export NO_COLOR=1 CARGO_TERM_COLOR=never

STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
STARTED_EPOCH="$(date +%s)"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
RESULTS_DIR="$PROJECT_ROOT/benches/results"
REPORT="$RESULTS_DIR/benchmark_${STAMP}.txt"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$RESULTS_DIR"

NAMES=()
STATUSES=()
SECONDS_TAKEN=()
FAILED=0
LAST=-1

# run_step <name> <command...>: runs a step, echoes its output live, and
# records its status, duration, and output for the report. Sets LAST to the
# step's index.
run_step() {
    local name=$1
    shift
    local index=${#NAMES[@]}
    local log="$WORK/step_${index}.log"
    local start=$SECONDS

    echo "==> $name"
    "$@" 2>&1 | tee "$log"
    local status=${PIPESTATUS[0]}
    echo

    LAST=$index
    NAMES+=("$name")
    SECONDS_TAKEN+=($((SECONDS - start)))

    if [[ $status -ne 0 ]]; then
        STATUSES+=("FAIL")
        FAILED=$((FAILED + 1))
    else
        STATUSES+=("PASS")
    fi
}

# skip_step <name> <reason>: records a step that did not run.
skip_step() {
    local index=${#NAMES[@]}

    echo "==> $1 skipped: $2"
    echo
    echo "Skipped: $2" > "$WORK/step_${index}.log"
    LAST=$index
    NAMES+=("$1")
    STATUSES+=("SKIP")
    SECONDS_TAKEN+=(0)
}

log_of() { echo "$WORK/step_$1.log"; }

# ---- Run --------------------------------------------------------------

CRITERION_ARGS=(--noplot)
[[ $QUICK -eq 1 ]] && CRITERION_ARGS+=(--quick)
[[ -n $INDICATOR ]] && CRITERION_ARGS+=("$INDICATOR")

PYTHON_ARGS=()
[[ $QUICK -eq 1 ]] && PYTHON_ARGS+=(--quick)
[[ -n $INDICATOR ]] && PYTHON_ARGS+=("$INDICATOR")

RUST_PASSED=0
SUMMARY_IDX=-1
PY_SINGLE_IDX=-1
PY_BATCH_IDX=-1

if [[ $RUN_PYTHON -eq 1 ]]; then
    # The Python numbers are only meaningful with a release build.
    run_step "Build Python extension (release)" \
        uv run maturin develop --release \
        --manifest-path rust/crates/pyta-python/Cargo.toml
fi

if [[ $RUN_RUST -eq 1 ]]; then
    # `--bench` runs only the named Criterion target; the library has none.
    if [[ $RUN_SINGLE -eq 1 ]]; then
        run_step "Rust single-call benchmarks (Criterion)" \
            cargo bench -p pyta-engine --bench single_call -- "${CRITERION_ARGS[@]}"
        [[ ${STATUSES[$LAST]} == PASS ]] && RUST_PASSED=$((RUST_PASSED + 1))
    fi

    if [[ $RUN_BATCH -eq 1 ]]; then
        run_step "Rust batch benchmarks (Criterion)" \
            cargo bench -p pyta-engine --bench workloads -- "${CRITERION_ARGS[@]}"
        [[ ${STATUSES[$LAST]} == PASS ]] && RUST_PASSED=$((RUST_PASSED + 1))
    fi

    # Only files written since this run started are summarized, so a filtered
    # run never reports older numbers. After a total failure there is nothing
    # fresh to report.
    if [[ $RUST_PASSED -gt 0 ]]; then
        run_step "Criterion summary" python3 scripts/benchmark_summary.py --since "$STARTED_EPOCH"
    else
        skip_step "Criterion summary" "the Criterion benchmarks failed, so no fresh results exist."
    fi
    SUMMARY_IDX=$LAST
fi

if [[ $RUN_PYTHON -eq 1 ]]; then
    if [[ $RUN_SINGLE -eq 1 ]]; then
        run_step "Python single-call benchmark" \
            uv run python benches/python/bench_boundary.py "${PYTHON_ARGS[@]}"
        PY_SINGLE_IDX=$LAST
    fi

    if [[ $RUN_BATCH -eq 1 ]]; then
        run_step "Python batch benchmark" \
            uv run python benches/python/bench_batch.py "${PYTHON_ARGS[@]}"
        PY_BATCH_IDX=$LAST
    fi
fi

# ---- Report -----------------------------------------------------------

git_commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    git_state="uncommitted changes"
else
    git_state="clean"
fi

cpu_model="$(awk -F': ' '/^model name/ {print $2; exit}' /proc/cpuinfo 2>/dev/null)"
governor="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown)"

if [[ $FAILED -eq 0 ]]; then
    overall="COMPLETED"
else
    overall="FAILED ($FAILED of ${#NAMES[@]} steps)"
fi

groups=()
[[ $RUN_SINGLE -eq 1 ]] && groups+=(single)
[[ $RUN_BATCH -eq 1 ]] && groups+=(batch)
layers=()
[[ $RUN_RUST -eq 1 ]] && layers+=(rust)
[[ $RUN_PYTHON -eq 1 ]] && layers+=(python)

if [[ $QUICK -eq 1 ]]; then
    quick_note="QUICK (shorter runs; do not compare with full runs)"
else
    quick_note="full"
fi

{
    echo "PyTA benchmarks"
    echo "==============="
    echo "Result:   $overall"
    echo "Started:  $STARTED_AT"
    echo "Finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Duration: ${SECONDS}s"
    echo
    echo "Options"
    echo "-------"
    echo "Command:   scripts/benchmark.sh $ORIGINAL_ARGS"
    echo "Groups:    ${groups[*]}"
    echo "Layers:    ${layers[*]}"
    echo "Indicator: ${INDICATOR:-all}"
    echo "Mode:      $quick_note"
    echo
    echo "Environment"
    echo "-----------"
    echo "Commit:   $git_commit on $git_branch ($git_state)"
    echo "Rust:     $(rustc --version 2>/dev/null)"
    echo "Python:   $(uv run python --version 2>/dev/null)"
    echo "OS:       $(uname -sr)"
    echo "CPU:      ${cpu_model:-unknown} ($(nproc 2>/dev/null || echo '?') threads)"
    echo "Governor: $governor"
    echo
    echo "Steps"
    echo "-----"
    for i in "${!NAMES[@]}"; do
        printf '%-4s %-42s %-6s %6ss\n' "$((i + 1))." "${NAMES[$i]}" "${STATUSES[$i]}" "${SECONDS_TAKEN[$i]}"
    done

    if [[ $SUMMARY_IDX -ge 0 ]]; then
        echo
        echo "Summary: Criterion"
        echo "------------------"
        cat "$(log_of "$SUMMARY_IDX")"
    fi

    if [[ $PY_SINGLE_IDX -ge 0 ]]; then
        echo
        echo "Summary: Python single calls"
        echo "----------------------------"
        cat "$(log_of "$PY_SINGLE_IDX")"
    fi

    if [[ $PY_BATCH_IDX -ge 0 ]]; then
        echo
        echo "Summary: Python batch"
        echo "---------------------"
        cat "$(log_of "$PY_BATCH_IDX")"
    fi

    echo
    echo
    echo "FULL RESULTS"
    echo "============"
    for i in "${!NAMES[@]}"; do
        echo
        echo "----------------------------------------------------------------------"
        echo "$((i + 1)). ${NAMES[$i]}  [${STATUSES[$i]}, ${SECONDS_TAKEN[$i]}s]"
        echo "----------------------------------------------------------------------"
        cat "$(log_of "$i")"
    done
} > "$REPORT"

echo "==> Benchmarks $overall in ${SECONDS}s"
echo "==> Report: ${REPORT#"$PROJECT_ROOT"/}"

[[ $FAILED -eq 0 ]]
