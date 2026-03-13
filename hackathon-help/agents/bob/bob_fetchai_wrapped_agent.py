from agents.models.config import BOB_SEED
from agents.models.models import SharedAgentState
from uagents import Agent, Context

bob = Agent(
    name="bob",
    seed=BOB_SEED,
    port=8002,
    mailbox=True,
    publish_agent_details=True,
)


def super_cool_bob_workflow(state: SharedAgentState) -> SharedAgentState:
    """
    In a real implementation, this is where Bob's specialized agentic workflow lives.
    Think LangGraph state machines, LangChain pipelines, external API calls, tool use,
    RAG retrieval — whatever Bob is an expert at. He receives the shared state,
    executes his workflow against state.query, and writes the final output to
    state.result before returning. That mutation is how his work gets communicated
    back to the orchestrator and ultimately to the user.
    """
    state.result = f"Hello, this is Bob! Your message was: {state.query}"
    return state


@bob.on_message(SharedAgentState)
async def handle_message(ctx: Context, sender: str, state: SharedAgentState):
    ctx.logger.info(f"Received state from orchestrator: session={state.chat_session_id}, query={state.query!r}")
    state = super_cool_bob_workflow(state)
    await ctx.send(sender, state)


if __name__ == "__main__":
    bob.run()
