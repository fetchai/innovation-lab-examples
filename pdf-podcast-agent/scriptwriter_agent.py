"""
Agent 2 – The Scriptwriter
==========================
Run in its own terminal:

    python scriptwriter_agent.py

Receives the distilled ResearchInsights and uses a carefully engineered
prompt to generate a lively, two-host debate script.

By separating this from extraction we prevent the LLM from losing hard
metrics while trying to be creative at the same time.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from uagents import Agent, Context

from schemas import DialogueLine, PodcastScript, ResearchInsights

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

SCRIPTWRITER_MODEL = os.getenv("SCRIPTWRITER_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = """\
You are the head writer for a popular tech podcast called "Debug Mode".
Your job is to turn dry research facts into a gripping, natural-sounding
debate between two hosts:

  • HostA – The Skeptic. Pushes back, asks "but how?", demands proof.
  • HostB – The Expert. Defends the work with specific numbers and insight.

Given the research insights below, write a 10–14 line back-and-forth script.

Rules:
1. Make it sound HUMAN. Use natural speech: "Wait, really?", "Right, but—",
   "Okay hold on…", "That's the thing though,", "Exactly!"
2. HostB must cite at least 3 of the provided key_metrics by exact value.
3. The controversial_point must be debated directly.
4. Each line should be 1–3 sentences — podcast pacing, not a lecture.
5. End on an unresolved tension or a provocative open question.
6. Do NOT add stage directions, music cues, or section headers.
7. Return ONLY valid JSON — no markdown, no extra prose:

{
  "topic_title": "<catchy 5-8 word title for this episode>",
  "lines": [
    {"speaker": "HostA", "text": "…"},
    {"speaker": "HostB", "text": "…"}
  ]
}
"""

# ── Agent ─────────────────────────────────────────────────────────────────────

scriptwriter = Agent(
    name="podcast_scriptwriter",
    seed=os.getenv("SCRIPTWRITER_SEED", "podcast_scriptwriter_seed_v1"),
    port=8002,
    endpoint=["http://localhost:8002/submit"],
    network="testnet",
)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── Handlers ──────────────────────────────────────────────────────────────────


@scriptwriter.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info("[Scriptwriter] ready")
    ctx.logger.info(f"[Scriptwriter] address: {ctx.agent.address}")


@scriptwriter.on_message(model=ResearchInsights)
async def handle_script(ctx: Context, sender: str, msg: ResearchInsights) -> None:
    sid = msg.session_id[:8]
    ctx.logger.info(f"[{sid}] Scripting — thesis: {msg.core_thesis[:60]}…")

    user_content = (
        f"Core thesis:\n{msg.core_thesis}\n\n"
        f"Key metrics:\n" + "\n".join(f"  • {m}" for m in msg.key_metrics) + "\n\n"
        f"Most controversial point:\n{msg.controversial_point}"
    )

    try:
        resp = await client.chat.completions.create(
            model=SCRIPTWRITER_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.75,
            max_tokens=2_000,
        )

        raw = resp.choices[0].message.content
        data = json.loads(raw)

        lines = [
            DialogueLine(speaker=line["speaker"], text=line["text"])
            for line in data.get("lines", [])
        ]

        if not lines:
            raise ValueError("LLM returned empty lines array.")

        script = PodcastScript(
            lines=lines,
            topic_title=data.get("topic_title", "Tech Debate"),
            session_id=msg.session_id,
        )

        ctx.logger.info(
            f"[{sid}] Script done — {len(lines)} lines • '{script.topic_title}'"
        )
        await ctx.send(sender, script)

    except Exception as exc:
        ctx.logger.error(f"[{sid}] Error: {exc}")
        fallback = PodcastScript(
            lines=[
                DialogueLine(
                    speaker="HostA",
                    text=f"Today we're discussing: {msg.core_thesis[:120]}",
                ),
                DialogueLine(
                    speaker="HostB",
                    text=f"The key finding: {msg.controversial_point[:120]}",
                ),
            ],
            topic_title="Research Breakdown",
            session_id=msg.session_id,
        )
        await ctx.send(sender, fallback)


if __name__ == "__main__":
    scriptwriter.run()
