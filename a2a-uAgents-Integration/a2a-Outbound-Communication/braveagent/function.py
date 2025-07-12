from typing import Dict, List
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers
from brave.agent import BraveSearchAgentExecutor  

class BraveSearchAgent:
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        print("🔧 Setting up Brave Search Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="brave_search_specialist",
                description="AI Agent for web and news search using Brave Search API",
                url="http://localhost:10020",
                port=10020,
                specialties=["web search", "news", "information retrieval", "local business", "site-specific lookup"],
                priority=3
            )
        ]
        self.executors = {
            "brave_search_specialist": BraveSearchAgentExecutor()
        }
        print("✅ Brave Search Agent configuration created")

    def start_individual_a2a_servers(self):
        print("🔄 Starting Brave Search server...")
        a2a_servers(self.agent_configs, self.executors)
        print("✅ Brave Search server started!")

    def create_coordinator(self):
        print("🤖 Creating Brave Coordinator...")
        # Use a valid agent_executor, e.g., the BraveSearchAgentExecutor or a coordinator logic
        brave_executor = self.executors.get("brave_search_specialist")
        if brave_executor is None:
            raise ValueError("BraveSearchAgentExecutor not found in executors dictionary.")
        self.coordinator = SingleA2AAdapter(
            agent_executor=brave_executor,
            name="brave_coordinator",
            description="Coordinator for routing Brave Search queries",
            port=8200,
            mailbox=True
        )
        print("✅ Brave Coordinator created!")
        return self.coordinator

    def start_system(self):
        print("🚀 Starting Brave Search System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            print(f"🎯 Starting Brave coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            print("👋 Shutting down Brave Search system...")
            self.running = False
        except Exception as e:
            print(f"❌ Error: {e}")
            self.running = False

def main():
    try:
        system = BraveSearchAgent()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Brave system shutdown complete!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
