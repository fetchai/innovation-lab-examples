"""
Emit deterministic agent addresses for Docker startup.

This script prints KEY=VALUE lines suitable for sourcing from a shell script.
If a variable already exists in the environment, that value is preserved.
"""

import os

from uagents import Agent


def _address_from_seed(agent_name: str, seed_value: str) -> str:
    return Agent(name=agent_name, seed=seed_value).address


def main() -> None:
    seeds = {
        "EXTRACTOR_ADDRESS": os.getenv("EXTRACTOR_SEED", "rag_extractor_podcast_seed_v1"),
        "SCRIPTWRITER_ADDRESS": os.getenv("SCRIPTWRITER_SEED", "podcast_scriptwriter_seed_v1"),
        "VOICE_STUDIO_ADDRESS": os.getenv("VOICE_STUDIO_SEED", "voice_studio_podcast_seed_v1"),
        "HOST_A_ADDRESS": os.getenv("HOST_A_SEED", "pdf_podcast_host_a_seed_v1"),
        "HOST_B_ADDRESS": os.getenv("HOST_B_SEED", "pdf_podcast_host_b_seed_v1"),
    }

    agent_names = {
        "EXTRACTOR_ADDRESS": "extractor",
        "SCRIPTWRITER_ADDRESS": "scriptwriter",
        "VOICE_STUDIO_ADDRESS": "voice_studio",
        "HOST_A_ADDRESS": "host_a",
        "HOST_B_ADDRESS": "host_b",
    }

    for env_var, seed in seeds.items():
        current = os.getenv(env_var)
        value = current if current else _address_from_seed(agent_names[env_var], seed)
        print(f"{env_var}={value}")


if __name__ == "__main__":
    main()
