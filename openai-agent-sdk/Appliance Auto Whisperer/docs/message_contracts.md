# Message contracts

## `POST /v1/chat` (request)

| Field | Type | Notes |
|-------|------|--------|
| `session_id` | string | Optional; server assigns if empty |
| `appliance_type` | string | e.g. `"dishwasher"` |
| `symptoms` | string | Free text; may duplicate `message` |
| `message` | string | Optional user message |
| `image_base64` | string | Optional raw base64 or data URL |

## Response

| Field | Type | Notes |
|-------|------|--------|
| `session_id` | string | Session id |
| `markdown` | string | Rendered answer |
| `structured` | object | `diagnosis`, `sourcing`, `tutorials`, `synthesis` |

See `examples/` for samples.
