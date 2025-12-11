from datetime import datetime
from brand_agent.main import build_main_graph
from uagents import Model 
from langchain_core.load import dumps
from brand_agent.brand_agent_helpers import *
from utils.chat_helpers import *
from utils.db_helpers import get_most_recent_state_from_agent_db
from brand_agent.brand_agent_state_model import initialize_agent_state
from uuid import uuid4
import os
from chroma.chroma_helpers import *
from dotenv import load_dotenv
from uagents.setup import fund_agent_if_low
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

agent = Agent(
    name="Ryans Brand Agent",
    seed=os.getenv("BRAND_AGENT_SEED"),
    port=8081,
    mailbox=True,
)

fund_agent_if_low(str(agent.wallet.address()))

protocol = Protocol(spec=chat_protocol_spec)
graph = build_main_graph()

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    # region Simple parsing input and getting chat metadata
    chat_id = get_chat_id_from_message(msg)
    human_input = get_human_input_from_message(msg)

    # This should never execute. If it does, something is very wrong lol
    if chat_id is None:
        ctx.logger.error("No chat id found in message")
        return

    # This should never execute. If it does, something is very wrong lol
    if human_input is None:
        ctx.logger.error("No human input found in message")
        return
    # endregion

    # region Initializing the langgraph state, invoking the graph, then updating the state
    current_state = get_most_recent_state_from_agent_db(chat_id, ctx)
    if current_state is None:
        current_state = initialize_agent_state(sender, agent.address)

    current_state["messages"].append(HumanMessage(content=human_input))
    result = graph.invoke(current_state)
    json_result = dumps(result)
    ai_response = result["messages"][-1].content
    ctx.storage.set(chat_id, json_result)
    # endregion

    # region Sending the response back to the user through ASI:One
    if is_sent_by_asione(msg):
         # Save the updated state to the database
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.now(),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=ai_response),

                # This will end the chat session after one interaction
                # EndSessionContent(type="end-session") 
            ]
        ))
    # endregion


class Response(Model):
    text: str

@agent.on_rest_get("/", Response)
async def handle_get(ctx: Context):
    ctx.logger.info("Received GET request")
    return {
        "text": "Hello from the Brand Agent Get handler!",
    }

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

# I believe you have to have this to register it to AgentVerse
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()