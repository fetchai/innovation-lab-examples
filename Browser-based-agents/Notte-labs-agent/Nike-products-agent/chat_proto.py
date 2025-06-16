"""
Chat protocol implementation for enabling text-based communication between Nike Scraper Agent and ASI1 LLM.
"""

from datetime import datetime
from uuid import uuid4
from typing import Any

from uagents import Context, Model, Protocol

# Import the necessary components of the chat protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from nike_scraper import get_nike_info_enhanced, NikeScrapeRequest, NikeScrapeResponse

# Replace the AI Agent Address with one of the LLMs that support StructuredOutput
# OpenAI Agent: agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y
# Claude.ai Agent: agent1qvk7q2av3e2y5gf5s90nfzkc8a48q3wdqeevwrtgqfdl0k78rspd6f2l4dx
AI_AGENT_ADDRESS = 'agent1qtlpfshtlcxekgrfcpmv7m9zpajuwu7d5jfyachvpa4u3dkt6k0uwwp2lct'

if not AI_AGENT_ADDRESS:
    raise ValueError("AI_AGENT_ADDRESS not set")


def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    """Create a text chat message with optional end session marker."""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )


chat_proto = Protocol(spec=chat_protocol_spec)
struct_output_client_proto = Protocol(
    name="StructuredOutputClientProtocol", version="0.1.0"
)


class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]


class StructuredOutputResponse(Model):
    output: dict[str, Any]


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages from ASI1 LLM."""
    # Log only if the first content item is TextContent
    if msg.content and isinstance(msg.content[0], TextContent):
        ctx.logger.info(f"Got a message from {sender}: {msg.content[0].text}")
    elif msg.content and isinstance(msg.content[0], StartSessionContent):
        ctx.logger.info(f"Got a start session message from {sender}")
    else:
        ctx.logger.info(f"Got a message from {sender} with non-text initial content.")
    ctx.storage.set(str(ctx.session), sender)
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            continue
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Got a message from {sender}: {item.text}")
            ctx.storage.set(str(ctx.session), sender)
            await ctx.send(
                AI_AGENT_ADDRESS,
                StructuredOutputPrompt(
                    prompt=item.text, output_schema=NikeScrapeRequest.schema()
                ),
            )
        else:
            ctx.logger.info(f"Got unexpected content from {sender}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements for chat messages."""
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )


@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_structured_output_response(
    ctx: Context, sender: str, msg: StructuredOutputResponse
):
    """Handle structured output responses from the AI agent."""
    session_sender = ctx.storage.get(str(ctx.session))
    if session_sender is None:
        ctx.logger.error(
            "Discarding message because no session sender found in storage"
        )
        return

    # Check for empty or clearly invalid output from LLM
    if not msg.output or "<UNKNOWN>" in str(msg.output) or not isinstance(msg.output, dict) or not msg.output.get('action'):
        await ctx.send(
            session_sender,
            create_text_chat(
                "Sorry, I couldn't understand your Nike product request. Please try asking about Nike categories or products."
            ),
        )
        return

    try:
        # Parse the structured output from the LLM
        try:
            request = NikeScrapeRequest.parse_obj(msg.output)
        except Exception as p_err: # Catch Pydantic validation errors or others
            ctx.logger.error(f"Error parsing LLM output: {msg.output}. Error: {p_err}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I received an invalid response structure from the AI. Please try rephrasing your request."
                ),
            )
            return
        
        # Get the Nike information based on the structured request
        nike_response = await get_nike_info_enhanced(request=request)
        
        # Send the response back to the user
        chat_message = create_text_chat(nike_response.results)
        await ctx.send(session_sender, chat_message)
        
    except Exception as err:
        ctx.logger.error(f"Error processing Nike request: {err}")
        await ctx.send(
            session_sender,
            create_text_chat(
                "Sorry, I couldn't process your Nike product request. Please try again with a simpler query."
            ),
        )
