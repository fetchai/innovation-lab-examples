# Sample API response (`POST /v1/chat`)

```json
{
  "session_id": "…",
  "markdown": "## Summary\n…",
  "structured": {
    "diagnosis": {},
    "sourcing": {},
    "tutorials": { "videos": [] },
    "synthesis": {}
  }
}
```

The `markdown` field is the primary user-facing answer; `structured` is for UI or downstream agents.
