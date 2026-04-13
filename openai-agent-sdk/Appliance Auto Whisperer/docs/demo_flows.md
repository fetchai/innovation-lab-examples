# Demo flows

1. **Text-only** — Send `symptoms` + `appliance_type`; receive markdown + structured JSON.
2. **With image** — Add `image_base64` (JPEG); diagnosis client attaches a vision message when `OPENAI_API_KEY` is set.
3. **Session** — Omit `session_id` on first call; reuse returned `session_id` on follow-ups (state hooks in `app/storage/`).

Example payloads live under `examples/`.
