#!/usr/bin/env bash
set -euo pipefail
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill in secrets."
else
  echo ".env already exists; not overwriting."
fi
