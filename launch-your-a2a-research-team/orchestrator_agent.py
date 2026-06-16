import os
from uuid import uuid4

import httpx
import uvicorn
from a2a.client import A2AClient, A2ACardResolver
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.apps import A2AStarletteApplication
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)
from a2a.utils import new_agent_text_message
from dotenv import load_dotenv
from uagents_core.adapters.a2a import agentverse_sdk

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "9999"))
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL", f"http://localhost:{ORCHESTRATOR_PORT}"
).rstrip("/")
AGENT_NAME = os.getenv("AGENT_NAME", "A2A Research Team Orchestrator")
AGENTVERSE_AGENT_URI = os.getenv("AGENTVERSE_AGENT_URI", "").strip()

RESEARCH_AGENT_URL = os.getenv("RESEARCH_AGENT_URL", "http://localhost:10001")
ANALYSIS_AGENT_URL = os.getenv("ANALYSIS_AGENT_URL", "http://localhost:10002")
SUMMARY_AGENT_URL = os.getenv("SUMMARY_AGENT_URL", "http://localhost:10003")

if AGENTVERSE_AGENT_URI:
    agentverse_sdk.init(AGENTVERSE_AGENT_URI)


def _extract_text_from_parts(parts) -> str:
    text_chunks: list[str] = []
    for part in parts or []:
        root = getattr(part, "root", None)
        if root is not None and hasattr(root, "text"):
            text_chunks.append(root.text)
            continue
        if hasattr(part, "text"):
            text_chunks.append(part.text)
    return "\n".join(chunk.strip() for chunk in text_chunks if chunk and chunk.strip())


def _extract_text_from_response(response) -> str:
    if not isinstance(response.root, SendMessageSuccessResponse):
        raise ValueError("Remote agent returned a non-success A2A response.")

    result = response.root.result
    if isinstance(result, Message):
        return _extract_text_from_parts(result.parts)

    if isinstance(result, Task):
        if result.status and result.status.message:
            text = _extract_text_from_parts(result.status.message.parts)
            if text:
                return text
        if result.artifacts:
            artifact_texts = [
                _extract_text_from_parts(artifact.parts)
                for artifact in result.artifacts
            ]
            final_text = "\n\n".join(text for text in artifact_texts if text)
            if final_text:
                return final_text

    raise ValueError("Remote agent response did not contain readable text.")


async def call_remote_agent(agent_url: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=90) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()
        client = A2AClient(
            httpx_client=httpx_client, agent_card=agent_card, url=agent_url
        )

        payload = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
                "messageId": uuid4().hex,
            }
        }
        request = SendMessageRequest(
            id=uuid4().hex,
            params=MessageSendParams(**payload),
        )
        response = await client.send_message(request)
        return _extract_text_from_response(response)


class OrchestratorAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input().strip()
        print(f"[orchestrator_agent] incoming user request: {user_text!r}")

        research_prompt = (
            "Create research notes for the following user request.\n\n"
            f"User request:\n{user_text}"
        )
        research_notes = await call_remote_agent(RESEARCH_AGENT_URL, research_prompt)
        print("[orchestrator_agent] research step complete")

        analysis_prompt = (
            "Analyze the following research notes for the original user request.\n\n"
            f"User request:\n{user_text}\n\n"
            f"Research notes:\n{research_notes}"
        )
        analysis_notes = await call_remote_agent(ANALYSIS_AGENT_URL, analysis_prompt)
        print("[orchestrator_agent] analysis step complete")

        summary_prompt = (
            "Create the final user-facing answer using the material below.\n\n"
            f"User request:\n{user_text}\n\n"
            f"Research notes:\n{research_notes}\n\n"
            f"Analysis:\n{analysis_notes}"
        )
        final_answer = await call_remote_agent(SUMMARY_AGENT_URL, summary_prompt)
        print("[orchestrator_agent] summary step complete")

        await event_queue.enqueue_event(
            new_agent_text_message(
                final_answer,
                context_id=context.context_id or str(uuid4()),
                task_id=context.task_id or str(uuid4()),
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


agent_card = AgentCard(
    name=AGENT_NAME,
    description="Coordinates multiple Gemini-powered A2A research agents.",
    url=PUBLIC_BASE_URL,
    version="0.1.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="research_orchestration",
            name="Research Orchestration",
            description="Delegates research, analysis, and summarization to worker agents.",
            examples=[
                "Research electric vehicle adoption in India",
                "Give me a brief on AI regulation in Europe",
            ],
            tags=["a2a", "orchestrator", "research", "gemini"],
        )
    ],
)

handler = DefaultRequestHandler(
    agent_executor=OrchestratorAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=handler,
).build()


if __name__ == "__main__":
    print(f"[orchestrator_agent] public base URL: {PUBLIC_BASE_URL}")
    print(
        "[orchestrator_agent] Agentverse bridge enabled:"
        f" {'yes' if AGENTVERSE_AGENT_URI else 'no'}"
    )
    print(
        "[orchestrator_agent] worker urls:"
        f" research={RESEARCH_AGENT_URL},"
        f" analysis={ANALYSIS_AGENT_URL},"
        f" summary={SUMMARY_AGENT_URL}"
    )
    uvicorn.run(app, host=HOST, port=ORCHESTRATOR_PORT)
