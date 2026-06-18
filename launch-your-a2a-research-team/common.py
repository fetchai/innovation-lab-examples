import os
from uuid import uuid4

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv
from google import genai

load_dotenv()

_gemini_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _gemini_client

    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        _gemini_client = genai.Client(api_key=api_key)

    return _gemini_client


def gemini_generate(system_prompt: str, user_prompt: str) -> str:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=f"{system_prompt.strip()}\n\nUser input:\n{user_prompt.strip()}",
    )
    text = getattr(response, "text", None)
    if text:
        return text.strip()
    return "No response text returned from Gemini."


def build_agent_card(
    *,
    name: str,
    description: str,
    url: str,
    skill_id: str,
    skill_name: str,
    skill_description: str,
    examples: list[str],
    tags: list[str],
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=url.rstrip("/"),
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_name,
                description=skill_description,
                examples=examples,
                tags=tags,
            )
        ],
    )


def build_app(agent_card: AgentCard, agent_executor) -> A2AStarletteApplication:
    handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    ).build()


def extract_text_from_parts(parts) -> str:
    text_chunks: list[str] = []
    for part in parts or []:
        root = getattr(part, "root", None)
        if root is not None and hasattr(root, "text"):
            text_chunks.append(root.text)
            continue
        if hasattr(part, "text"):
            text_chunks.append(part.text)
    return "\n".join(chunk.strip() for chunk in text_chunks if chunk and chunk.strip())


def extract_text_from_send_response(send_response: SendMessageResponse) -> str:
    if not isinstance(send_response.root, SendMessageSuccessResponse):
        raise ValueError("Remote agent returned a non-success A2A response.")

    result = send_response.root.result

    if isinstance(result, Message):
        return extract_text_from_parts(result.parts)

    if isinstance(result, Task):
        if result.status and result.status.message:
            text = extract_text_from_parts(result.status.message.parts)
            if text:
                return text
        if result.artifacts:
            artifact_text = []
            for artifact in result.artifacts:
                artifact_text.append(extract_text_from_parts(artifact.parts))
            final_text = "\n\n".join(chunk for chunk in artifact_text if chunk.strip())
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
        return extract_text_from_send_response(response)
