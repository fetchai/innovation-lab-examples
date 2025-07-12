from typing import Dict, List
from uagents_adapter import MultiA2AAdapter, A2AAgentConfig, a2a_servers
from agents.research_agent import ResearchAgentExecutor
from agents.coding_agent import CodingAgentExecutor
from agents.analysis_agent import AnalysisAgentExecutor
import os
from dotenv import load_dotenv

load_dotenv()

class MultiAgentOrchestrator:
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        print("🔧 Setting up Multi-Agent System")
        self.agent_configs = [
            A2AAgentConfig(
                name="research_specialist",
                description="AI Research Specialist for research and analysis",
                url="http://localhost:10020",
                port=10020,
                specialties=["research", "analysis", "fact-finding", "summarization"],
                priority=3
            ),
            A2AAgentConfig(
                name="coding_specialist",
                description="AI Software Engineer for coding",
                url="http://localhost:10022",
                port=10022,
                specialties=["coding", "debugging", "programming"],
                priority=3
            ),
            A2AAgentConfig(
                name="analysis_specialist",
                description="AI Data Analyst for insights and metrics",
                url="http://localhost:10023",
                port=10023,
                specialties=["data analysis", "insights", "forecasting"],
                priority=2
            )
        ]
        self.executors = {
            "research_specialist": ResearchAgentExecutor(),
            "coding_specialist": CodingAgentExecutor(),
            "analysis_specialist": AnalysisAgentExecutor()
        }
        print("✅ Agent configurations created")

    def start_individual_a2a_servers(self):
        print("🔄 Starting servers...")
        a2a_servers(self.agent_configs, self.executors)
        print("✅ Servers started!")

    def create_coordinator(self):
        print("🤖 Creating Coordinator...")
        self.coordinator = MultiA2AAdapter(
            name="coordinator-TEST-GAUTAM",
            description="Routes queries to AI specialists",
            llm_api_key= os.getenv("ASI1_API_KEY"),
            model= os.getenv("MODEL"),
            base_url= os.getenv("BASE_URL"),
            port=8200,
            mailbox=True,
            agent_configs=self.agent_configs,
            routing_strategy="keyword_match"
        )
        print("✅ Coordinator created!")
        return self.coordinator

    def start_system(self):
        print("🚀 Starting Multi-Agent System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            print(f"🎯 Starting coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            print("👋 Shutting down...")
            self.running = False
        except Exception as e:
            print(f"❌ Error: {e}")
            self.running = False

def main():
    try:
        system = MultiAgentOrchestrator()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Shutdown complete!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()