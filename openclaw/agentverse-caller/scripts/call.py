#!/usr/bin/env python3
"""Send a ChatMessage to a Fetch.ai Agentverse agent and wait for the response."""

import asyncio
import json
import os
import random
import signal
import sys
import urllib.request
from uuid import uuid4

# ── agent key → address lookup ──────────────────────────────────────

SHORTCUTS = {
    "search": "agent1qt5uffgp0l3h9mqed8zh8vy5vs374jl2f8y0mjjvqm44axqseejqzmzx9v8",
    "asi": "agent1qdhaqxdvjhtchfmra6ycwjt7p3dj7ucq2ccnx2ppk4pa5mde4kc0ghep43j",
    "image": "agent1q0utywlfr3dfrfkwk4fjmtdrfew0zh692untdlr877d6ay8ykwpewydmxtl",
    "stocks": "agent1q085746wlr3u2uh4fmwqplude8e0w6fhrmqgsnlp49weawef3ahlutypvu6",
    "signals": "agent1qtwk0kzcnqym78rq5fgl6hxua2yessmlgunan27xezk0zr4th7ugkz32ndm",
    "translate": "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz",
    "stats": "agent1qvtnt9s6uhua3c3jundxrpgqjsy9quc2h4s83anjg6r2m95g90dn2ruw8zm",
    "github": "agent1q20jn039g90w7lv8rch2uzjwv36tm5kwmsfe5dqc70zht27enqpkcjewdkz",
}


def resolve_name(name: str) -> str | None:
    """Search Agentverse by name and return the top agent's address."""
    body = json.dumps(
        {
            "search_text": name,
            "sort": "relevancy",
            "direction": "desc",
            "filters": {"state": ["active"]},
            "offset": 0,
            "limit": 1,
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        agents = data.get("agents", [])
        if agents:
            hit = agents[0]
            print(
                f'Resolved "{name}" -> {hit["name"]} ({hit["address"]})',
                file=sys.stderr,
            )
            return hit["address"]
    except Exception as e:
        print(f"Agentverse lookup failed: {e}", file=sys.stderr)
    return None


# ── CLI parsing ─────────────────────────────────────────────────────


def usage():
    print(
        'Usage: call.py <address|shortcut|name> "query" [--timeout 90] [--seed SEED]',
        file=sys.stderr,
    )
    print(f"Shortcuts: {', '.join(SHORTCUTS)}", file=sys.stderr)
    print('Names:     call.py "Weather Agent" "forecast for NYC"', file=sys.stderr)
    sys.exit(2)


def parse_args():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] in ("-h", "--help"):
        usage()

    target = args[0]

    if target in SHORTCUTS:
        target = SHORTCUTS[target]
    elif target.startswith("agent1q"):
        pass
    else:
        resolved = resolve_name(target)
        if not resolved:
            print(f'Error: no agent found for "{target}"', file=sys.stderr)
            sys.exit(1)
        target = resolved

    timeout = 90
    seed = os.environ.get("FETCH_AGENT_SEED", "")
    if not seed:
        # Auto-generate a unique seed per install, persisted to a local file
        seed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".seed")
        if os.path.exists(seed_file):
            seed = open(seed_file).read().strip()
        else:
            seed = f"openclaw-fetch-{uuid4().hex}"
            with open(seed_file, "w") as f:
                f.write(seed)
            print(
                f"Generated new agent identity (seed saved to {seed_file})",
                file=sys.stderr,
            )
    query_parts = []

    i = 1
    while i < len(args):
        if args[i] == "--timeout" and i + 1 < len(args):
            timeout = int(args[i + 1])
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("Error: no query provided", file=sys.stderr)
        usage()

    return target, query, timeout, seed


# ── auto-register mailbox ───────────────────────────────────────────


async def register_mailbox_delayed(port: int, ctx, done_event: asyncio.Event) -> None:
    """Wait for the local HTTP server to start, then POST to /connect."""
    api_key = os.environ.get("AGENTVERSE_API_KEY", "").strip()
    if not api_key:
        done_event.set()
        return

    # Wait for the ASGI server to be ready
    await asyncio.sleep(3)

    payload = json.dumps(
        {
            "user_token": api_key,
            "agent_type": "mailbox",
        }
    ).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}/connect",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            if resp.status == 200:
                ctx.logger.info("Mailbox registered with Agentverse")
            else:
                ctx.logger.warning(
                    f"Mailbox registration returned {resp.status}: {body}"
                )
    except Exception:
        ctx.logger.info(
            "Mailbox registration in progress (handler will complete async)"
        )

    # Give the mailbox client time to pick up the registration
    await asyncio.sleep(3)
    done_event.set()


# ── main ────────────────────────────────────────────────────────────


def main():
    target, query, timeout_secs, seed = parse_args()

    try:
        from uagents import Agent, Context, Protocol
        from uagents_core.contrib.protocols.chat import (
            ChatMessage,
            ChatAcknowledgement,
            TextContent,
            chat_protocol_spec,
        )
    except ImportError:
        print(
            "Error: uagents not installed. Run: pip install uagents uagents-core",
            file=sys.stderr,
        )
        sys.exit(1)

    port = random.randint(9100, 9999)

    agent = Agent(
        name="openclaw_caller",
        seed=seed,
        port=port,
        mailbox=True,
        network="testnet",
    )

    proto = Protocol(spec=chat_protocol_spec)
    message_sent = False

    mailbox_ready = asyncio.Event()

    @agent.on_event("startup")
    async def startup(ctx: Context):
        api_key = os.environ.get("AGENTVERSE_API_KEY", "").strip()
        if not api_key:
            ctx.logger.warning(
                "No AGENTVERSE_API_KEY set — mailbox registration skipped. "
                "Set it to receive responses: export AGENTVERSE_API_KEY=<key>"
            )

        # Register mailbox and wait for it to complete before sending
        asyncio.create_task(register_mailbox_delayed(port, ctx, mailbox_ready))
        await mailbox_ready.wait()

        ctx.logger.info(f"Sending to {target}: {query}")
        print("Connecting to Agentverse agent...", flush=True)
        await ctx.send(
            target,
            ChatMessage(content=[TextContent(text=query)]),
        )
        nonlocal message_sent
        message_sent = True
        print(
            "Message sent. Waiting for response (this takes 15-60 seconds)...",
            flush=True,
        )
        ctx.logger.info("Message sent — waiting for response...")

    @proto.on_message(ChatMessage)
    async def on_response(ctx: Context, sender: str, msg: ChatMessage):
        if sender != target:
            ctx.logger.info(f"Ignoring message from {sender}")
            return
        if not message_sent:
            ctx.logger.info("Ignoring stale message from mailbox queue")
            return
        parts = [item.text for item in msg.content if hasattr(item, "text")]
        response = "\n".join(parts)
        ctx.logger.info(f"Response received from {sender}")
        print("---RESPONSE_START---")
        print(response)
        sys.stdout.flush()
        os._exit(0)

    @proto.on_message(ChatAcknowledgement)
    async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(f"Acknowledged by {sender}")

    agent.include(proto)

    def on_timeout(signum, frame):
        print(f"Timeout: no response within {timeout_secs}s.", file=sys.stderr)
        os._exit(1)

    signal.signal(signal.SIGALRM, on_timeout)
    signal.alarm(timeout_secs)

    agent.run()


if __name__ == "__main__":
    main()
