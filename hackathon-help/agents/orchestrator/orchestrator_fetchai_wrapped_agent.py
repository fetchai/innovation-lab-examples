from datetime import datetime, timezone
from uuid import uuid4

from agents.models.config import ORCHESTRATOR_SEED
from agents.models.models import SharedAgentState
from agents.orchestrator.chat_protocol import chat_proto, generate_orchestrator_response_from_state
from uagents import Agent, Context, Model
from uagents_core.contrib.protocols.chat import ChatMessage, EndSessionContent, TextContent

orchestrator = Agent(
    name="orchestrator",
    seed=ORCHESTRATOR_SEED,
    port=8003,
    mailbox=True,
    publish_agent_details=True,
)

orchestrator.include(chat_proto, publish_manifest=True)


class HealthResponse(Model):
    status: str


class HttpMessagePost(Model):
    content: str


class HttpMessageResponse(Model):
    echo: str


@orchestrator.on_rest_get("/health", HealthResponse)
async def health(ctx: Context) -> HealthResponse:
    """
    REST health check endpoint for the orchestrator agent.

    To connect your agents to a custom frontend, you can expose them through
    REST endpoints like this one. Visit the agent's host and port to interact:

        http://localhost:8003/health

    You can add additional REST endpoints using @orchestrator.on_rest_get() or
    @orchestrator.on_rest_post() to build a full API for your frontend to consume.
    """
    return HealthResponse(status="ok healthy")


@orchestrator.on_rest_post("/message", HttpMessagePost, HttpMessageResponse)
async def message(ctx: Context, req: HttpMessagePost) -> HttpMessageResponse:
    """
    REST endpoint to send a message to the orchestrator from any HTTP client.

    To post a message, cURL the agent directly:

    curl -X POST http://localhost:8003/message \
      -H "Content-Type: application/json" \
      -d '{"content": "Hello, orchestrator!"}'

    The agent will respond with the same content echoed back as confirmation.
    You can swap the echo logic here with a call into the agent pipeline to get
    real responses from the orchestrator back to your frontend.
    """
    return HttpMessageResponse(echo=req.content)


@orchestrator.on_message(SharedAgentState)
async def handle_agent_response(ctx: Context, sender: str, state: SharedAgentState):
    """
    Receives the completed SharedAgentState back from a helper agent (e.g. Alice, Bob).
    The orchestrator is the sole bridge between the internal agent flow and ASI:One —
    so once a helper agent finishes, we relay the result directly back to the original user.
    """
    ctx.logger.info(f"Received state back from agent: session={state.chat_session_id}, result={state.result!r}")
    response = generate_orchestrator_response_from_state(state)
    await ctx.send(
        state.user_sender_address,
        ChatMessage(
            timestamp=datetime.now(tz=timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


if __name__ == "__main__":
    orchestrator.run()
