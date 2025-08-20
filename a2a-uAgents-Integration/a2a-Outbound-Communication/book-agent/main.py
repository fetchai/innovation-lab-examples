import os
from threading import Thread
from typing import Dict, List
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers
from books_recommender_agent import BooksRecommenderAgentExecutor
from dotenv import load_dotenv
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class BooksRecommenderSystem:
    """
    Manages the setup and execution of the A2A Books Recommender agent.
    """
    def __init__(self):
        self.coordinator = None
        self.agent_configs: List[A2AAgentConfig] = []
        self.executors: Dict[str, any] = {}
        self.running = False

    def setup_agents(self):
        """
        Configures the A2AAgentConfig and AgentExecutor for the books recommender.
        """
        logger.info("🔧 Setting up Books Recommender Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="books_recommender_specialist",
                description="AI Agent for book recommendations and reading assistance.",
                url="http://localhost:10022",
                port=10022,
                specialties=[
                    "book recommendations", "literature", "fiction", "non-fiction",
                    "genres", "authors", "reading lists", "book reviews"
                ],
                priority=3
            )
        ]
        self.executors = {
            "books_recommender_specialist": BooksRecommenderAgentExecutor()
        }
        logger.info("✅ Books Recommender Agent configuration created")

    def start_individual_a2a_servers(self):
        """
        Starts individual A2A servers for the Books Recommender Agent.
        """
        logger.info("🔄 Starting Books Recommender server...")
        a2a_servers(self.agent_configs, self.executors)
        logger.info("✅ Books Recommender server started!")

    def create_coordinator(self):
        """
        Creates the SingleA2AAdapter (uAgent coordinator) for the books recommender.
        """
        logger.info("🤖 Creating Books Recommender Coordinator...")
        books_executor = self.executors.get("books_recommender_specialist")
        if books_executor is None:
            raise ValueError("BooksRecommenderAgentExecutor not found in executors dictionary.")

        self.coordinator = SingleA2AAdapter(
            agent_executor=books_executor,
            name="books_recommender",
            description="Coordinator for routing book-related queries to the Books Recommender Agent.",
            port=8033,
            mailbox=True,
        )
        logger.info("✅ Books Recommender Coordinator created!")
        return self.coordinator

    def start_system(self):
        """
        Orchestrates the entire system startup process.
        """
        logger.info("🚀 Starting Books Recommender System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            logger.info(f"🎯 Starting Books Recommender coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            logger.info("👋 Shutting down Books Recommender system...")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Error during agent system startup: {e}", exc_info=True)
            self.running = False

def main():
    """
    Main function to run the Books Recommender System in a separate thread.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        system = BooksRecommenderSystem()
        system.start_system()
    except KeyboardInterrupt:
        logger.info("👋 Books Recommender system thread shutdown complete!")
    except Exception as e:
        logger.error(f"❌ An error occurred in agent system thread: {e}", exc_info=True)
        system.running = False
    finally:
        loop.close()

if __name__ == "__main__":
    logger.info("🚀 Starting Books Recommender System...")
    agent_thread = Thread(target=main, daemon=True)
    agent_thread.start()
    # Keep the main thread alive to allow the agent thread to run
    try:
        agent_thread.join()
    except KeyboardInterrupt:
        logger.info("👋 Main thread shutdown complete!")