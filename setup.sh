#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<EOF
Usage: ./setup.sh <example-folder> [--run]

Sets up a Fetch.ai Innovation Lab example for local development.

Arguments:
  <example-folder>   Name of the example folder (e.g. fetch-hackathon-quickstarter)
  --run              Automatically run the agent after setup (optional)

Examples:
  ./setup.sh fetch-hackathon-quickstarter
  ./setup.sh gemini-quickstart/01-basic-gemini-agent --run
  ./setup.sh fet-example

What this script does:
  1. Validates the example folder exists
  2. Creates a Python virtual environment (.venv)
  3. Installs dependencies from requirements.txt
  4. Copies .env.example to .env (if present and .env doesn't exist)
  5. Prints instructions to run the agent

EOF
    exit 1
}

if [[ $# -lt 1 ]]; then
    echo "Error: No example folder specified."
    echo ""
    usage
fi

EXAMPLE="$1"
AUTO_RUN="${2:-}"
EXAMPLE_DIR="$REPO_ROOT/$EXAMPLE"

if [[ ! -d "$EXAMPLE_DIR" ]]; then
    echo "Error: Example folder '$EXAMPLE' not found."
    echo ""
    echo "Available examples:"
    for dir in "$REPO_ROOT"/*/; do
        dirname="$(basename "$dir")"
        [[ "$dirname" == .* || "$dirname" == docs || "$dirname" == .github ]] && continue
        if [[ -f "$dir/requirements.txt" ]] || [[ -f "$dir/agent.py" ]] || [[ -f "$dir/main.py" ]]; then
            echo "  $dirname"
        fi
    done
    exit 1
fi

echo "=== Fetch.ai Innovation Lab Setup ==="
echo "Example: $EXAMPLE"
echo ""

cd "$EXAMPLE_DIR"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo "Error: Python 3.10+ is required but not found."
    echo "Install Python from https://www.python.org/downloads/"
    exit 1
fi

echo "[1/4] Using $($PYTHON_CMD --version)"

if [[ ! -d ".venv" ]]; then
    echo "[2/4] Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
else
    echo "[2/4] Virtual environment already exists."
fi

VENV_ACTIVATE=""
if [[ -f ".venv/bin/activate" ]]; then
    VENV_ACTIVATE=".venv/bin/activate"
elif [[ -f ".venv/Scripts/activate" ]]; then
    VENV_ACTIVATE=".venv/Scripts/activate"
else
    echo "Error: Could not find a virtual environment activation script."
    echo "Expected .venv/bin/activate or .venv/Scripts/activate."
    exit 1
fi

source "$VENV_ACTIVATE"

if [[ -f "requirements.txt" ]]; then
    echo "[3/4] Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
else
    echo "[3/4] No requirements.txt found — skipping dependency install."
fi

if [[ -f ".env.example" ]] && [[ ! -f ".env" ]]; then
    cp .env.example .env
    echo "[4/4] Created .env from .env.example — edit it with your API keys."
elif [[ -f ".env" ]]; then
    echo "[4/4] .env already exists — skipping."
else
    echo "[4/4] No .env.example found — no environment variables needed."
fi

ENTRY_FILE=""
for candidate in agent.py main.py workflow.py app.py; do
    if [[ -f "$candidate" ]]; then
        ENTRY_FILE="$candidate"
        break
    fi
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate the environment:"
echo "  cd $EXAMPLE && source $VENV_ACTIVATE"
echo ""

if [[ -n "$ENTRY_FILE" ]]; then
    if [[ "$AUTO_RUN" == "--run" ]]; then
        echo "Starting agent..."
        $PYTHON_CMD "$ENTRY_FILE"
    else
        echo "To run the agent:"
        echo "  python $ENTRY_FILE"
    fi
else
    echo "Check the example's README.md for run instructions."
fi
