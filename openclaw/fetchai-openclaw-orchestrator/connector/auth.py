"""
Request authentication for the OpenClaw Connector.

Verifies that inbound task dispatches:
  • Carry a valid Ed25519 signature
  • Come from a recognised orchestrator
  • Have not been tampered with
"""

from __future__ import annotations

import json
import logging

from shared.crypto import verify_signature
from shared.schemas import RejectionReason

logger = logging.getLogger(__name__)


class RequestAuthenticator:
    """Validates incoming task dispatch signatures."""

    def __init__(self, orchestrator_public_key_hex: str | None = None):
        # In the MVP the orchestrator's public key is configured at
        # startup.  In production it would be fetched from Agentverse
        # or the Almanac contract.
        self._orchestrator_pubkey = orchestrator_public_key_hex

    @property
    def has_key(self) -> bool:
        return self._orchestrator_pubkey is not None

    def set_orchestrator_key(self, public_key_hex: str) -> None:
        self._orchestrator_pubkey = public_key_hex
        logger.info("Orchestrator public key configured")

    def verify_dispatch(
        self,
        task_plan_json: str,
        signature_hex: str,
    ) -> tuple[bool, RejectionReason | None]:
        """
        Verify the signature over a serialised task plan.

        Returns ``(True, None)`` on success or ``(False, reason)``
        on failure.
        """
        if not self._orchestrator_pubkey:
            logger.warning(
                "No orchestrator public key configured – skipping verification"
            )
            # In dev mode we allow unsigned requests
            return True, None

        if not signature_hex:
            return False, RejectionReason.INVALID_SIGNATURE

        try:
            plan_dict = json.loads(task_plan_json)
        except json.JSONDecodeError:
            return False, RejectionReason.INVALID_SIGNATURE

        ok = verify_signature(
            public_key_hex=self._orchestrator_pubkey,
            payload=plan_dict,
            signature_hex=signature_hex,
        )
        if not ok:
            logger.warning("Signature verification failed")
            return False, RejectionReason.INVALID_SIGNATURE

        return True, None
