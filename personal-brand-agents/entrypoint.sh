#!/bin/bash
set -e

# Start local chroma server in the background
chroma run --path ./chroma &

# Start the wrapped agent
python -m wrapped_uagents.wrapped_data_management_agent
