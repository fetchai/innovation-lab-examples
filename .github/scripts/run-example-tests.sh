#!/usr/bin/env bash
#
# Run every example test suite in the repository.
#
# Each example is an independent project with its own (often conflicting)
# dependencies, so a single `pytest` from the repository root cannot work — it
# fails at collection because no one set of packages satisfies all examples.
# Instead, every example that ships a `tests/` directory gets its own
# virtualenv built from that example's `requirements.txt`.
#
# Usage:
#   bash .github/scripts/run-example-tests.sh [example-dir ...]
#
# With no arguments every discovered suite runs. The script exits non-zero if
# any suite fails, and prints a summary of all suites at the end.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

PYTHON_BIN="${PYTHON_BIN:-python3}"

# Placeholder credentials. Some examples build their SDK client at import time
# and refuse to import without a key, which would turn a unit-test run into a
# collection error. No test may make a real network call with these.
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-placeholder-key}"
export ASI_ONE_API_KEY="${ASI_ONE_API_KEY:-test-placeholder-key}"
export ASI1_API_KEY="${ASI1_API_KEY:-test-placeholder-key}"

discover_suites() {
    find . -type d -name tests \
        -not -path "./.git/*" \
        -not -path "*/node_modules/*" \
        -not -path "*/.venv/*" \
        -not -path "*/venv/*" \
        -not -path "*/site-packages/*" \
        -print \
    | sed 's|/tests$||' \
    | sed 's|^\./||' \
    | sort -u
}

SUITES=()
if [ "$#" -gt 0 ]; then
    SUITES=("$@")
else
    # Not `mapfile`: macOS still ships bash 3.2, so maintainers can run this too.
    while IFS= read -r line; do
        [ -n "$line" ] && SUITES+=("$line")
    done < <(discover_suites)
fi

if [ "${#SUITES[@]}" -eq 0 ]; then
    echo "No example test suites found."
    exit 0
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

declare -a RESULTS=()
OVERALL=0

for suite in "${SUITES[@]}"; do
    echo ""
    echo "=============================================================="
    echo "Test suite: $suite"
    echo "=============================================================="

    if [ ! -d "$suite/tests" ]; then
        echo "  no tests/ directory — skipping"
        RESULTS+=("SKIP (no tests/)  $suite")
        continue
    fi

    if [ ! -f "$suite/requirements.txt" ]; then
        echo "  no requirements.txt — cannot build an environment for this suite"
        RESULTS+=("FAIL (no requirements.txt)  $suite")
        OVERALL=1
        continue
    fi

    venv="$WORKDIR/venv_$(echo "$suite" | tr '/ ' '__')"
    if ! "$PYTHON_BIN" -m venv "$venv"; then
        echo "  could not create virtualenv"
        RESULTS+=("FAIL (venv)  $suite")
        OVERALL=1
        continue
    fi

    "$venv/bin/pip" install --quiet --upgrade pip

    if ! "$venv/bin/pip" install --quiet -r "$suite/requirements.txt"; then
        echo "  dependency installation failed"
        RESULTS+=("FAIL (pip install)  $suite")
        OVERALL=1
        continue
    fi

    # pytest itself is a test-time tool; not every example lists it.
    "$venv/bin/pip" install --quiet pytest pytest-asyncio

    if ( cd "$suite" && "$venv/bin/python" -m pytest -q ); then
        RESULTS+=("PASS  $suite")
    else
        RESULTS+=("FAIL (tests)  $suite")
        OVERALL=1
    fi
done

echo ""
echo "=============================================================="
echo "Summary"
echo "=============================================================="
for line in "${RESULTS[@]}"; do
    echo "  $line"
done

if [ "$OVERALL" -ne 0 ]; then
    echo ""
    echo "One or more example test suites failed."
fi

exit "$OVERALL"
