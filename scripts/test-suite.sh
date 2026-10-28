#!/usr/bin/env bash
# Runs every PyTA check and writes a timestamped report to tests/results/.
#
# The report has a summary at the top and the full output of every step
# below it. Rust formatting is fixed first (like CI), then checked.
# Every step runs even if an earlier one fails; the exit status is
# non-zero if any step failed.
set -uo pipefail

# Resolve the project root from this script's location.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Plain text only, so the report is readable in any editor.
export NO_COLOR=1 CARGO_TERM_COLOR=never

STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
RESULTS_DIR="$PROJECT_ROOT/tests/results"
REPORT="$RESULTS_DIR/test-suite_${STAMP}.txt"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$RESULTS_DIR"

NAMES=()
STATUSES=()
SECONDS_TAKEN=()
FAILED=0
STEP_NOTE="$WORK/note"

# run_step <name> <command...>: runs a step, echoes its output live, and
# records its status, duration, and output for the report.
run_step() {
    local name=$1
    shift
    local index=${#NAMES[@]}
    local log="$WORK/step_${index}.log"
    local start=$SECONDS

    : > "$STEP_NOTE"
    echo "==> $name"
    "$@" 2>&1 | tee "$log"
    local status=${PIPESTATUS[0]}
    echo

    NAMES+=("$name")
    SECONDS_TAKEN+=($((SECONDS - start)))

    if [[ $status -ne 0 ]]; then
        STATUSES+=("FAIL")
        FAILED=$((FAILED + 1))
    elif [[ -s "$STEP_NOTE" ]]; then
        STATUSES+=("PASS ($(cat "$STEP_NOTE"))")
    else
        STATUSES+=("PASS")
    fi
}

# Fixes Rust formatting in place, as CI does, and notes what it changed.
fix_rust_formatting() {
    local changed
    changed=$(cargo fmt --all -- --check 2>&1 | grep -c '^Diff in' || true)

    if [[ $changed -eq 0 ]]; then
        echo "Formatting already clean."
        return 0
    fi

    cargo fmt --all || return 1
    echo "Fixed formatting in $changed place(s)."
    echo "fixed $changed place(s)" > "$STEP_NOTE"
}

run_step "Rust formatting (cargo fmt --all)" fix_rust_formatting
run_step "Rust formatting check" cargo fmt --all -- --check
run_step "Clippy" cargo clippy --workspace --all-targets --all-features -- -D warnings
run_step "Rust tests" cargo test --workspace
run_step "Build Python extension" \
    uv run --with maturin maturin develop --manifest-path rust/crates/pyta-python/Cargo.toml
run_step "Smoke test" uv run python tests/smoke/test_smoke.py
run_step "Python tests (pytest)" uv run --extra pandas pytest --color=no
run_step "Ruff lint" uv run ruff check python tests
run_step "Ruff format check" uv run ruff format --check python tests

# ---- Report -----------------------------------------------------------

log_of() { echo "$WORK/step_$1.log"; }

# Sums "N passed" over every `test result:` line cargo prints.
rust_test_counts() {
    local log=$1
    awk '/^test result:/ {
        for (i = 1; i <= NF; i++) {
            if ($i == "passed;") passed += $(i - 1)
            if ($i == "failed;") failed += $(i - 1)
            if ($i == "ignored;") ignored += $(i - 1)
        }
    } END { printf "%d passed, %d failed, %d ignored", passed, failed, ignored }' "$log"
}

pytest_counts() {
    grep -E '^=*.*[0-9]+ (passed|failed|error)' "$1" | tail -n 1 | sed -E 's/^=+ *//; s/ *=+$//'
}

git_commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    git_state="uncommitted changes"
else
    git_state="clean"
fi

if [[ $FAILED -eq 0 ]]; then
    overall="PASSED"
else
    overall="FAILED ($FAILED of ${#NAMES[@]} steps)"
fi

{
    echo "PyTA test suite"
    echo "==============="
    echo "Result:   $overall"
    echo "Started:  $STARTED_AT"
    echo "Finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Duration: ${SECONDS}s"
    echo
    echo "Environment"
    echo "-----------"
    echo "Commit:  $git_commit on $git_branch ($git_state)"
    echo "Rust:    $(rustc --version 2>/dev/null)"
    echo "Python:  $(uv run python --version 2>/dev/null)"
    echo "OS:      $(uname -sr)"
    echo
    echo "Steps"
    echo "-----"
    for i in "${!NAMES[@]}"; do
        printf '%-4s %-38s %-24s %5ss\n' "$((i + 1))." "${NAMES[$i]}" "${STATUSES[$i]}" "${SECONDS_TAKEN[$i]}"
    done
    echo
    echo "Test counts"
    echo "-----------"
    echo "Rust:   $(rust_test_counts "$(log_of 3)")"
    echo "Python: $(pytest_counts "$(log_of 6)")"
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

echo "==> Test suite $overall in ${SECONDS}s"
echo "==> Report: ${REPORT#"$PROJECT_ROOT"/}"

[[ $FAILED -eq 0 ]]
