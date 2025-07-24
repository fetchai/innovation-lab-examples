
from datetime import datetime
from uuid import uuid4
from threading import Thread

from fastapi import FastAPI
import uvicorn

from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# ---------------------
# FastAPI Setup
# ---------------------
app = FastAPI()

@app.get("/ping")
def ping():
    return {"status": "agent is running"}

# ---------------------
# OpenAI / ASI setup
# ---------------------
subject_matter = None

client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key='',
)

agent = Agent(
    name="ASI-agent-gautam",
    seed="ASI-agent-gautam",
    port=8002,  # Port for the agent to listen on
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id))
    text = ''.join([item.text for item in msg.content if isinstance(item, TextContent)])
    
    try:
        r = client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": text},
            ],
            max_tokens=2048,
        )
        response = str(r.choices[0].message.content)
    except Exception:
        ctx.logger.exception('Error querying model')
        response = "I am afraid something went wrong and I am unable to answer your question at the moment"

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=response)],
    ))

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

agent.include(protocol, publish_manifest=True)

# ---------------------
# Start uAgent and FastAPI together
# ---------------------
def run_agent():
    agent.run()

if __name__ == "__main__":
    Thread(target=run_agent).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)  # FastAPI for Render