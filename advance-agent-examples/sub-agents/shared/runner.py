"""
Main entry point for the Time Agent with A2A Outbound Adapter.
This exposes the agent on Agentverse for discovery and communication.
"""
import logging
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from uagents_adapter import A2AAgentConfig, SingleA2AAdapter, a2a_servers
from shared.executor import BaseAgentExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Runner for the Agent with A2A Outbound Adapter.
    """

    def __init__(
        self,
        agent_name: str,
        agent_description: str,
        agent_url: str,
        agent_port: int,
        coordinator_port: int,
        a2a_port: int,
        agent_seed: str,
        specialties: list[str],
        executor: BaseAgentExecutor,
    ) -> None:
        self.agent_configs: list[A2AAgentConfig] = []
        self.executors: dict[str, Any] = {}
        self.running = False
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.agent_port = agent_port
        self.coordinator_port = coordinator_port
        self.a2a_port = a2a_port
        self.agent_seed = agent_seed
        self.specialties = specialties
        self.agent_url = agent_url
        self.agent_configs = [
            A2AAgentConfig(
                name=self.agent_name,
                description=self.agent_description,
                url=self.agent_url,
                port=self.agent_port,
                specialties=self.specialties,
            )
        ]
        self.executors = {self.agent_name: executor}
        logger.info("AgentRunner initialized for agent: %s", self.agent_name)

    def run(self) -> None:
        logger.info("Starting agent: %s", self.agent_name)
        try:
            logger.info("Starting A2A servers for agent configs")
            a2a_servers(self.agent_configs, self.executors)
            executor = self.executors.get(self.agent_name)
            if executor is None:
                logger.error("Executor for agent %s not found", self.agent_name)
                raise ValueError(f"Executor for agent {self.agent_name} not found")
            logger.info(
                "Creating SingleA2AAdapter coordinator on port %d", self.coordinator_port
            )
            coordinator = SingleA2AAdapter(
                agent_executor=executor,
                name=self.agent_name,
                description=self.agent_description,
                port=self.coordinator_port,
                mailbox=True,
                seed=self.agent_seed,
                a2a_port=self.a2a_port,
            )
            self.running = True
            logger.info("Agent %s is now running", self.agent_name)
            coordinator.run()
        except KeyboardInterrupt:
            logger.info("Agent %s stopped by user", self.agent_name)
            self.running = False
        except Exception as e:
            logger.exception("Error running agent %s: %s", self.agent_name, e)
            self.running = False

__all__ = ["AgentRunner"]