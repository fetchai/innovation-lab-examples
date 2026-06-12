"""
Bridge agent: reads heart rate over BLE from a Garmin watch and POSTs each
reading to the CardioPulse agent's local REST endpoint (default
http://127.0.0.1:8001/bpm).

This runs on the user's local machine (BLE is local hardware). The bridge and
the main agent run on the same machine, so a direct localhost POST keeps up
with the 1Hz heart-rate stream — agent-to-agent mailbox messaging is too slow
for that rate. Override AGENT_URL in .env only if you move the agent elsewhere.

    python bridge_agent.py
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx
from bleak import BleakClient, BleakScanner
from dotenv import load_dotenv
from uagents import Agent, Context

print("Bridge agent starting up...", flush=True)

load_dotenv()


# ---------- Configuration ----------------------------------------------------

# Local URL the bridge POSTs HR readings to. Both agents run on the same
# machine, so localhost is fast and direct (1Hz streaming).
AGENT_URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8001/bpm")
BRIDGE_SEED = os.environ.get("BRIDGE_SEED", "cardio-bridge-default-seed-change-me")
DEVICE_HINT = os.environ.get("GARMIN_NAME", "Forerunner")

# Kept for reference / future use when CardioPulse moves to a cloud host.
CARDIOPULSE_ADDRESS = os.environ.get("CARDIOPULSE_ADDRESS", "").strip()

# Standard BLE Heart Rate Service / Measurement characteristic UUIDs.
HEART_RATE_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"


# ---------- BLE parsing ------------------------------------------------------


def parse_hr_measurement(data: bytearray) -> dict:
    """Decode the standard BLE Heart Rate Measurement payload."""
    flags = data[0]
    hr_16bit = flags & 0x01
    energy_present = (flags >> 3) & 0x01
    rr_present = (flags >> 4) & 0x01

    offset = 1
    if hr_16bit:
        bpm = int.from_bytes(data[offset : offset + 2], byteorder="little")
        offset += 2
    else:
        bpm = data[offset]
        offset += 1
    if energy_present:
        offset += 2  # skip 2 bytes of energy

    rr_intervals: list[float] = []
    if rr_present:
        while offset + 1 < len(data):
            rr_raw = int.from_bytes(data[offset : offset + 2], byteorder="little")
            rr_intervals.append(round(rr_raw * 1000 / 1024, 2))
            offset += 2

    return {"bpm": bpm, "rr_intervals": rr_intervals}


async def find_garmin():
    """Scan once for a Garmin watch advertising the standard HR service."""
    devices = await BleakScanner.discover(timeout=15.0)
    for d in devices:
        name = d.name or ""
        if DEVICE_HINT.lower() in name.lower() or "garmin" in name.lower():
            return d
    return None


async def wait_for_garmin(ctx: Context):
    """Keep scanning until the watch shows up. Don't exit if it's offline —
    that would crash-loop under KeepAlive. Just wait patiently."""
    attempt = 0
    while True:
        attempt += 1
        ctx.logger.info(
            f"Scanning for BLE devices matching '{DEVICE_HINT}' "
            f"(attempt {attempt}, 15s)..."
        )
        device = await find_garmin()
        if device:
            ctx.logger.info(f"Found: {device.name} ({device.address})")
            return device
        ctx.logger.info(
            "No matching device. Sleeping 30s before next scan. "
            "Tip: enable Broadcast Heart Rate on your watch."
        )
        await asyncio.sleep(30)


# ---------- Agent runtime ----------------------------------------------------

bridge = Agent(
    name="cardio-bridge",
    seed=BRIDGE_SEED,
    port=8003,
    mailbox=False,  # Bridge talks to a known address; no mailbox needed.
)

# Shared queue from BLE callback -> agent send loop. Using a queue lets the
# BLE callback stay fast (non-blocking) while the agent does the network I/O.
_send_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)

# Stats for the periodic "[POST status]" line.
_stats = {"sent": 0, "ack": 0, "fail": 0, "last_err": ""}


@bridge.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(f"Bridge online (POSTing HR readings to {AGENT_URL})")

    # Spin up the BLE scanner + sender loop as background tasks.
    asyncio.create_task(_ble_loop(ctx))
    asyncio.create_task(_sender_loop(ctx))
    asyncio.create_task(_status_loop(ctx))


async def _ble_loop(ctx: Context) -> None:
    """Outer loop: find the watch, hold the connection, reconnect if dropped.

    This loop runs forever. If the watch goes offline (broadcast disabled,
    out of range, dead battery), the BLE client will raise and we just go
    back to scanning instead of exiting. That way KeepAlive never has to
    restart us.
    """
    while True:
        device = await wait_for_garmin(ctx)
        try:
            async with BleakClient(device) as ble:
                ctx.logger.info(f"Connected to {device.name}. Streaming HR...")

                def on_hr(_handle, data: bytearray) -> None:
                    parsed = parse_hr_measurement(data)
                    parsed["ts"] = time.time()
                    try:
                        _send_queue.put_nowait(parsed)
                    except asyncio.QueueFull:
                        # Drop old readings rather than block the BLE callback.
                        pass

                await ble.start_notify(HEART_RATE_MEASUREMENT, on_hr)
                # Stay connected as long as the BLE link is alive.
                while ble.is_connected:
                    await asyncio.sleep(5)
                ctx.logger.warning("BLE connection dropped. Will rescan and reconnect.")
        except Exception as e:
            ctx.logger.warning(
                f"BLE loop error ({type(e).__name__}): {e}. Retrying in 10s."
            )
            await asyncio.sleep(10)


async def _sender_loop(ctx: Context) -> None:
    """Pull readings off the queue and POST them to the local agent endpoint.

    Uses a single httpx.AsyncClient with keep-alive so each POST reuses the
    same TCP connection — fast enough to keep up with 1Hz BLE notifications.
    """
    async with httpx.AsyncClient(timeout=2.0) as http:
        while True:
            reading = await _send_queue.get()
            try:
                resp = await http.post(AGENT_URL, json=reading)
                if resp.status_code < 300:
                    _stats["sent"] += 1
                    _stats["ack"] += 1
                else:
                    _stats["fail"] += 1
                    _stats["last_err"] = f"HTTP {resp.status_code}: {resp.text[:120]}"
            except Exception as e:
                _stats["fail"] += 1
                _stats["last_err"] = f"{type(e).__name__}: {e}"


async def _status_loop(ctx: Context) -> None:
    """Print a heartbeat status line every 10 seconds so the user can see flow."""
    while True:
        await asyncio.sleep(10)
        sent = _stats["sent"]
        ack = _stats["ack"]
        fail = _stats["fail"]
        if fail > 0:
            ctx.logger.info(
                "stream: %d sent / %d ack / %d failed -> last error: %s",
                sent,
                ack,
                fail,
                _stats["last_err"],
            )
        else:
            ctx.logger.info("stream: %d sent / %d ack / 0 failed", sent, ack)


if __name__ == "__main__":
    bridge.run()
