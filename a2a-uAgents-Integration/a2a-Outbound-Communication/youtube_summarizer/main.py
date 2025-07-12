import logging
from typing import Dict, Any
from agent_executor import SummarizerAgentExecutor
from uagents_adapter import SingleA2AAdapter, A2AAgentConfig, a2a_servers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YoutubeSummarizerSystem:
    def __init__(self):
        self.coordinator = None
        self.agent_configs = []
        self.executors = {}
        self.running = False

    def setup_agents(self):
        logger.info("🔧 Setting up YouTube Summarizer Agent")
        self.agent_configs = [
            A2AAgentConfig(
                name="youtube_summarizer",
                description="AI Agent for summarizing YouTube videos using closed captions",
                url="http://localhost:10030",
                port=10030,
                specialties=["youtube", "video summarization", "transcription", "content analysis"],
                priority=3,
                examples=[
                    "Summarize this YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "Provide a summary of the key points in this tutorial video",
                ],
            )
        ]
        self.executors = {"youtube_summarizer": SummarizerAgentExecutor()}
        logger.info("✅ YouTube Summarizer Agent configuration created")
        self._print_agent_card()

    def _print_agent_card(self):
        """Prints a formatted agent card with system details."""
        print("\n" + "="*50)
        print("📋 YouTube Summarizer Agent Card")
        print("="*50)
        print(f"Name: {self.agent_configs[0].name}")
        print(f"Description: {self.agent_configs[0].description}")
        print(f"URL: {self.agent_configs[0].url}")
        print(f"Port: {self.agent_configs[0].port}")
        print(f"Specialties: {', '.join(self.agent_configs[0].specialties)}")
        print(f"Status: {'Running' if self.running else 'Stopped'}")
        print("="*50 + "\n")

    def start_individual_a2a_servers(self):
        logger.info("🔄 Starting YouTube Summarizer server...")
        executors: Dict[str, Any] = self.executors
        a2a_servers(self.agent_configs, executors)
        logger.info("✅ YouTube Summarizer server started!")

    def create_coordinator(self):
        logger.info("🤖 Creating YouTube Summarizer Coordinator...")
        executor = self.executors.get("youtube_summarizer")
        if executor is None:
            raise ValueError("SummarizerAgentExecutor not found in executors dictionary.")
        self.coordinator = SingleA2AAdapter(
            agent_executor=executor,
            name="youtube_summarizer_coordinator",
            description="Coordinator for routing YouTube video summarization queries",
            port=8300,
            mailbox=True,
        )
        logger.info("✅ YouTube Summarizer Coordinator created!")
        return self.coordinator

    def start_system(self):
        logger.info("🚀 Starting YouTube Summarizer System")
        try:
            self.setup_agents()
            self.start_individual_a2a_servers()
            coordinator = self.create_coordinator()
            self.running = True
            logger.info(f"🎯 Starting YouTube Summarizer coordinator on port {coordinator.port}...")
            coordinator.run()
        except KeyboardInterrupt:
            logger.info("👋 Shutting down YouTube Summarizer system...")
            self.running = False
            self._print_agent_card()
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            self.running = False
            self._print_agent_card()

if __name__ == "__main__":
    system = YoutubeSummarizerSystem()
    system.start_system()