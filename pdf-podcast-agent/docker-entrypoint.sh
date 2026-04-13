#!/usr/bin/env sh
set -e

if [ -z "${EXTRACTOR_ADDRESS:-}" ] || [ -z "${SCRIPTWRITER_ADDRESS:-}" ] || [ -z "${VOICE_STUDIO_ADDRESS:-}" ] || [ -z "${HOST_A_ADDRESS:-}" ] || [ -z "${HOST_B_ADDRESS:-}" ]; then
  echo "[entrypoint] Resolving deterministic agent addresses from seeds..."
  python /app/docker_bootstrap_addresses.py > /tmp/agent-addresses.env
  set -a
  . /tmp/agent-addresses.env
  set +a
fi

exec "$@"
