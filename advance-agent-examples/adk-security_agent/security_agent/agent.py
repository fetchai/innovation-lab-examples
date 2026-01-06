"""
Security & Guardrails Agent

Prompt Engineering is NOT a Security Strategy.
Asking an LLM nicely to "please ignore PII" is wishful thinking, not governance.

This agent integrates uAgents chat protocol with Google ADK to demonstrate
defense-in-depth security strategy:

1. Model Armor (Infrastructure Layer): Global protection against PII, hate speech, jailbreaks
2. Identity Verification (Storage Layer): User role management (student/developer/enterprise/business/robot)
3. Security Callbacks (Developer Layer): Role-based access control and custom business logic
4. Monitoring Plugins (Observability Layer): Audit logging and security event tracking

Architecture:
- uAgents: Chat protocol and identity storage
- ADK Runner: Agent execution with callbacks and plugins
- Model Armor: Infrastructure-level security (configured separately)
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

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import our modules
import sys
sys.path.insert(0, os.path.dirname(__file__))
from app_setup import agent as security_agent, plugin
from callback_and_plugins import set_session_state, clear_session_state

# Load environment variables
load_dotenv()

# Constants
APP_NAME = "security_guardrails_app"
USER_ID = "user_default"
SESSION_ID = "session_01"
UAGENT_NAME = "security_guardrails_chat_agent"

# Initialize uAgent
agent = Agent(
    name=UAGENT_NAME,
    seed=UAGENT_NAME,
    port=8008,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner and session service
adk_runner = None
session_service = None

# Track processed messages
processed_messages = set()
processed_content = {}  # key: (sender, content_hash), value: timestamp

# In-memory storage for user identities (fallback if ctx.storage is not available)
user_identities = {}  # key: sender address, value: identity dict


def initialize_adk_agent():
    """Initialize ADK Runner with security agent, plugins, and session service."""
    global adk_runner, session_service
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create session service
    session_service = InMemorySessionService()
    
    # Create Runner with agent
    # Note: Runner uses the agent's callback (before_agent_callback)
    # Plugins would need to be handled differently, but callbacks work with Runner
    adk_runner = Runner(
        agent=security_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    # Ensure session_service reference is correct (use runner's session_service)
    if hasattr(adk_runner, 'session_service'):
        session_service = adk_runner.session_service
    
    return adk_runner


async def _ensure_session_exists(user_id: str = USER_ID, session_id: str = SESSION_ID):
    """Ensure session exists in session service."""
    global adk_runner, session_service
    
    # Use runner's session service if available, otherwise use global
    service = adk_runner.session_service if adk_runner and hasattr(adk_runner, 'session_service') else session_service
    
    if service is None:
        return
    
    try:
        await service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
    except Exception as e:
        # Session might already exist, try to get it
        try:
            await service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            # If get also fails, that's okay - runner will create session if needed
            # Some ADK versions auto-create sessions
            pass


def _extract_text_from_event(event):
    """Extract text from ADK event."""
    # Check if it's a final response
    if hasattr(event, 'is_final_response'):
        if callable(event.is_final_response):
            if event.is_final_response():
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
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
        if content is None:
            pass
        elif isinstance(content, list):
            for item in content:
                if hasattr(item, 'text') and item.text:
                    return item.text
                if isinstance(item, str):
                    return item
                if hasattr(item, 'parts') and item.parts:
                    for part in item.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text
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


async def process_with_adk(query: str, user_id: str = USER_ID, session_id: str = SESSION_ID, user_state: dict = None) -> str:
    """
    Process query using ADK Runner with security guardrails.
    
    Args:
        query: User query
        user_id: ADK user ID
        session_id: ADK session ID
        user_state: User identity state (role, permissions, etc.)
    """
    global adk_runner
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        # Store state for callbacks to access (before session creation)
        state = user_state if user_state else {}
        set_session_state(user_id, session_id, state)
        
        # Ensure session exists with correct user_id and session_id
        # Note: Some ADK versions auto-create sessions, but we'll try to create it explicitly
        try:
            await _ensure_session_exists(user_id=user_id, session_id=session_id)
        except Exception as session_error:
            # If session creation fails, continue anyway - runner might auto-create
            pass
        
        # Create message content
        content = types.Content(role='user', parts=[types.Part(text=query)])
        response_parts = []
        
        # Run ADK agent (callbacks will access state via get_session_state)
        # Runner will create session automatically if it doesn't exist
        try:
            async for event in adk_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                text = _extract_text_from_event(event)
                if text and text.strip() and text not in response_parts:
                    response_parts.append(str(text))
            
            return ' '.join(response_parts).strip() if response_parts else "No response from security agent"
        finally:
            # Clean up state after processing
            clear_session_state(user_id, session_id)
        
    except Exception as e:
        error_msg = str(e)
        # Clean up state on error
        clear_session_state(user_id, session_id)
        return f"Error processing query: {error_msg}"


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize ADK agent on startup."""
    ctx.logger.info(f"Security Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    try:
        initialize_adk_agent()
        ctx.logger.info("ADK security agent with guardrails and plugins initialized successfully")
        
        # Check Model Armor configuration
        model_armor_template = os.getenv("MODEL_ARMOR_TEMPLATE", "security_guardrails_template")
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "fetch-ai-innovation-lab")
        location = os.getenv("MODEL_ARMOR_LOCATION", "us-central1")
        
        ctx.logger.info(f"Model Armor Template: projects/{project_id}/locations/{location}/templates/{model_armor_template}")
        ctx.logger.info("Note: Model Armor applies automatically at infrastructure level if configured")
        
    except Exception as e:
        ctx.logger.error(f"Failed to initialize ADK security agent: {str(e)}")


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with security guardrails."""
    global processed_messages, processed_content
    import hashlib
    import time
    
    # Check if message already processed by msg_id
    message_key = f"{sender}:{msg.msg_id}"
    if message_key in processed_messages:
        ctx.logger.debug(f"Duplicate message ignored (by msg_id): {msg.msg_id}")
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
        
        # Check for duplicate content within last 5 seconds
        content_hash = hashlib.md5(f"{sender}:{text_content}".encode()).hexdigest()
        content_key = (sender, content_hash)
        current_time = time.time()
        
        if content_key in processed_content:
            time_diff = current_time - processed_content[content_key]
            if time_diff < 5.0:
                ctx.logger.debug(f"Duplicate message ignored (by content): {text_content[:50]}...")
                return
        
        # Mark message as processed
        processed_messages.add(message_key)
        processed_content[content_key] = current_time
        
        # Clean old entries
        if len(processed_content) > 100:
            cutoff_time = current_time - 60
            processed_content = {k: v for k, v in processed_content.items() if v > cutoff_time}
        
        ctx.logger.info(f"Received query from {sender}: {text_content[:100]}...")
        
        # Send acknowledgement first
        ack = ChatAcknowledgement(
            timestamp=datetime.datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id
        )
        await ctx.send(sender, ack)
        
        # Check if user identity is stored (try uAgents storage first, fallback to in-memory)
        storage_key = f"user_{sender}"
        stored_identity = None
        
        # Try to get from uAgents storage
        try:
            if hasattr(ctx, 'storage') and ctx.storage is not None:
                stored_identity = await ctx.storage.get(storage_key)
        except (AttributeError, TypeError) as e:
            ctx.logger.debug(f"Storage not available: {e}")
        except Exception as e:
            ctx.logger.debug(f"Could not access ctx.storage: {e}")
        
        # Fallback to in-memory storage
        if stored_identity is None:
            stored_identity = user_identities.get(sender)
        
        user_state = {}
        user_role = None
        
        if stored_identity:
            # User already identified - use stored identity
            user_role = stored_identity.get("role", "student")
            user_state = {
                "user_role": user_role,
                "user_id": stored_identity.get("user_id", sender),
                "user_name": stored_identity.get("name", "User"),
                "permissions": stored_identity.get("permissions", []),
                "student_profile": user_role == "student"
            }
            ctx.logger.info(f"User identified from storage: {user_state.get('user_name')} ({user_role})")
            
            # Process the query normally
            # (continue to process_with_adk below)
        else:
            # First time user - check if they're providing identity
            identity_query = text_content.strip().lower()
            valid_roles = ["student", "developer", "enterprise", "business", "robot"]
            
            if identity_query in valid_roles:
                # User provided their identity
                user_role = identity_query
                user_name = user_role.capitalize()
                
                # Set permissions based on role
                if user_role == "developer":
                    permissions = ["read", "ask_questions", "admin_access", "system_config"]
                elif user_role in ["enterprise", "business"]:
                    permissions = ["read", "ask_questions", "admin_access"]
                elif user_role == "robot":
                    permissions = ["read", "ask_questions", "automated_access"]
                else:  # student
                    permissions = ["read", "ask_questions"]
                
                # Store identity (try uAgents storage first, fallback to in-memory)
                identity_data = {
                    "role": user_role,
                    "user_id": sender,
                    "name": user_name,
                    "permissions": permissions
                }
                
                # Try to store in uAgents storage
                try:
                    if hasattr(ctx, 'storage') and ctx.storage is not None:
                        await ctx.storage.set(storage_key, identity_data)
                except (AttributeError, TypeError) as e:
                    ctx.logger.debug(f"Storage not available: {e}")
                except Exception as e:
                    ctx.logger.debug(f"Could not store in ctx.storage: {e}")
                
                # Always store in in-memory as fallback (persists during agent runtime)
                user_identities[sender] = identity_data
                
                user_state = {
                    "user_role": user_role,
                    "user_id": sender,
                    "user_name": user_name,
                    "permissions": permissions,
                    "student_profile": user_role == "student"
                }
                
                ctx.logger.info(f"User identity stored: {user_name} ({user_role})")
                
                # Send confirmation message
                confirmation = ChatMessage(
                    timestamp=datetime.datetime.utcnow(),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text=f"✅ Thank you! Your identity has been saved as: **{user_name}**. How can I help you today?")]
                )
                await ctx.send(sender, confirmation)
                return
            else:
                # Ask user to identify themselves
                identity_prompt = ChatMessage(
                    timestamp=datetime.datetime.utcnow(),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text="👋 Welcome! Please identify yourself by replying with **one** of the following:\n\n• **student**\n• **developer**\n• **enterprise**\n• **business**\n• **robot**\n\nThis will help me provide you with the appropriate access and assistance.")]
                )
                await ctx.send(sender, identity_prompt)
                return
        
        # Process query with user state (security callbacks will verify user identity)
        # Use a unique session_id per user to avoid conflicts
        adk_user_id = user_state.get("user_id", USER_ID)
        adk_session_id = f"session_{adk_user_id}"  # Unique session per user
        
        response_text = await process_with_adk(
            text_content, 
            user_id=adk_user_id, 
            session_id=adk_session_id,
            user_state=user_state
        )
        
        response = ChatMessage(
            timestamp=datetime.datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response_text)]
        )
        await ctx.send(sender, response)
        ctx.logger.info(f"Sent response to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {str(e)}")
        processed_messages.discard(message_key)
        if 'content_key' in locals():
            processed_content.pop(content_key, None)
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
