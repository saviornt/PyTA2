#!/usr/bin/env bash
# Build PyTA's release wheel, (re)create PyTA-Integration/.venv with it, then run every example,
# the integration tests and ruff. Works from a deleted .venv and dist/.
#
# Usage: PyTA-Integration/scripts/setup.sh [--bench] [--no-build] [--no-run]
#   --bench     also install the `bench` extra (TA-Lib 0.8.3, for the comparison benchmarks)
#   --no-build  reuse the wheel already in dist/ instead of rebuilding it
#   --no-run    install only; skip the examples, tests and ruff
set -euo pipefail

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; }

bench=0
build=1
run=1
for arg in "$@"; do
    case "$arg" in
        --bench) bench=1 ;;
        --no-build) build=0 ;;
        --no-run) run=0 ;;
        -h | --help) usage; exit 0 ;;
        *) echo "unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo="$(cd "$project/.." && pwd)"
dist="$project/dist"
venv="$project/.venv"
python="$venv/bin/python"

# An activated environment (PyTA's own .venv, say) must not leak into this one.
unset VIRTUAL_ENV CONDA_PREFIX PYTHONPATH

step() { printf '\n==> %s\n' "$*"; }

if (( build )); then
    step "Building the PyTA release wheel into dist/"
    rm -rf "$dist"
    # Built from PyTA's root pyproject.toml, so maturin packages the Python sources
    # (python-source = "python") with the extension module.
    uv run --directory "$repo" maturin build --release --out "$dist"
fi

shopt -s nullglob
wheels=("$dist"/pyta-*.whl)
shopt -u nullglob
if (( ${#wheels[@]} != 1 )); then
    echo "expected exactly one pyta wheel in $dist, found ${#wheels[@]}" >&2
    exit 1
fi
wheel="${wheels[0]}"

step "Creating $venv (Python 3.15)"
uv venv --clear --python 3.15 "$venv"

step "Installing $(basename "$wheel") and the project's dependencies"
extras=()
if (( bench )); then
    extras=(--extra bench)
fi
# The wheel is named on the command line, so it satisfies the `pyta` requirement; the source tree
# is never installed or put on the path.
(cd "$project" && uv pip install --python "$python" "$wheel" \
    -r pyproject.toml "${extras[@]}" --group dev)

if (( ! run )); then
    exit 0
fi

cd "$project"

for example in examples/*.py; do
    step "Running $example"
    "$python" "$example"
done

step "Running the integration tests"
"$python" -m pytest

step "Running ruff"
"$venv/bin/ruff" check .
"$venv/bin/ruff" format --check .

step "Done"
