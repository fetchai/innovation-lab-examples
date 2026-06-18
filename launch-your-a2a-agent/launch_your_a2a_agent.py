import os
from uuid import uuid4

from dotenv import load_dotenv
from uagents_core.adapters.a2a import agentverse_sdk

load_dotenv()

AGENTVERSE_A2A_URI = os.getenv("AGENTVERSE_AGENT_URI", "").strip()
if AGENTVERSE_A2A_URI:
    agentverse_sdk.init(AGENTVERSE_A2A_URI)

import uvicorn  # noqa: E402
from a2a.server.agent_execution import AgentExecutor, RequestContext  # noqa: E402
from a2a.server.events import EventQueue  # noqa: E402
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler  # noqa: E402
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore  # noqa: E402
from a2a.server.apps import A2AStarletteApplication  # noqa: E402
from a2a.types import AgentCapabilities, AgentCard, AgentSkill  # noqa: E402
from a2a.utils import new_agent_text_message  # noqa: E402


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "9999"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}").rstrip("/")
AGENT_NAME = os.getenv("AGENT_NAME", "Launch Your A2A Agent")


class HelloWorldExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input().strip()
        print(f"[launch_your_a2a_agent] incoming message: {user_text!r}")
        if not user_text:
            user_text = "world"

        reply = f"Hello, {user_text}!"

        await event_queue.enqueue_event(
            new_agent_text_message(
                reply,
                context_id=context.context_id or str(uuid4()),
                task_id=context.task_id or str(uuid4()),
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported in this hello-world example")


agent_card = AgentCard(
    name=AGENT_NAME,
    description="A minimal hello-world A2A agent for Agentverse onboarding demos.",
    url=PUBLIC_BASE_URL,
    version="0.1.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="hello_world",
            name="Hello World",
            description="Returns a simple hello greeting.",
            tags=["hello", "greeting", "demo", "a2a"],
            examples=["hello", "say hi", "introduce yourself"],
        )
    ],
)

handler = DefaultRequestHandler(
    agent_executor=HelloWorldExecutor(),
    task_store=InMemoryTaskStore(),
)

app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=handler,
).build()


if __name__ == "__main__":
    print(f"[launch_your_a2a_agent] public base URL: {PUBLIC_BASE_URL}")
    print(
        "[launch_your_a2a_agent] Agentverse bridge enabled:"
        f" {'yes' if AGENTVERSE_A2A_URI else 'no'}"
    )
    uvicorn.run(app, host=HOST, port=PORT)
