import os
import logging
from typing import Dict, List
from dotenv import load_dotenv

from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers
from currency_agent_system.agent_executor import CurrencyAgentExecutor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CurrencyAgentRunner")

class CurrencyAgent:
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        logger.info("🔧 Setting up Currency Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="currency_specialist",
                description="Helps with exchange rates for currencies",
                url="http://localhost:10000",
                port=10000,
                specialties=["currency conversion", "currency exchange", "forex rates"],
                priority=2
            )
        ]
        self.executors = {
            "currency_specialist": CurrencyAgentExecutor()
        }
        logger.info("✅ Agent configuration created")

    def start_individual_a2a_servers(self):
        logger.info("🔄 Starting Currency Agent server...")
        a2a_servers(self.agent_configs, self.executors)
        logger.info("✅ Agent server started!")

    def create_coordinator(self):
        logger.info("🤖 Creating Currency Coordinator...")
        self.coordinator = SingleA2AAdapter(
            agent_executor=CurrencyAgentExecutor(),
            name="currency--",
            description="Routes queries to the Currency Agent",
            port=8100,
            mailbox=True
        )
        logger.info(f"✅ Coordinator created on port {self.coordinator.port}")
        return self.coordinator

    def start_system(self):
        logger.info("🚀 Starting Currency Agent System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            logger.info(f"🎯 Starting coordinator on port {coordinator.port}... Press Ctrl+C to stop.")
            coordinator.run()
        except KeyboardInterrupt:
            logger.info("👋 System shutdown by user.")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Error occurred: {e}")
            self.running = False

def main():
    try:
        system = CurrencyAgent()
        system.start_system()
    except KeyboardInterrupt:
        print("👋 Shutdown complete!")
    except Exception as e:
        print(f"❌ Error: {e}")
if __name__ == "__main__":
    main()
