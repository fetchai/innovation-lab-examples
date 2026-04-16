#!/bin/bash
# Fire-and-forget: starts call.py in background, returns immediately.
# Usage: fire.sh <shortcut|address|name> "query" [--timeout N]
# Output goes to /tmp/fetch-agents-<user>-response.txt
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTFILE="/tmp/fetch-agents-$(whoami)-response.txt"
echo "PENDING" > "$OUTFILE"
nohup python3 "$SCRIPT_DIR/call.py" "$@" > "$OUTFILE" 2>/dev/null &
disown
echo "Agent call started. Poll with result.sh in ~40 seconds."
