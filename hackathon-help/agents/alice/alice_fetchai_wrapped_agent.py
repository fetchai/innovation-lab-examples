from agents.models.config import ALICE_SEED
from agents.models.models import SharedAgentState
from uagents import Agent, Context

alice = Agent(
    name="alice",
    seed=ALICE_SEED,
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)


def super_cool_alice_workflow(state: SharedAgentState) -> SharedAgentState:
    """
    In a real implementation, this is where Alice's specialized agentic workflow lives.
    Think LangGraph state machines, LangChain pipelines, external API calls, tool use,
    RAG retrieval — whatever Alice is an expert at. She receives the shared state,
    executes her workflow against state.query, and writes the final output to
    state.result before returning. That mutation is how her work gets communicated
    back to the orchestrator and ultimately to the user.
    """
    state.result = f"Hello, this is Alice! Your message was: {state.query}"
    return state


@alice.on_message(SharedAgentState)
async def handle_message(ctx: Context, sender: str, state: SharedAgentState):
    ctx.logger.info(f"Received state from orchestrator: session={state.chat_session_id}, query={state.query!r}")
    state = super_cool_alice_workflow(state)
    await ctx.send(sender, state)


if __name__ == "__main__":
    alice.run()
