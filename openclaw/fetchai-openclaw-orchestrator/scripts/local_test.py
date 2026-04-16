#!/usr/bin/env python3
"""
Local end-to-end test script.

Exercises the full pipeline *without* needing Agentverse:
  1. Planner   – converts an objective into a task plan
  2. Policy    – validates the plan against Fetch-side + local policies
  3. Crypto    – signs the plan, verifies the signature
  4. Executor  – runs the plan through the connector executor

Run:
    python scripts/local_test.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force demo directory for safe testing
os.environ.setdefault("DEMO_PROJECTS_DIR", str(PROJECT_ROOT / "demo_projects"))

from shared.crypto import (
    generate_keypair,
    public_key_to_hex,
    sign_payload,
    verify_signature,
)
from shared.schemas import TaskStatus
from orchestrator.planner import plan_objective
from orchestrator.policy import FetchPolicy
from orchestrator.storage import PairingStore
from connector.auth import RequestAuthenticator
from connector.policy import LocalPolicy
from connector.executor import execute_plan


def divider(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main():
    # ------------------------------------------------------------------
    # 1. Simulate device pairing
    # ------------------------------------------------------------------
    divider("1. DEVICE PAIRING")

    priv, pub = generate_keypair()
    pub_hex = public_key_to_hex(pub)
    print("  Generated device keypair")
    print(f"  Public key : {pub_hex[:32]}…")

    store = PairingStore()
    record = store.pair("u_test", "dev_test", pub_hex, ["weekly_report"])
    print(f"  Paired     : user={record.user_id} device={record.device_id}")
    assert store.is_paired("u_test", "dev_test")
    print("  ✅ Pairing verified")

    # ------------------------------------------------------------------
    # 2. Objective → Task Plan
    # ------------------------------------------------------------------
    divider("2. OBJECTIVE → TASK PLAN")

    objective = "Generate my weekly dev report and post a summary to Slack"
    print(f"  Objective: {objective}")

    plan = plan_objective(objective)
    print(f"  Task ID  : {plan.task_id}")
    print(f"  Steps    : {len(plan.steps)}")
    for i, step in enumerate(plan.steps, 1):
        print(f"    {i}. [{step.type.value}] {step.action} {step.params}")
    print(
        f"  Constraints: no_delete={plan.constraints.no_delete}, "
        f"confirm={plan.constraints.require_user_confirmation}"
    )

    # ------------------------------------------------------------------
    # 3. Fetch-side policy check
    # ------------------------------------------------------------------
    divider("3. FETCH-SIDE POLICY CHECK")

    policy = FetchPolicy()
    rejection = policy.validate("u_test", plan)
    if rejection is None:
        print("  ✅ Plan passes Fetch-side policy")
    else:
        print(f"  ❌ Rejected: {rejection.value}")
        return 1

    # ------------------------------------------------------------------
    # 4. Sign the task plan
    # ------------------------------------------------------------------
    divider("4. SIGN TASK PLAN")

    plan_dict = plan.model_dump(mode="json")
    plan_json = json.dumps(plan_dict, sort_keys=True, default=str)
    signature = sign_payload(priv, plan_dict)
    print(f"  Signature: {signature[:32]}…")

    # Verify
    ok = verify_signature(pub_hex, plan_dict, signature)
    print(f"  ✅ Signature valid: {ok}")

    # ------------------------------------------------------------------
    # 5. Connector authentication
    # ------------------------------------------------------------------
    divider("5. CONNECTOR AUTHENTICATION")

    auth = RequestAuthenticator(orchestrator_public_key_hex=pub_hex)
    ok, reason = auth.verify_dispatch(plan_json, signature)
    print(f"  Auth result: ok={ok}, reason={reason}")
    assert ok
    print("  ✅ Connector accepted the signed dispatch")

    # ------------------------------------------------------------------
    # 6. Local policy check
    # ------------------------------------------------------------------
    divider("6. LOCAL POLICY CHECK")

    local_policy = LocalPolicy()
    local_rejection = local_policy.validate_plan(plan)
    if local_rejection is None:
        print("  ✅ Plan passes local policy")
    else:
        print(f"  ❌ Rejected: {local_rejection.value}")
        return 1

    # ------------------------------------------------------------------
    # 7. Execute the plan
    # ------------------------------------------------------------------
    divider("7. EXECUTE TASK PLAN")

    result = execute_plan(plan)
    print(f"  Task ID : {result.task_id}")
    print(f"  Status  : {result.status.value}")
    print("  Steps   :")
    for sr in result.step_results:
        emoji = "✅" if sr.status == TaskStatus.COMPLETED else "❌"
        print(f"    {emoji} {sr.action}: {sr.status.value}")
        if sr.error:
            print(f"       Error: {sr.error}")
        if sr.output and isinstance(sr.output, dict):
            for k, v in sr.output.items():
                val = str(v)
                if len(val) > 80:
                    val = val[:80] + "…"
                print(f"       {k}: {val}")

    # ------------------------------------------------------------------
    # 8. Summary
    # ------------------------------------------------------------------
    divider("8. SUMMARY")

    report_text = result.outputs.get("generate_report", {}).get("report_text", "")
    if report_text:
        print("  --- Generated Report ---")
        for line in report_text.split("\n")[:20]:
            print(f"  {line}")
        if report_text.count("\n") > 20:
            print("  … (truncated)")

    print(f"\n  Overall status: {result.status.value}")
    print("  ✅ End-to-end local test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
