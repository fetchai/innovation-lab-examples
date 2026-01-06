from shared.agent import AgentManager

def main() -> None:
    manager = AgentManager.load("Investor Memo")
    manager.run_agent(tools=[])

if __name__ == "__main__":
    main()