#!/bin/bash
set -euo pipefail

# This script is Bash-specific and must be run with Bash.

echo "🚀 Setting up devcontainer..."

# Determine workspace root dynamically and mark it safe for git operations
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  WORKSPACE_ROOT=$(git rev-parse --show-toplevel)
else
  WORKSPACE_ROOT="$PWD"
fi

git config --global --add safe.directory "$WORKSPACE_ROOT" || true

# Simple retry wrapper for transient network/install failures
retry() {
  local -r max_attempts=3
  local -r cmd=("$@")
  local attempt=1
  until "${cmd[@]}"; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Command failed after $attempt attempts: ${cmd[*]}" >&2
      return 1
    fi
    echo "Command failed, retrying (${attempt}/${max_attempts})..."
    attempt=$((attempt + 1))
    sleep $((attempt * 2))
  done
}

# Validate required tools: node and npm
if ! command -v node >/dev/null 2>&1; then
  echo "node is required but not found in PATH. Please install Node.js." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required but not found in PATH. Please install Node.js and npm." >&2
  exit 1
fi

# Install Azle CLI (idempotent)
echo "🔗 Installing Azle CLI..."
retry npm install -g azle@latest || echo "Warning: azle installation failed, continuing..."

# Install npm dependencies in the 'ic' subfolder if it exists
if [ -d "ic" ]; then
  echo "📦 Installing npm dependencies in ic/..."
  pushd ic >/dev/null
  retry npm install || echo "Warning: npm install in ic failed"
  popd >/dev/null
else
  echo "No 'ic' directory found; skipping npm install step"
fi

# Optionally set up dfx identity if dfx is available
if command -v dfx >/dev/null 2>&1; then
  echo "🔑 Setting up dfx identity..."
  dfx identity new codespace_dev --storage-mode=plaintext || echo "Identity may already exist"
  dfx identity use codespace_dev || true
  dfx start --background || echo "Warning: dfx start failed"
  dfx stop || true
else
  echo "dfx not found; skipping dfx identity steps"
fi

echo "✅ Devcontainer setup complete!"