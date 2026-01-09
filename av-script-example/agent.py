"""
Example Agent Script with Agentverse Registration and ASI One Integration
"""

import os
import requests
import traceback
from datetime import datetime
from uuid import uuid4

from uagents import Agent, Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)
from dotenv import load_dotenv

load_dotenv()

UAGENT_NAME = "ExampleAgent"
SEED_PHRASE = os.getenv("AGENT_SEED_PHRASE", "example-agent-seed-phrase-123")
AGENTVERSE_KEY = os.getenv("AGENTVERSE_KEY")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8006"))
HOSTING_ENDPOINT = os.getenv("HOSTING_ENDPOINT")

agent = Agent(
    name=UAGENT_NAME,
    seed=SEED_PHRASE,
    port=AGENT_PORT,
    mailbox=True
)

chat_proto = Protocol(spec=chat_protocol_spec)

README = """# Example Agent 🤖

An example agent that demonstrates Agentverse registration, chat protocol, and ASI One API integration.

## Features

- **Agentverse Registration**: Automatically registers with Agentverse for discoverability
- **Chat Protocol**: Full chat protocol implementation with session management
- **ASI One Integration**: Uses ASI One API for AI-powered responses
- **Multi-turn conversations**: Supports session-based chat interactions

## Prerequisites

- Python 3.10+
- ASI One API key
- Agentverse API key (optional, for registration)

## Usage

### Run Locally

```bash
python agent.py
```

The agent will start on `http://0.0.0.0:8006`

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"What is agentic AI?"
"Explain machine learning"
"Hello, how are you?"
```

## Technology Stack

- **uAgents**: Chat protocol communication and agent-to-agent messaging
- **ASI One API**: AI-powered responses
- **Agentverse**: Agent discovery and registration
"""


def call_asi_one_api(user_message: str) -> str:
    url = "https://api.asi1.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ASI_ONE_API_KEY}"
    }
    data = {
        "model": "asi1-mini",
        "messages": [{"role": "user", "content": user_message}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        return "Sorry, I couldn't generate a response."
    except requests.exceptions.RequestException as e:
        return f"Error calling ASI One API: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent())
    
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Received message from {sender}")
    
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id
        )
    )
    
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Session started with {sender}")
            welcome_message = create_text_chat("Hello! I'm an example agent. How can I help you?")
            await ctx.send(sender, welcome_message)
        
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Text message from {sender}: {item.text}")
            
            if ASI_ONE_API_KEY:
                try:
                    ai_response = call_asi_one_api(item.text)
                    response_message = create_text_chat(ai_response)
                except Exception as e:
                    ctx.logger.error(f"Error calling ASI One API: {e}")
                    response_message = create_text_chat("Sorry, I encountered an error processing your request.")
            else:
                response_message = create_text_chat(
                    f"Hello from Agent! You said: {item.text}\n\n"
                    "Note: ASI_ONE_API_KEY not configured. Set it to enable AI-powered responses."
                )
            
            await ctx.send(sender, response_message)
        
        elif isinstance(item, EndSessionContent):
            ctx.logger.info(f"Session ended with {sender}")
            goodbye_message = create_text_chat("Goodbye! Thanks for chatting.", end_session=True)
            await ctx.send(sender, goodbye_message)
        
        else:
            ctx.logger.info(f"Received unexpected content type from {sender}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info(f"🚀 Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    
    if AGENTVERSE_KEY and SEED_PHRASE:
        try:
            endpoint_url = HOSTING_ENDPOINT
            if not endpoint_url and hasattr(agent, '_endpoints') and agent._endpoints:
                endpoint_url = agent._endpoints[0].url
            elif not endpoint_url:
                endpoint_url = f"http://localhost:{AGENT_PORT}"
            
            ctx.logger.info(f"Registering with Agentverse using endpoint: {endpoint_url}")
            
            register_chat_agent(
                "Example Agent",
                endpoint_url,
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=AGENTVERSE_KEY,
                    agent_seed_phrase=SEED_PHRASE,
                ),
                readme=README,
                description="An example agent demonstrating Agentverse registration, chat protocol, and ASI One API integration."
            )
            ctx.logger.info("✅ Registered with Agentverse")
        except Exception as e:
            ctx.logger.error(f"❌ Failed to register with Agentverse: {e}")
            ctx.logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        missing = []
        if not AGENTVERSE_KEY:
            missing.append("AGENTVERSE_KEY")
        if not SEED_PHRASE:
            missing.append("AGENT_SEED_PHRASE")
        ctx.logger.warning(f"⚠️ {', '.join(missing)} not set, skipping Agentverse registration")
    
    if ASI_ONE_API_KEY:
        ctx.logger.info("✅ ASI One API key configured")
    else:
        ctx.logger.warning("⚠️ ASI_ONE_API_KEY not set, AI responses will be disabled")


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
