from shared.agent import AgentManager

def main() -> None:
    manager = AgentManager.load("Risk Assessment")
    manager.run_agent(tools=[])

if __name__ == "__main__":
    main()