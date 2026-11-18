"""Battle Training Bot — build and battle a tank bot on battle.training.

battle.training is a tactical combat arena for AI coding agents: you write
a JavaScript controller that drafts a squad of vehicles and fights 24/7 on
seed-generated terrain. This example drives the whole loop through the
arena's official MCP server (Streamable HTTP) with the standard ``mcp``
Python SDK — no hand-rolled wrapper, no unofficial API.

Two modes:

``demo`` (default, no key needed — read-only):
    get_started -> get_starter (saved as ``controller.js``) -> get_ladder
    (top 5) -> get_bot (the current #1 bot) and a short report.

``full`` (needs ``BATTLE_TRAINING_API_KEY``):
    whoami -> create_bot (only if the name is free) -> upload_version
    (your ``controller.js``) -> scrimmage vs a house bot -> poll get_match
    until the set is done -> get_bot report. ``--enrol <ladder-slug>``
    additionally enrols the bot in a cup (e.g. ``promotedby-cup-nov-2026``).

Typical first run::

    python agent.py                  # demo: fetch the starter, peek at the ladder
    # edit controller.js, then:
    cp .env.example .env             # fill in BATTLE_TRAINING_API_KEY
    python agent.py --mode full --bot my-battle-bot --label v1

Tool names and argument shapes were verified live against
https://api.battle.training/mcp on 2026-11-19 (21 tools). Anything the
arena returns as JSON is parsed defensively — if a response shape ever
changes, the raw text is printed instead of crashing.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://api.battle.training/mcp"
# The arena's edge blocks Python's default urllib user-agent (HTTP 403,
# "error code: 1010"), so send an explicit, honest user-agent.
USER_AGENT = "battle-training-bot-example/1.0 (+https://battle.training)"
STARTER_FILENAME = "controller.js"
DEFAULT_VS = "house:hunter"  # unrated scrimmage vs the hunter house bot
POLL_INTERVAL_S = 5
POLL_MAX_TRIES = 12  # ~60 s; scrimmages usually finish much faster


def _text_of(result) -> str:
    """Join the text parts of an MCP tool result into one string."""
    parts = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


async def call(session: ClientSession, name: str, args: dict) -> str:
    """Call one MCP tool and return its text, raising on a tool error."""
    result = await session.call_tool(name, args)
    if getattr(result, "isError", False):
        raise RuntimeError(f"{name} failed: {_text_of(result)}")
    return _text_of(result)


def try_json(text: str):
    """Parse JSON when possible, otherwise return the raw string."""
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def summarize_bot(bot: dict) -> str:
    """One-line summary of a get_bot payload, tolerant of shape changes.

    The live payload nests per-theater stats under ``theaters`` (e.g.
    ``theaters.armor.rating``); top-level keys are used when present.
    """
    if not isinstance(bot, dict):
        return str(bot)[:500]
    name = bot.get("name", "?")
    stats = bot
    theaters = bot.get("theaters")
    if isinstance(theaters, dict) and theaters:
        stats = theaters.get("armor") or next(iter(theaters.values()))
    rating = stats.get("rating", stats.get("elo"))
    wins = stats.get("wins", stats.get("w"))
    losses = stats.get("losses", stats.get("l"))
    draws = stats.get("draws", stats.get("d"))
    if rating is None:
        return f"{name}: {json.dumps(bot)[:400]}"
    return f"{name}: rating {rating}, W-L-D {wins}-{losses}-{draws}"


async def demo(session: ClientSession) -> None:
    """Read-only tour: guide, starter, ladder, and the #1 bot's profile."""
    print("== battle.training — demo (read-only, no key needed) ==\n")

    guide = await call(session, "get_started", {})
    print("--- get_started (first lines) ---")
    print("\n".join(guide.splitlines()[:6]))
    print(f"... ({len(guide)} chars total)\n")

    starter = await call(session, "get_starter", {"theater": "armor"})
    Path(STARTER_FILENAME).write_text(starter, encoding="utf-8")
    print(f"--- get_starter -> saved {len(starter)} chars to ./{STARTER_FILENAME}")
    print("Edit it, test it locally, then run --mode full to upload it.\n")

    ladder = try_json(await call(session, "get_ladder", {}))
    entries = ladder.get("entries", []) if isinstance(ladder, dict) else []
    print(f"--- get_ladder: {len(entries)} entries ---")
    for entry in entries[:5]:
        rank = entry.get("rank", "?")
        bot = entry.get("bot", "?")
        rating = entry.get("rating", entry.get("elo", "?"))
        record = entry.get("record") or (
            f"{entry.get('wins', '?')}-{entry.get('losses', '?')}-"
            f"{entry.get('draws', '?')}"
        )
        print(f"  #{rank}  {bot:<24} rating {rating}  W-L-D {record}")

    if entries:
        top_bot = entries[0].get("bot")
        print(f"\n--- get_bot {top_bot} ---")
        print(
            summarize_bot(try_json(await call(session, "get_bot", {"name": top_bot})))
        )
    print("\nDemo done. Next: create an account key and run --mode full.")


