from datetime import datetime
from uuid import uuid4
import os
from dotenv import load_dotenv
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

load_dotenv()

# Constants
AGENT_NAME = "asi1-agent"
SEED_PHRASE = os.getenv("AGENT_SEED_PHRASE", "av-deploy-example")
AGENTVERSE_KEY = os.getenv("ILABS_AGENTVERSE_API_KEY")

client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key=os.getenv("ASI_API_KEY"),  
)

agent = Agent(
    name=AGENT_NAME,
    seed=SEED_PHRASE,
    port=8001,
    mailbox=True,
    handle_messages_concurrently=True
)

protocol = Protocol(spec=chat_protocol_spec)

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    response = "Sorry, I wasn’t able to process that."
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant. Answer user queries clearly and politely."},
                {"role": "user", "content": text},
            ],
            max_tokens=2048,
        )
        response = str(r.choices[0].message.content)
    except:
        ctx.logger.exception("Error querying model")

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=response),
            EndSessionContent(type="end-session"),
        ]
    ))

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

agent.include(protocol, publish_manifest=True)

README = """# ASI1 Agent

![tag:asi1-llm-agent](https://img.shields.io/badge/asi1-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

An AI assistant powered by ASI1 that can help answer questions and process queries using advanced AI capabilities.

## Features

- **AI-powered responses**: Uses ASI API for intelligent conversation
- **Chat protocol support**: Compatible with uAgents chat protocol
- **Session management**: Handles multi-turn conversations

## Usage

Send messages to the agent via ASI1 or direct chat protocol to interact with the AI assistant.
"""

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize agent and register with Agentverse on startup."""
    ctx.logger.info(f"🚀 Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    
    # Register with Agentverse
    if AGENTVERSE_KEY and SEED_PHRASE:
        try:
            register_chat_agent(
                AGENT_NAME,
                agent._endpoints[0].url,
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=AGENTVERSE_KEY,
                    agent_seed_phrase=SEED_PHRASE,
                ),
                readme=README,
                description="An AI assistant powered by ASI1 that can help answer questions and process queries using advanced AI capabilities."
            )
            ctx.logger.info("✅ Registered with Agentverse")
        except Exception as e:
            ctx.logger.error(f"Failed to register with Agentverse: {e}")
    else:
        ctx.logger.warning("⚠️ AGENTVERSE_KEY or SEED_PHRASE not set, skipping Agentverse registration")

if __name__ == "__main__":
    agent.run()