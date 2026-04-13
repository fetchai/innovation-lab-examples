"""Quick smoke: GET /health on localhost:8000 (server must be running)."""

from __future__ import annotations

import json
import sys

import httpx


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/health"
    try:
        r = httpx.get(url, timeout=5.0)
        print(json.dumps({"status_code": r.status_code, "body": r.json()}, indent=2))
        raise SystemExit(0 if r.status_code == 200 else 1)
    except Exception as e:  # noqa: BLE001
        print(f"Smoke test failed: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