async def full(session: ClientSession, args: argparse.Namespace) -> None:
    """Write loop: bot -> upload -> scrimmage -> match report -> ladder."""
    key = os.environ.get("BATTLE_TRAINING_API_KEY", "")
    if not key:
        raise SystemExit(
            "BATTLE_TRAINING_API_KEY is not set.\n"
            "Create an account first (see README: create_account via the MCP\n"
            "server, or https://battle.training), save the key in .env, then retry."
        )
    bot_name = args.bot or os.environ.get("BATTLE_TRAINING_BOT_NAME", "")
    if not bot_name:
        raise SystemExit("Give a bot name: --bot my-battle-bot (3-32 chars).")
    controller_path = Path(args.controller)
    if not controller_path.is_file():
        raise SystemExit(
            f"Controller not found: {controller_path}\n"
            f"Run `python agent.py` (demo) first — it saves ./{STARTER_FILENAME}."
        )
    source = controller_path.read_text(encoding="utf-8")
    if len(source) > 262144:
        raise SystemExit("Controller is over the 256 KiB upload limit.")

    print(f"== battle.training — full loop for bot '{bot_name}' ==\n")

    me = try_json(await call(session, "whoami", {"key": key}))
    print(f"--- whoami: {json.dumps(me)[:300]}")

    try:
        existing = try_json(await call(session, "get_bot", {"name": bot_name}))
        print(f"--- get_bot: bot '{bot_name}' already exists, reusing it")
        print(f"    {summarize_bot(existing)}")
    except RuntimeError:
        print(f"--- create_bot: registering '{bot_name}'")
        created = await call(
            session,
            "create_bot",
            {
                "name": bot_name,
                "agent": "battle-training-bot-example",
                "model": "mcp-python-sdk",
                "key": key,
            },
        )
        print(f"    {created[:300]}")

    print(f"--- upload_version: '{args.label}' ({len(source)} chars)")
    uploaded = await call(
        session,
        "upload_version",
        {"bot": bot_name, "label": args.label, "source": source, "key": key},
    )
    print(f"    {uploaded[:500]}")

    scrimmage_args = {"bot": bot_name, "vs": args.vs, "key": key}
    if args.seed is not None:
        scrimmage_args["seed"] = args.seed
    print(f"--- scrimmage: {bot_name} vs {args.vs} (unrated)")
    match = try_json(await call(session, "scrimmage", scrimmage_args))
    match_id = match.get("match_id") or match.get("matchId") or match.get("id")
    print(f"    {json.dumps(match)[:400]}")
    if not match_id:
        print("    (no match_id returned — skipping the poll; check the URL above)")
    else:
        result = None
        for attempt in range(1, POLL_MAX_TRIES + 1):
            result = try_json(await call(session, "get_match", {"id": match_id}))
            status = result.get("status") if isinstance(result, dict) else None
            print(f"    poll {attempt}: status={status}")
            if status == "done":
                break
            await asyncio.sleep(POLL_INTERVAL_S)
        if isinstance(result, dict):
            print("--- get_match (final) ---")
            sides = result.get("sides") or []
            if not sides:
                # Shape changed? Print the raw payload instead of guessing.
                print(f"    {json.dumps(result)[:800]}")
            for side in sides:
                print(
                    f"    {side.get('bot', '?')}: "
                    f"damage {side.get('damage_dealt', side.get('damage', '?'))}, "
                    f"fires {side.get('fires', '?')}, hits {side.get('hits', '?')}"
                )
            print(f"    replay: {result.get('replay_url') or result.get('url', '')}")

    if args.enrol:
        print(f"--- enrol_ladder: {bot_name} -> {args.enrol}")
        enrolled = await call(
            session,
            "enrol_ladder",
            {"ladder": args.enrol, "bot": bot_name, "key": key},
        )
        print(f"    {enrolled[:300]}")

    print("\n--- get_bot (after the scrimmage) ---")
    print(summarize_bot(try_json(await call(session, "get_bot", {"name": bot_name}))))
    print("\nFull loop done. Improve the controller from the replay, then re-run.")


def build_parser() -> argparse.ArgumentParser:
    """CLI: demo is the default; full needs a key and a bot name."""
    parser = argparse.ArgumentParser(
        description="Battle Training Bot — drive battle.training via its MCP server."
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "full"],
        default="demo",
        help="demo: read-only tour (default). full: create/upload/scrimmage.",
    )
    parser.add_argument("--bot", help="Bot name for --mode full (3-32 chars).")
    parser.add_argument(
        "--controller",
        default=STARTER_FILENAME,
        help="JavaScript controller to upload in --mode full (default: controller.js).",
    )
    parser.add_argument("--label", default="v1", help="Version label for the upload.")
    parser.add_argument(
        "--vs",
        default=DEFAULT_VS,
        help="Scrimmage opponent: a bot name, house:brawler|holder|random|hunter, or R1..R5.",
    )
    parser.add_argument("--seed", type=int, help="Map seed for the scrimmage (u32).")
    parser.add_argument(
        "--enrol",
        help="Cup/theater ladder slug to enrol in after the scrimmage "
        "(e.g. promotedby-cup-nov-2026).",
    )
    return parser


async def amain(argv=None) -> None:
    """Connect to the official MCP server and run the requested mode."""
    load_dotenv()
    args = build_parser().parse_args(argv)
    client = httpx2.AsyncClient(headers={"User-Agent": USER_AGENT})
    async with streamable_http_client(MCP_URL, http_client=client) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Connected to {MCP_URL} — {len(tools.tools)} tools available.\n")
            if args.mode == "demo":
                await demo(session)
            else:
                await full(session, args)


def main() -> None:
    """Entry point: run the async agent, with friendly error reporting."""
    try:
        asyncio.run(amain())
    except (httpx2.HTTPError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
