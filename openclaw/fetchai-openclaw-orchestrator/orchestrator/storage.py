"""
In-memory device pairing storage for the Orchestrator Agent.

In production this would be backed by Agentverse agent storage or
an external datastore.  For the MVP we keep everything in-process.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from shared.schemas import DeviceRecord

logger = logging.getLogger(__name__)


class PairingStore:
    """Thread-safe in-memory registry of paired devices."""

    def __init__(self) -> None:
        # key = (user_id, device_id)
        self._devices: dict[tuple[str, str], DeviceRecord] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def pair(
        self,
        user_id: str,
        device_id: str,
        public_key_hex: str,
        capabilities: list[str] | None = None,
    ) -> DeviceRecord:
        record = DeviceRecord(
            user_id=user_id,
            device_id=device_id,
            public_key_hex=public_key_hex,
            capabilities=capabilities or ["weekly_report"],
            paired_at=datetime.now(timezone.utc),
        )
        self._devices[(user_id, device_id)] = record
        logger.info("Paired device %s for user %s", device_id, user_id)
        return record

    def unpair(self, user_id: str, device_id: str) -> bool:
        key = (user_id, device_id)
        if key in self._devices:
            del self._devices[key]
            logger.info("Unpaired device %s for user %s", device_id, user_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, user_id: str, device_id: str) -> DeviceRecord | None:
        return self._devices.get((user_id, device_id))

    def is_paired(self, user_id: str, device_id: str) -> bool:
        return (user_id, device_id) in self._devices

    def devices_for_user(self, user_id: str) -> list[DeviceRecord]:
        return [rec for (uid, _), rec in self._devices.items() if uid == user_id]

    def all_devices(self) -> list[DeviceRecord]:
        return list(self._devices.values())
