"""
Agent 1 – The RAG Extractor
===========================
Run in its own terminal:

    python extractor_agent.py

Receives raw document text from the Orchestrator, fires a single structured
OpenAI call with JSON mode, and returns a tight ResearchInsights payload.

This agent deliberately drops the 40-page document after extracting three
facts so that downstream agents never have to handle large payloads.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from uagents import Agent, Context

from schemas import ExtractRequest, ResearchInsights

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = """\
You are an elite technical researcher. Read the provided document carefully.
Extract exactly three things and return ONLY valid JSON:

{
  "core_thesis": "<2-3 sentences – the central argument or finding>",
  "key_metrics": [
    "<exact stat or number from the text>",
    "<exact stat or number from the text>",
    "<exact stat or number from the text>",
    "<exact stat or number from the text>"
  ],
  "controversial_point": "<the most surprising, counterintuitive, or debatable claim>"
}

Rules:
- Be SPECIFIC. Use exact numbers, percentages, or quotes from the text.
- Never be generic ("the paper discusses …"). Pull the hard facts.
- key_metrics must contain 3–6 items.
- Return ONLY the JSON object – no markdown fences, no extra prose.
"""

# ── Agent ─────────────────────────────────────────────────────────────────────

extractor = Agent(
    name="rag_extractor",
    seed=os.getenv("EXTRACTOR_SEED", "rag_extractor_podcast_seed_v1"),
    port=8001,
    endpoint=["http://localhost:8001/submit"],
    network="testnet",
)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── Handlers ──────────────────────────────────────────────────────────────────


@extractor.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info("[RAG Extractor] ready")
    ctx.logger.info(f"[RAG Extractor] address: {ctx.agent.address}")


@extractor.on_message(model=ExtractRequest)
async def handle_extract(ctx: Context, sender: str, msg: ExtractRequest) -> None:
    sid = msg.session_id[:8]
    ctx.logger.info(f"[{sid}] Extracting from {len(msg.document_text):,} chars …")

    try:
        text = msg.document_text[:50_000]

        resp = await client.chat.completions.create(
            model=EXTRACTION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Document:\n\n{text}"},
            ],
            temperature=0.2,
            max_tokens=1_200,
        )

        raw = resp.choices[0].message.content
        data = json.loads(raw)

        insights = ResearchInsights(
            core_thesis=data.get("core_thesis", "Could not extract thesis."),
            key_metrics=data.get("key_metrics", []),
            controversial_point=data.get("controversial_point", ""),
            session_id=msg.session_id,
        )

        ctx.logger.info(f"[{sid}] Done — {insights.core_thesis[:70]}…")
        await ctx.send(sender, insights)

    except Exception as exc:
        ctx.logger.error(f"[{sid}] Error: {exc}")
        await ctx.send(
            sender,
            ResearchInsights(
                core_thesis=f"Extraction failed: {str(exc)[:200]}",
                key_metrics=["Error – check logs"],
                controversial_point="Unable to extract insights.",
                session_id=msg.session_id,
            ),
        )


if __name__ == "__main__":
    extractor.run()
