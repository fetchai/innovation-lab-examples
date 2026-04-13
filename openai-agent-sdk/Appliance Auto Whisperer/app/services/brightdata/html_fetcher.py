from __future__ import annotations

import httpx


async def fetch_html(url: str, timeout_s: float = 20.0) -> str:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(
            url, headers={"User-Agent": "appliance-auto-whisperer/0.2"}
        )
        r.raise_for_status()
        return r.text
