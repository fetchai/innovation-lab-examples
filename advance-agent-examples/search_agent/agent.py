"""
Search Agent that integrates uAgents chat protocol with Google ADK.
This agent has Google Search capability and processes queries via ADK.
"""

import os
import datetime
from uuid import uuid4
from dotenv import load_dotenv

from uagents import Agent, Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

from google.adk.agents import Agent as ADKAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types

# Load environment variables
load_dotenv()

# Constants
APP_NAME = "simple_search_agent"
USER_ID = "user_default"
SESSION_ID = "session_01"
UAGENT_NAME = "search_chat_agent"

# Initialize uAgent
agent = Agent(
    name=UAGENT_NAME,
    seed=UAGENT_NAME,
    port=8006,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner and session service
adk_runner = None
session_service = None

# Track processed messages to prevent duplicates
processed_messages = set()


def initialize_adk_agent():
    """Initialize ADK agent with Google Search tool."""
    global adk_runner, session_service
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create ADK agent with only google_search tool
    # Note: Custom tools (get_weather, get_current_time) cause function calling errors
    # Using only google_search which is a built-in ADK tool that works reliably
    root_agent = ADKAgent(
        name="search_agent",
        model="gemini-3-pro-preview",
        description="A helpful assistant that can search Google for current information.",
        instruction="""
        You are a helpful assistant with access to Google Search.
        
        If the user asks a question that requires current information, facts, weather, time, or any real-time data, use the 'google_search' tool to find the answer.
        Always cite your sources implicitly by providing the answer clearly based on the search results.
        """,
        tools=[google_search]
    )
    
    # Create session service and runner
    session_service = InMemorySessionService()
    adk_runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    return adk_runner


async def _ensure_session_exists():
    """Ensure session exists in session service."""
    try:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID
        )
    except Exception:
        try:
            await session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=SESSION_ID
            )
        except Exception:
            pass


def _extract_text_from_event(event):
    """Extract text from ADK event."""
    # Check if it's a final response
    if hasattr(event, 'is_final_response') and event.is_final_response():
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
    
    # Check parts attribute
    if hasattr(event, 'parts') and event.parts:
        for part in event.parts:
            if hasattr(part, 'text') and part.text:
                return part.text
            if isinstance(part, str):
                return part
    
    # Check content attribute
    if hasattr(event, 'content'):
        content = event.content
        if isinstance(content, list):
            for item in content:
                if hasattr(item, 'text') and item.text:
                    return item.text
                if isinstance(item, str):
                    return item
        elif hasattr(content, 'text') and content.text:
            return content.text
        elif hasattr(content, 'parts') and content.parts:
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
    
    # Check direct text attribute
    if hasattr(event, 'text') and event.text:
        return event.text
    
    # If event is a string
    if isinstance(event, str):
        return event
    
    return None


async def process_with_adk(query: str) -> str:
    """Process query using ADK runner with Google Search."""
    global adk_runner
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        await _ensure_session_exists()
        
        # Create message content
        content = types.Content(role='user', parts=[types.Part(text=query)])
        response_parts = []
        
        # Run ADK agent
        async for event in adk_runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content
        ):
            # Check for final response
            if hasattr(event, 'is_final_response') and event.is_final_response():
                if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_parts.append(part.text)
            
            # Extract text from event
            text = _extract_text_from_event(event)
            if text and text not in response_parts:
                response_parts.append(str(text))
        
        return ' '.join(response_parts).strip() if response_parts else "No response from ADK agent"
        
    except Exception as e:
        return f"Error processing query: {str(e)}"


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize ADK agent on startup."""
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    try:
        initialize_adk_agent()
        ctx.logger.info("ADK search agent initialized successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to initialize ADK agent: {str(e)}")


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and process with ADK."""
    global processed_messages
    
    # Check if message already processed
    message_key = f"{sender}:{msg.msg_id}"
    if message_key in processed_messages:
        ctx.logger.debug(f"Duplicate message ignored: {msg.msg_id}")
        return
    
    try:
        # Extract text content
        text_content = None
        for item in msg.content:
            if isinstance(item, TextContent):
                text_content = item.text
                break
        
        if not text_content:
            ctx.logger.warning("Received message with no text content")
            return
        
        # Mark message as processed
        processed_messages.add(message_key)
        
        ctx.logger.info(f"Received query from {sender}: {text_content}")
        
        # Send acknowledgement
        ack = ChatAcknowledgement(
            timestamp=datetime.datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id
        )
        await ctx.send(sender, ack)
        
        # Process query and send response
        response_text = await process_with_adk(text_content)
        
        response = ChatMessage(
            timestamp=datetime.datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response_text)]
        )
        await ctx.send(sender, response)
        ctx.logger.info(f"Sent response to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {str(e)}")
        # Remove from processed set on error so it can be retried
        processed_messages.discard(message_key)
        error_msg = ChatMessage(
            timestamp=datetime.datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=f"Error: {str(e)}")]
        )
        await ctx.send(sender, error_msg)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle received acknowledgements."""
    ctx.logger.info(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")


# Include chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()

