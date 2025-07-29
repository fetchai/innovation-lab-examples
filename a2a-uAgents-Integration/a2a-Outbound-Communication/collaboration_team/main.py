import os
from typing import Dict, List
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers 
from collaboration_team import DiscussionTeamExecutor 
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DiscussionTeamSystem:
    """
    Manages the setup and execution of the A2A Discussion Team agent.
    """
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        """
        Configures the A2AAgentConfig and AgentExecutor for the discussion team.
        """
        print("🔧 Setting up Discussion Team Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="discussion_team_specialist",
                description="AI Team for comprehensive research and discussion across various platforms (Reddit, HackerNews, Academic, Twitter).",
                url="http://localhost:10020", # The URL where the A2A server for this agent will run
                port=10020, # The port for the A2A server
                specialties=[
                    "research", "discussion", "consensus building", "social media analysis",
                    "academic research", "tech news", "community insights"
                ],
                priority=3
            )
        ]
        self.executors = {
            "discussion_team_specialist": DiscussionTeamExecutor() # NEW: Use the new executor
        }
        print("✅ Discussion Team Agent configuration created")

    def start_individual_a2a_servers(self):
        """
        Starts the individual A2A server for the discussion team agent.
        """
        print("🔄 Starting Discussion Team server...")
        a2a_servers(self.agent_configs, self.executors)
        print("✅ Discussion Team server started!")

    def create_coordinator(self):
        """
        Creates the SingleA2AAdapter (uAgent coordinator) for the discussion team.
        """
        print("🤖 Creating Discussion Team Coordinator...")
        
        # Get the executor instance
        discussion_executor = self.executors.get("discussion_team_specialist")
        if discussion_executor is None:
            raise ValueError("DiscussionTeamExecutor not found in executors dictionary.")

        self.coordinator = SingleA2AAdapter(
            agent_executor=discussion_executor,
            name="discussion_team_coordinator",
            description="Coordinator for routing discussion topics to the specialist team.",
            port=8200, # The port for the uAgent coordinator
            mailbox=True
        )
        print("✅ Discussion Team Coordinator created!")
        return self.coordinator

    def start_system(self):
        """
        Orchestrates the entire system startup process.
        """
        print("🚀 Starting Discussion Team System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            print(f"🎯 Starting Discussion Team coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            print("👋 Shutting down Discussion Team system...")
            self.running = False
        except Exception as e:
            print(f"❌ Error during system startup: {e}")
            self.running = False

def main():
    """
    Main function to run the Discussion Team A2A system.
    """
    # Set the UAGENT_MESSAGE_TIMEOUT environment variable
    # This tells the uAgent coordinator to wait longer for responses.
    os.environ["UAGENT_MESSAGE_TIMEOUT"] = os.getenv("UAGENT_MESSAGE_TIMEOUT", "600") # Default to 600 seconds (10 minutes)

    try:
        system = DiscussionTeamSystem()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Discussion Team system shutdown complete!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
