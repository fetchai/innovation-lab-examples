from shared.agent import AgentManager
from shared.tools import generate_infographic

def main() -> None:
    manager = AgentManager.load("Infographic Generator")
    manager.run_agent(tools=[generate_infographic])

if __name__ == "__main__":
    main()