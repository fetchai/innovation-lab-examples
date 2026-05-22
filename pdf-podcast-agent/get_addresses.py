"""
get_addresses.py – Address sheet printer
=========================================
Prints the deterministic on-chain addresses for all four agents WITHOUT
starting any servers. Because addresses are derived purely from seed phrases,
this is always accurate.

Usage:
    python get_addresses.py

Copy the output into your .env (or paste the export block into your terminal)
before starting the orchestrator.
"""

import os
from uagents import Agent

seeds = {
    "ORCHESTRATOR": os.getenv("ORCHESTRATOR_SEED", "pdf_podcast_orchestrator_seed_v1"),
    "EXTRACTOR": os.getenv("EXTRACTOR_SEED", "rag_extractor_podcast_seed_v1"),
    "SCRIPTWRITER": os.getenv("SCRIPTWRITER_SEED", "podcast_scriptwriter_seed_v1"),
    "VOICE_STUDIO": os.getenv("VOICE_STUDIO_SEED", "voice_studio_podcast_seed_v1"),
    "HOST_A": os.getenv("HOST_A_SEED", "pdf_podcast_host_a_seed_v1"),
    "HOST_B": os.getenv("HOST_B_SEED", "pdf_podcast_host_b_seed_v1"),
}

# Build agents just to read their addresses (no .run() called)
agents = {name: Agent(name=name.lower(), seed=seed) for name, seed in seeds.items()}

print()
print("=" * 65)
print("  PDF-to-Podcast Agent Addresses")
print("=" * 65)
for name, agent in agents.items():
    print(f"  {name:<16} {agent.address}")
print("=" * 65)

print()
print("-- Paste into .env ------------------------------------------")
print(f"EXTRACTOR_ADDRESS={agents['EXTRACTOR'].address}")
print(f"SCRIPTWRITER_ADDRESS={agents['SCRIPTWRITER'].address}")
print(f"VOICE_STUDIO_ADDRESS={agents['VOICE_STUDIO'].address}")
print(f"HOST_A_ADDRESS={agents['HOST_A'].address}")
print(f"HOST_B_ADDRESS={agents['HOST_B'].address}")
print()
print("-- Or export in PowerShell ----------------------------------")
print(f'$env:EXTRACTOR_ADDRESS="{agents["EXTRACTOR"].address}"')
print(f'$env:SCRIPTWRITER_ADDRESS="{agents["SCRIPTWRITER"].address}"')
print(f'$env:VOICE_STUDIO_ADDRESS="{agents["VOICE_STUDIO"].address}"')
print(f'$env:HOST_A_ADDRESS="{agents["HOST_A"].address}"')
print(f'$env:HOST_B_ADDRESS="{agents["HOST_B"].address}"')
print()
print("-- Or export in bash ----------------------------------------")
print(f'export EXTRACTOR_ADDRESS="{agents["EXTRACTOR"].address}"')
print(f'export SCRIPTWRITER_ADDRESS="{agents["SCRIPTWRITER"].address}"')
print(f'export VOICE_STUDIO_ADDRESS="{agents["VOICE_STUDIO"].address}"')
print(f'export HOST_A_ADDRESS="{agents["HOST_A"].address}"')
print(f'export HOST_B_ADDRESS="{agents["HOST_B"].address}"')
print()
