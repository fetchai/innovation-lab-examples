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
load_dotenv()
client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key=os.getenv("ASI_API_KEY"),  
)

agent = Agent(
    name="ASI-agent-gautam",
    seed="ASI-agent-gautam",
    port=8001,
    mailbox=True,
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
            model="asi1-mini",
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
if __name__ == "__main__":
    agent.run()
