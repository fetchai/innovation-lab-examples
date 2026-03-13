import os
from dotenv import find_dotenv, load_dotenv
from uagents_core.identity import Identity

load_dotenv(find_dotenv())

ALICE_SEED = os.getenv("ALICE_SEED_PHRASE")
BOB_SEED = os.getenv("BOB_SEED_PHRASE")
ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_SEED_PHRASE")

ALICE_ADDRESS = Identity.from_seed(seed=ALICE_SEED, index=0).address
BOB_ADDRESS = Identity.from_seed(seed=BOB_SEED, index=0).address
