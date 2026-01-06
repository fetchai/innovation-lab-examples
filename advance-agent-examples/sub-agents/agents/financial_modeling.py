from shared.agent import AgentManager
from shared.tools import generate_financial_chart

def main() -> None:
    manager = AgentManager.load("Financial Modeling")
    manager.run_agent(tools=[generate_financial_chart])

if __name__ == "__main__":
    main()