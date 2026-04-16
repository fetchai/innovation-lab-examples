#!/bin/bash
# Read the response from the last fire.sh call.
# Polls until the response marker appears (up to 90 seconds).
OUTFILE="/tmp/fetch-agents-$(whoami)-response.txt"
if [ ! -f "$OUTFILE" ]; then
    echo "No pending request. Run fire.sh first."
    exit 1
fi
WAITED=0
while ! grep -q "RESPONSE_START" "$OUTFILE" 2>/dev/null && [ $WAITED -lt 90 ]; do
    sleep 5
    WAITED=$((WAITED + 5))
done
if ! grep -q "RESPONSE_START" "$OUTFILE" 2>/dev/null; then
    echo "Timeout: no response after ${WAITED}s."
    exit 1
fi
# Extract everything after the marker
sed -n '/---RESPONSE_START---/,$ p' "$OUTFILE" | tail -n +2
