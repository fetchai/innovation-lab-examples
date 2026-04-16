#!/bin/bash
# Wrapper that suppresses noisy uagents logs and only outputs the response.
# Usage: ask.sh <shortcut|address|name> "query"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/call.py" "$@" 2>/dev/null
