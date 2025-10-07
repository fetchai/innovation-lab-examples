import os
from pathlib import Path
from uagents_adapter.a2a_outbound import SingleA2AAdapter

# Load env if available
try:
    from dotenv import load_dotenv
    # Load from examples root if present, then local folder as fallback
    ROOT = Path(__file__).resolve().parents[1]
    load_dotenv(ROOT / ".env", override=True)
    load_dotenv(Path(__file__).parent / ".env", override=True)
except Exception:
    pass

# Import executor (works when run as script)
try:
    from .store_executor import StoreAgentExecutor  # type: ignore
except Exception:
    from store_executor import StoreAgentExecutor


def main():
    a2a_port = int(os.getenv("STORE_A2A_PORT", "10031"))
    uagent_port = int(os.getenv("STORE_UAGENT_PORT", "8230"))

    executor = StoreAgentExecutor()
    adapter = SingleA2AAdapter(
        agent_executor=executor,
        name="demo_store_uagent",
        description="Store agent with cart + payment",
        port=uagent_port,
        a2a_port=a2a_port,
        mailbox=True,
    )
    adapter.run()


if __name__ == "__main__":
    main()


