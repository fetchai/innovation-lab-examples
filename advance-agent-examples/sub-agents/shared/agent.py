
import os
from google.adk.agents import Agent
from google.adk.agents.llm_agent import ToolUnion

from google.genai import types
from google.adk.runners import Runner
from google.adk.planners import BuiltInPlanner
from google.adk.sessions import InMemorySessionService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents.context_cache_config import ContextCacheConfig
from pydantic import BaseModel, ConfigDict
from google.adk.artifacts import GcsArtifactService

from shared.executor import BaseAgentExecutor
from shared.runner import AgentRunner

class AgentManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    GOOGLE_STORAGE_BUCKET_NAME: str
    GOOGLE_API_KEY: str
    ASI_API_KEY: str
    NAME: str
    MODEL: str
    DESCRIPTION: str
    INSTRUCTION: str
    APP_NAME: str
    URL: str
    AGENT_PORT: int
    A2A_PORT: int
    COORDINATOR_PORT: int
    SEED: str
    CACHE_MIN_TOKENS: int
    CACHE_TTL_SECONDS: int
    CACHE_INTERVALS: int
    COMPACTION_INTERVAL: int
    COMPACTION_OVERLAP: int
    SPECIALTIES: list[str]

    agent: Agent | None = None
    session_service: InMemorySessionService | None = None
    app: App | None = None
    executor: BaseAgentExecutor | None = None
    runner: AgentRunner | None = None

    @staticmethod
    def load(agent_key: str) -> "AgentManager":
        prefix: str = agent_key.upper().replace(" ", "_")
        
        required_vars = [
            # shared settings
            "GOOGLE_STORAGE_BUCKET_NAME",
            "GOOGLE_API_KEY",
            "ASI_API_KEY",

            # agent specific settings
            f"{prefix}_NAME",
            f"{prefix}_MODEL",
            f"{prefix}_DESCRIPTION",
            f"{prefix}_INSTRUCTION",
            f"{prefix}_APP_NAME",
            f"{prefix}_URL",
            f"{prefix}_AGENT_PORT",
            f"{prefix}_A2A_PORT",
            f"{prefix}_COORDINATOR_PORT",
            f"{prefix}_SEED",
            f"{prefix}_SPECIALTIES",

            # common settings
            "AGENT_CACHE_MIN_TOKENS",
            "AGENT_CACHE_TTL_SECONDS",
            "AGENT_CACHE_INTERVALS",
            "AGENT_COMPACTION_INTERVAL",
            "AGENT_COMPACTION_OVERLAP",
        ]
        env_vars: dict[str, str] = {}
        for var in required_vars:
            value = os.getenv(var)
            if value is None:
                raise ValueError(f"{var} environment variable is required")
            env_vars[var] = value

        return AgentManager(
            # shared settings
            GOOGLE_STORAGE_BUCKET_NAME=env_vars["GOOGLE_STORAGE_BUCKET_NAME"],
            GOOGLE_API_KEY=env_vars["GOOGLE_API_KEY"],
            ASI_API_KEY=env_vars["ASI_API_KEY"],

            # agent specific settings
            NAME=env_vars[f"{prefix}_NAME"],
            MODEL=env_vars[f"{prefix}_MODEL"],
            DESCRIPTION=env_vars[f"{prefix}_DESCRIPTION"],
            INSTRUCTION=env_vars[f"{prefix}_INSTRUCTION"],
            APP_NAME=env_vars[f"{prefix}_APP_NAME"],
            URL=env_vars[f"{prefix}_URL"],
            AGENT_PORT=int(env_vars[f"{prefix}_AGENT_PORT"]),
            A2A_PORT=int(env_vars[f"{prefix}_A2A_PORT"]),
            COORDINATOR_PORT=int(env_vars[f"{prefix}_COORDINATOR_PORT"]),
            SEED=env_vars[f"{prefix}_SEED"],
            SPECIALTIES=[
                s.strip() for s in env_vars[f"{prefix}_SPECIALTIES"].split(",")
            ],

            # common settings
            CACHE_MIN_TOKENS=int(env_vars["AGENT_CACHE_MIN_TOKENS"]),
            CACHE_TTL_SECONDS=int(env_vars["AGENT_CACHE_TTL_SECONDS"]),
            CACHE_INTERVALS=int(env_vars["AGENT_CACHE_INTERVALS"]),
            COMPACTION_INTERVAL=int(env_vars["AGENT_COMPACTION_INTERVAL"]),
            COMPACTION_OVERLAP=int(env_vars["AGENT_COMPACTION_OVERLAP"]),
        )
    
    def get_agent(self, tools: list[ToolUnion]) -> Agent:
        """Helper to get the Agent."""
        if self.agent:
            return self.agent

        self.agent = Agent(
            model=self.MODEL,
            name=self.NAME,
            description=self.DESCRIPTION,
            instruction=self.INSTRUCTION,
            tools=tools,
            planner=BuiltInPlanner(
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MEDIUM
                )
            )
        )
        return self.agent

    def get_session_service(self) -> InMemorySessionService:
        """Helper to get the session service."""
        if self.session_service:
            return self.session_service
        self.session_service = InMemorySessionService()
        return self.session_service

    def get_app(self, tools: list[ToolUnion]) -> App:
        """Helper to get the App."""
        return App(
            name=self.NAME,
            root_agent=self.get_agent(tools=tools),
            context_cache_config=ContextCacheConfig(
                min_tokens=self.CACHE_MIN_TOKENS,
                ttl_seconds=self.CACHE_TTL_SECONDS,
                cache_intervals=self.CACHE_INTERVALS
            ),
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=self.COMPACTION_INTERVAL,
                overlap_size=self.COMPACTION_OVERLAP
            )
        )

    def get_runner(self, tools: list[ToolUnion]) -> Runner:
        """Helper to get a Runner."""
        if self.app is None:
            self.app = self.get_app(tools=tools)
        return Runner(
            app=self.app,
            session_service=self.get_session_service(),
            artifact_service=GcsArtifactService(
                bucket_name=self.GOOGLE_STORAGE_BUCKET_NAME
            )
        )
    
    def get_executor(self, tools: list[ToolUnion]) -> BaseAgentExecutor:
        """Helper to get the Agent Executor."""
        if self.executor:
            return self.executor
        self.executor = BaseAgentExecutor(
            app=self.get_app(tools=tools),
            session_service=self.get_session_service()
        )
        return self.executor
    
    def get_agent_runner(self, tools: list[ToolUnion]) -> AgentRunner:
        """Helper to get the Agent Runner."""
        if self.runner:
            return self.runner
        self.runner = AgentRunner(
            agent_name=self.NAME,
            agent_description=self.DESCRIPTION,
            agent_url=self.URL,
            agent_port=self.AGENT_PORT,
            coordinator_port=self.COORDINATOR_PORT,
            a2a_port=self.A2A_PORT,
            agent_seed=self.SEED,
            specialties=self.SPECIALTIES,
            executor=self.get_executor(tools=tools)
        )
        return self.runner
    
    def run_agent(self, tools: list[ToolUnion]) -> None:
        """Run the Agent."""
        runner = self.get_agent_runner(tools=tools)
        runner.run()

__all__ = ["AgentManager"]