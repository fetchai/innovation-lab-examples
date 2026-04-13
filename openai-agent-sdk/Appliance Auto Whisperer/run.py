"""
run.py — Convenience launcher
==============================
Starts all three agents in separate subprocesses with staggered startup,
mirroring the pdf-podcast-agent pattern so you get clean isolated logs.

Usage:
    python run.py

Press Ctrl+C to stop all three agents at once.

Alternatively run each agent manually in its own terminal:
    Terminal 1:  python workers/parts_agent.py
    Terminal 2:  python workers/tutorial_agent.py
    Terminal 3:  python diagnostic_bureau.py      ← start LAST
"""

import os
import subprocess
import sys
import threading
import time

from pathlib import Path

# ── Pre-flight checks ─────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    # Load .env into os.environ so child processes inherit all keys
    from dotenv import load_dotenv

    load_dotenv(env_file)

missing = [k for k in ("AGENTVERSE_API_KEY", "GEMINI_API_KEY") if not os.getenv(k)]
if missing:
    print(f"[run.py] WARNING: missing env vars: {', '.join(missing)}")
    print("         Copy .env.example → .env and fill in your keys.")
    print("         Continuing anyway — some features may not work.\n")

# ── Launch subprocesses ───────────────────────────────────────────────────────

agents = [
    ("PartsAgent", [sys.executable, "workers/parts_agent.py"]),
    ("TutorialAgent", [sys.executable, "workers/tutorial_agent.py"]),
    ("Orchestrator", [sys.executable, "diagnostic_bureau.py"]),
]

procs: list[tuple[str, subprocess.Popen]] = []
for label, cmd in agents:
    p = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    procs.append((label, p))
    print(f"[run.py] Started {label} (pid {p.pid})")
    # Stagger startup: give workers time to register on Almanac before
    # the orchestrator starts resolving their addresses.
    time.sleep(2.0 if label != "Orchestrator" else 0.5)

print("\n[run.py] All agents running — streaming logs below.")
print("[run.py] Press Ctrl+C to stop all agents.\n")

# ── Stream merged logs from all children ──────────────────────────────────────


def _stream(label: str, proc: subprocess.Popen) -> None:
    for line in proc.stdout:  # type: ignore[union-attr]
        print(f"[{label}] {line}", end="", flush=True)


threads = [
    threading.Thread(target=_stream, args=(lbl, p), daemon=True) for lbl, p in procs
]
for t in threads:
    t.start()

# ── Wait / Ctrl+C shutdown ────────────────────────────────────────────────────

try:
    while all(p.poll() is None for _, p in procs):
        time.sleep(1)
    # If any agent died unexpectedly, report it
    for label, p in procs:
        rc = p.poll()
        if rc is not None:
            print(
                f"\n[run.py] {label} exited with code {rc} — shutting down all agents."
            )
            break
except KeyboardInterrupt:
    print("\n[run.py] Ctrl+C received — shutting down all agents …")

for label, p in procs:
    p.terminate()
for label, p in procs:
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()

print("[run.py] All agents stopped.")
