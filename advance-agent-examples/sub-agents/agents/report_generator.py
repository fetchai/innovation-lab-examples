from shared.agent import AgentManager
from shared.tools import generate_html_report

def main() -> None:
    manager = AgentManager.load("Report Generator")
    manager.run_agent(tools=[generate_html_report])

if __name__ == "__main__":
    main()