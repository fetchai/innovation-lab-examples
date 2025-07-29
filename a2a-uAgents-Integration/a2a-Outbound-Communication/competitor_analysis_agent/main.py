import os
from typing import Dict, List
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers # Import from your fixed adapter
from competitor_analysis_executor import CompetitorAnalysisExecutor # NEW: Import the new executor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class CompetitorAnalysisSystem:
    """
    Manages the setup and execution of the A2A Competitor Analysis agent.
    """
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        """
        Configures the A2AAgentConfig and AgentExecutor for the competitor analysis agent.
        """
        print("🔧 Setting up Competitor Analysis Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="competitor_analysis_specialist",
                description="AI Agent for comprehensive competitor analysis and market intelligence.",
                url="http://localhost:10020", # The URL where the A2A server for this agent will run
                port=10020, # The port for the A2A server
                specialties=[
                    "competitor analysis", "market intelligence", "SWOT analysis",
                    "strategic recommendations", "industry research", "product comparison"
                ],
                priority=3
            )
        ]
        self.executors = {
            "competitor_analysis_specialist": CompetitorAnalysisExecutor() # NEW: Use the new executor
        }
        print("✅ Competitor Analysis Agent configuration created")

    def start_individual_a2a_servers(self):
        """
        Starts the individual A2A server for the competitor analysis agent.
        """
        print("🔄 Starting Competitor Analysis server...")
        a2a_servers(self.agent_configs, self.executors)
        print("✅ Competitor Analysis server started!")

    def create_coordinator(self):
        """
        Creates the SingleA2AAdapter (uAgent coordinator) for the competitor analysis agent.
        """
        print("🤖 Creating Competitor Analysis Coordinator...")
        
        # Get the executor instance
        competitor_executor = self.executors.get("competitor_analysis_specialist")
        if competitor_executor is None:
            raise ValueError("CompetitorAnalysisExecutor not found in executors dictionary.")

        self.coordinator = SingleA2AAdapter(
            agent_executor=competitor_executor,
            name="competitor_analysis_coordinator",
            description="Coordinator for routing competitor analysis queries to the specialist agent.",
            port=8200, # The port for the uAgent coordinator
            mailbox=True
        )
        print("✅ Competitor Analysis Coordinator created!")
        return self.coordinator

    def start_system(self):
        """
        Orchestrates the entire system startup process.
        """
        print("🚀 Starting Competitor Analysis System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            print(f"🎯 Starting Competitor Analysis coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            print("👋 Shutting down Competitor Analysis system...")
            self.running = False
        except Exception as e:
            print(f"❌ Error during system startup: {e}")
            self.running = False

def main():
    """
    Main function to run the Competitor Analysis A2A system.
    """
    # Set the UAGENT_MESSAGE_TIMEOUT environment variable
    os.environ["UAGENT_MESSAGE_TIMEOUT"] = os.getenv("UAGENT_MESSAGE_TIMEOUT", "300") # Default to 300 seconds (5 minutes)

    try:
        system = CompetitorAnalysisSystem()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Competitor Analysis system shutdown complete!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
