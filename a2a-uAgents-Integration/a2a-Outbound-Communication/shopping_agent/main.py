import os
from typing import Dict, List
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers 
from shopping_agent import ShoppingAgentExecutor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ShoppingPartnerSystem:
    """
    Manages the setup and execution of the A2A Shopping Partner agent.
    """
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        """
        Configures the A2AAgentConfig and AgentExecutor for the shopping partner.
        """
        print("🔧 Setting up Shopping Partner Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="shopping_partner_specialist",
                description="AI Agent for product recommendations and shopping assistance.",
                url="http://localhost:10020", # The URL where the A2A server for this agent will run
                port=10020, # The port for the A2A server
                specialties=[
                    "product recommendations", "shopping", "e-commerce",
                    "fashion", "electronics", "home goods", "sports gear"
                ],
                priority=3 # Priority can be useful in multi-agent setups
            )
        ]
        self.executors = {
            "shopping_partner_specialist": ShoppingAgentExecutor()
        }
        print("✅ Shopping Partner Agent configuration created")

    def start_individual_a2a_servers(self):
        """
        Starts the individual A2A server for the shopping partner agent.
        """
        print("🔄 Starting Shopping Partner server...")
        a2a_servers(self.agent_configs, self.executors)
        print("✅ Shopping Partner server started!")

    def create_coordinator(self):
        """
        Creates the SingleA2AAdapter (uAgent coordinator) for the shopping partner.
        """
        print("🤖 Creating Shopping Partner Coordinator...")
        
        # Get the executor instance
        shopping_executor = self.executors.get("shopping_partner_specialist")
        if shopping_executor is None:
            raise ValueError("ShoppingAgentExecutor not found in executors dictionary.")

        self.coordinator = SingleA2AAdapter(
            agent_executor=shopping_executor,
            name="shopping_partner_coordinator",
            description="Coordinator for routing shopping-related queries to the Shopping Partner Agent.",
            port=8200, # The port for the uAgent coordinator
            mailbox=True
        )
        print("✅ Shopping Partner Coordinator created!")
        return self.coordinator

    def start_system(self):
        """
        Orchestrates the entire system startup process.
        """
        print("🚀 Starting Shopping Partner System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            print(f"🎯 Starting Shopping Partner coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            print("👋 Shutting down Shopping Partner system...")
            self.running = False
        except Exception as e:
            print(f"❌ Error during system startup: {e}")
            self.running = False

def main():
    """
    Main function to run the Shopping Partner A2A system.
    """
    # Set the UAGENT_MESSAGE_TIMEOUT environment variable
    # This tells the uAgent coordinator to wait longer for responses.
    os.environ["UAGENT_MESSAGE_TIMEOUT"] = os.getenv("UAGENT_MESSAGE_TIMEOUT", "120") # Default to 120 seconds

    try:
        system = ShoppingPartnerSystem()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Shopping Partner system shutdown complete!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()