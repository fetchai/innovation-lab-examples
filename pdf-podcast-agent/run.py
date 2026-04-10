"""
run.py – Convenience launcher (optional)
=========================================
Starts all four agents in SEPARATE subprocesses (one per agent), so you
get clean, isolated logs for each one — just like running 4 terminals by hand.

Usage:
    python run.py

Press Ctrl+C to stop all agents at once.

Alternatively, start each agent manually in its own terminal:
    Terminal 1:  python extractor_agent.py
    Terminal 2:  python scriptwriter_agent.py
    Terminal 3:  python voice_studio_agent.py
    Terminal 4:  python orchestrator.py       (start LAST)
"""

import os
import signal
import subprocess
import sys
import time

# ── Pre-flight checks ─────────────────────────────────────────────────────────

if not os.getenv("OPENAI_API_KEY"):
    print("[ERROR] OPENAI_API_KEY is not set.")
    print("  Set it first:  $env:OPENAI_API_KEY='sk-...'  (PowerShell)")
    sys.exit(1)

# Compute and inject addresses so the orchestrator has them from the start
print("Computing agent addresses …")
import importlib.util, io, contextlib

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(open("get_addresses.py").read())

output = buf.getvalue()
print(output)

# Parse the env-var lines from get_addresses output
env_extra = {}
for line in output.splitlines():
    if line.startswith("EXTRACTOR_ADDRESS="):
        env_extra["EXTRACTOR_ADDRESS"] = line.split("=", 1)[1]
    elif line.startswith("SCRIPTWRITER_ADDRESS="):
        env_extra["SCRIPTWRITER_ADDRESS"] = line.split("=", 1)[1]
    elif line.startswith("VOICE_STUDIO_ADDRESS="):
        env_extra["VOICE_STUDIO_ADDRESS"] = line.split("=", 1)[1]

child_env = {**os.environ, **env_extra}

# ── Launch subprocesses ───────────────────────────────────────────────────────

agents = [
    ("Extractor",    [sys.executable, "extractor_agent.py"]),
    ("Scriptwriter", [sys.executable, "scriptwriter_agent.py"]),
    ("VoiceStudio",  [sys.executable, "voice_studio_agent.py"]),
    ("Orchestrator", [sys.executable, "orchestrator.py"]),
]

procs = []
for label, cmd in agents:
    p = subprocess.Popen(
        cmd,
        env=child_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    procs.append((label, p))
    print(f"[run.py] Started {label} (pid {p.pid})")
    time.sleep(0.5)   # stagger startup slightly

print("\n[run.py] All agents running. Press Ctrl+C to stop.\n")

# ── Stream logs from all children ─────────────────────────────────────────────
import threading

def stream(label, proc):
    for line in proc.stdout:
        print(f"[{label}] {line}", end="")

threads = [threading.Thread(target=stream, args=(l, p), daemon=True) for l, p in procs]
for t in threads:
    t.start()

# ── Shutdown on Ctrl+C ────────────────────────────────────────────────────────
try:
    while all(p.poll() is None for _, p in procs):
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[run.py] Shutting down …")
    for label, p in procs:
        p.terminate()
    for label, p in procs:
        p.wait()
    print("[run.py] All agents stopped.")
