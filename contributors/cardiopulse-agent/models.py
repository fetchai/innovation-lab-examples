"""
Shared message models for CardioPulse + Bridge agent communication.

These types define the contract between the bridge (which talks to the watch
over BLE on the user's local machine) and the main CardioPulse agent (which
runs on Agentverse and handles chat, scoring, and coaching).
"""

from __future__ import annotations

from uagents import Model


class HRReading(Model):
    """One heart rate reading from the watch.

    Sent from bridge_agent -> cardiopulse_agent, typically once per second
    while the watch is broadcasting.
    """

    bpm: int
    rr_intervals: list[float] = []
    ts: float  # unix timestamp from the bridge's clock


class HRAck(Model):
    """Trivial acknowledgement so the bridge knows the message landed."""

    ok: bool
