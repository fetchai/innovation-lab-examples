from shared.agent import AgentManager
from shared.tools import google_search

def main() -> None:
    manager = AgentManager.load("Company Research")
    manager.run_agent(tools=[google_search])

if __name__ == "__main__":
    main()