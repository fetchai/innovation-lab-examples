"""
Policy Agent that integrates uAgents chat protocol with ADK.
Uses app_setup.py, steering.py, and chat_handler.py for context management.
"""

import os
import json
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
import os
sys.path.insert(0, os.path.dirname(__file__))
from app_setup import app
from chat_handler import chat
from steering import SteeringInputs, build_turn_instruction

# Load environment variables
load_dotenv()

# Constants
APP_NAME = "policy_qa_app"
USER_ID = "user_default"
SESSION_ID = "session_01"
UAGENT_NAME = "policy_chat_agent"

# Initialize uAgent
agent = Agent(
    name=UAGENT_NAME,
    seed=UAGENT_NAME,
    port=8007,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner and session service
adk_runner = None
session_service = None

# Track processed messages (by msg_id)
processed_messages = set()
# Track processed content (by sender + content + timestamp window) to prevent duplicate processing
processed_content = {}  # key: (sender, content_hash), value: timestamp


def initialize_adk_agent():
    """Initialize ADK runner from app setup."""
    global adk_runner, session_service
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create session service and runner
    session_service = InMemorySessionService()
    adk_runner = Runner(
        app=app,
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
    """Extract text from ADK event - comprehensive extraction."""
    # Check if it's a final response (callable check)
    if hasattr(event, 'is_final_response'):
        if callable(event.is_final_response):
            if event.is_final_response():
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                return part.text
    
    # Check parts attribute (direct)
    if hasattr(event, 'parts') and event.parts:
        for part in event.parts:
            if hasattr(part, 'text') and part.text:
                return part.text
            if isinstance(part, str):
                return part
    
    # Check content attribute (various structures)
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
                # Nested parts
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
    
    # Check for candidate responses (common in Gemini responses)
    if hasattr(event, 'candidates') and event.candidates:
        for candidate in event.candidates:
            if hasattr(candidate, 'content') and candidate.content:
                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text
    
    # Check direct text attribute
    if hasattr(event, 'text') and event.text:
        return event.text
    
    # If event is a string
    if isinstance(event, str):
        return event
    
    # Try to get string representation
    try:
        event_str = str(event)
        if event_str and event_str != str(type(event)):
            # Check if it contains meaningful text (not just object representation)
            if len(event_str) > 20 and not event_str.startswith('<'):
                return event_str
    except:
        pass
    
    return None


def _format_response(response_text: str) -> str:
    """Format JSON response into plain text format (no markdown, no JSON)."""
    if not response_text:
        return response_text
    
    # Try to parse as JSON
    try:
        # Try to find JSON in the response (might have extra text)
        response_text = response_text.strip()
        
        # Try to extract JSON if it's wrapped in code blocks or has extra text
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        
        # Try to find JSON object
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            
            # Format as plain text (no markdown)
            formatted = []
            
            # Answer (remove any markdown formatting)
            if 'answer' in data and data['answer']:
                answer_text = data['answer']
                # Remove markdown formatting from answer
                answer_text = answer_text.replace('**', '').replace('*', '').replace('`', '')
                # Remove markdown links [text](url) -> text
                import re
                answer_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', answer_text)
                formatted.append(answer_text)
            
            # Citations (plain text URLs, no markdown)
            if 'citations' in data and data['citations']:
                citations = data['citations']
                if isinstance(citations, list) and len(citations) > 0:
                    formatted.append("\n\nSources:")
                    for i, citation in enumerate(citations, 1):
                        citation_str = str(citation).strip()
                        # Remove markdown link formatting if present
                        citation_str = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', citation_str)
                        # Just show the URL as plain text
                        formatted.append(f"{i}. {citation_str}")
            
            # Confidence (optional, only if significantly low) - plain text
            if 'confidence' in data and data.get('confidence', 1.0) < 0.7:
                formatted.append(f"\nConfidence: {data['confidence']:.0%}")
            
            return '\n'.join(formatted)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # If not valid JSON or parsing fails, try to clean markdown and return
        import re
        cleaned = response_text
        # Remove markdown formatting
        cleaned = cleaned.replace('**', '').replace('*', '').replace('`', '')
        # Remove markdown links [text](url) -> text (url)
        cleaned = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', cleaned)
        return cleaned
    
    # Return original if not JSON or parsing failed, but clean markdown
    import re
    cleaned = response_text
    cleaned = cleaned.replace('**', '').replace('*', '').replace('`', '')
    cleaned = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', cleaned)
    return cleaned


async def process_with_adk(query: str, session_id: str = SESSION_ID) -> str:
    """Process query using ADK runner with context management."""
    global adk_runner
    import logging
    
    logger = logging.getLogger("policy_agent")
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        await _ensure_session_exists()
        
        # Use chat_handler to build turn instruction
        # This sets up the dynamic instruction based on intent
        chat(session_id, query)
        
        # Create message content
        content = types.Content(role='user', parts=[types.Part(text=query)])
        response_parts = []
        event_count = 0
        
        # Run ADK agent
        async for event in adk_runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=content
        ):
            event_count += 1
            # Debug: log event type
            event_type = type(event).__name__
            logger.debug(f"Received event {event_count}: {event_type}")
            
            # Check for final response first
            if hasattr(event, 'is_final_response') and callable(event.is_final_response):
                if event.is_final_response():
                    logger.debug("Event is final response")
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    if part.text not in response_parts:
                                        response_parts.append(part.text)
                                        logger.debug(f"Added text from final response: {part.text[:100]}")
            
            # Also try to extract text from any event
            text = _extract_text_from_event(event)
            if text and text.strip() and text not in response_parts:
                response_parts.append(str(text))
                logger.debug(f"Added text from event extraction: {text[:100]}")
        
        logger.debug(f"Total events received: {event_count}, Response parts: {len(response_parts)}")
        
        raw_response = ' '.join(response_parts).strip() if response_parts else "No response from ADK agent"
        
        if raw_response == "No response from ADK agent":
            logger.warning(f"No response extracted from {event_count} events")
            # Check if there was an error in the events
            # This might indicate a MALFORMED_FUNCTION_CALL or other error
            return "I encountered an issue processing your query. Please try rephrasing your question or ask again."
        
        # Format the response for better readability
        formatted_response = _format_response(raw_response)
        
        return formatted_response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in process_with_adk: {error_msg}", exc_info=True)
        
        # Check for specific error types
        if "MALFORMED_FUNCTION_CALL" in error_msg or "function" in error_msg.lower():
            return "I encountered an issue with tool usage. Please try rephrasing your question."
        elif "Session" in error_msg:
            return "Session error occurred. Please try again."
        else:
            return f"Error processing query: {error_msg}"


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize ADK agent on startup."""
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    try:
        initialize_adk_agent()
        ctx.logger.info("ADK policy agent initialized successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to initialize ADK agent: {str(e)}")


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with context management."""
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
        
        # Also check for duplicate content within last 5 seconds (to handle mailbox duplicates)
        content_hash = hashlib.md5(f"{sender}:{text_content}".encode()).hexdigest()
        content_key = (sender, content_hash)
        current_time = time.time()
        
        if content_key in processed_content:
            time_diff = current_time - processed_content[content_key]
            if time_diff < 5.0:  # Same content from same sender within 5 seconds
                ctx.logger.debug(f"Duplicate message ignored (by content): {text_content[:50]}... (received {time_diff:.2f}s ago)")
                return
        
        # Mark message as processed (both by ID and content)
        processed_messages.add(message_key)
        processed_content[content_key] = current_time
        
        # Clean old entries from processed_content (keep last 100)
        if len(processed_content) > 100:
            # Remove entries older than 60 seconds
            cutoff_time = current_time - 60
            processed_content = {k: v for k, v in processed_content.items() if v > cutoff_time}
        
        ctx.logger.info(f"Received query from {sender}: {text_content}")
        
        # Send acknowledgement
        ack = ChatAcknowledgement(
            timestamp=datetime.datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id
        )
        await ctx.send(sender, ack)
        
        # Process query with context management
        response_text = await process_with_adk(text_content, session_id=SESSION_ID)
        
        response = ChatMessage(
            timestamp=datetime.datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response_text)]
        )
        await ctx.send(sender, response)
        ctx.logger.info(f"Sent response to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {str(e)}")
        # Remove from processed sets on error so it can be retried
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

