#!/usr/bin/env python3
"""Search the Agentverse marketplace for agents."""

import json
import sys
import urllib.request


def usage():
    print('Usage: search.py "query" [-n 10]', file=sys.stderr)
    sys.exit(2)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        usage()

    query = args[0]
    limit = 10

    i = 1
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            print(f"Unknown arg: {args[i]}", file=sys.stderr)
            usage()

    body = json.dumps(
        {
            "search_text": query,
            "sort": "relevancy",
            "direction": "desc",
            "filters": {"state": ["active"]},
            "offset": 0,
            "limit": max(1, min(limit, 50)),
        }
    ).encode()

    req = urllib.request.Request(
        "https://agentverse.ai/v1/search/agents",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "OpenClaw-FetchAgents/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"Search failed: {e}", file=sys.stderr)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    agents = data.get("agents", [])
    results = []
    for a in agents:
        results.append(
            {
                "name": a.get("name", ""),
                "address": a.get("address", ""),
                "description": (a.get("description") or "")[:300],
                "interactions": a.get("total_interactions", 0),
                "status": a.get("status", ""),
            }
        )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
