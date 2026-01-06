"""
Agent that integrates uAgents chat protocol with Google ADK.
Queries received via chat protocol are processed by ADK agent.
"""

import os
import yaml
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv

from uagents import Agent, Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent_config import LlmAgentConfig
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables
load_dotenv()

# Constants
FIXED_SESSION_ID = "adk_chat_session_1"
FIXED_USER_ID = "user_1"
APP_NAME = "adk_chat_agent"

# Initialize uAgent
agent = Agent(
    name=APP_NAME,
    seed=APP_NAME,
    port=8005,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner
adk_runner = None

# Track processed messages to prevent duplicates
processed_messages = set()


def initialize_adk_agent():
    """Initialize ADK agent and runner from YAML configuration."""
    global adk_runner

    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    os.environ["GOOGLE_API_KEY"] = api_key
    
    # Load agent configuration
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "root_agent.yaml")
    )
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Agent config not found: {config_path}")
    
    # Load and create agent
    with open(config_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
    
    agent_config = LlmAgentConfig.model_validate(yaml_data)
    adk_agent = LlmAgent.from_config(agent_config, config_path)
    
    # Create runner
    session_service = InMemorySessionService()
    adk_runner = Runner(
        agent=adk_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    return adk_runner


def _extract_text_from_event(event):
    """Extract text from ADK event."""
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


async def _ensure_session_exists():
    """Ensure session exists in runner's session service."""
    runner_session_service = adk_runner.session_service
    
    try:
        await runner_session_service.create_session(
            app_name=APP_NAME,
            user_id=FIXED_USER_ID,
            session_id=FIXED_SESSION_ID
        )
    except Exception:
        try:
            await runner_session_service.get_session(
                app_name=APP_NAME,
                user_id=FIXED_USER_ID,
                session_id=FIXED_SESSION_ID
            )
        except Exception:
            pass


async def process_with_adk(query: str) -> str:
    """Process query using ADK runner."""
    global adk_runner
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        await _ensure_session_exists()
        
        # Create message and run
        new_message = types.Content(parts=[types.Part(text=query)])
        response_parts = []
        
        async for event in adk_runner.run_async(
            user_id=FIXED_USER_ID,
            session_id=FIXED_SESSION_ID,
            new_message=new_message
        ):
            text = _extract_text_from_event(event)
            if text:
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
        ctx.logger.info("ADK agent initialized successfully")
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
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id
        )
        await ctx.send(sender, ack)
        
        # Process query and send response
        response_text = await process_with_adk(text_content)
        
        response = ChatMessage(
            timestamp=datetime.utcnow(),
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
            timestamp=datetime.utcnow(),
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
