"""
Router Agent for Multi-Agent System
Routes user requests to specialized agents based on the task

This agent:
- Receives requests from users via ASI One
- Uses Claude to analyze what the user needs
- Routes to Vision Agent (images) or MCP Agent (GitHub/Airbnb/tools)
- Receives responses from specialized agents
- Sends final response back to user

Simple 3-agent architecture:
    User → Router Agent → Vision Agent / MCP Agent → Router Agent → User
"""

import os
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Optional
from dotenv import load_dotenv
from anthropic import Anthropic

from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    ResourceContent,
    chat_protocol_spec
)

# Load environment variables
load_dotenv()

# Configure Anthropic Claude
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

client = Anthropic(api_key=anthropic_api_key)

# Model configuration
MODEL_NAME = 'claude-3-5-sonnet-20241022'
MAX_TOKENS = 1024
TEMPERATURE = 0.7

# Create router agent
router = Agent(
    name="router",
    seed="router-agent-seed-phrase-12345",
    port=8005,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Agent addresses (UPDATE THESE when you run the specialized agents!)
VISION_AGENT_ADDRESS = "agent1qv7cf6qk25dej5vztevnd3mw5m06xhdxq58ql68lc22drt5wggq9wqxawpp"  # Vision agent
MCP_AGENT_ADDRESS = "agent1q0ed0f5czkrn7rdkndcjpkh2rf045nt4mmpc5mfnjlq2gtagq4tyv4cplwd"     # MCP agent

# Track pending requests
pending_requests: Dict[str, Dict] = {}


# Custom message model for agent responses
class AgentResponse(Model):
    """Response from a specialized agent"""
    request_id: str
    result: str
    agent_type: str


def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )


async def analyze_request(query: str, has_image: bool) -> str:
    """Use Claude to determine which agent should handle the request"""
    
    # If there's an image, definitely use vision agent
    if has_image:
        return "vision"
    
    # Use Claude to classify text requests
    classification_prompt = f"""You are a router for a multi-agent system. Analyze this user request and determine which agent should handle it.

Available agents:
- vision: Handles image analysis, visual questions, OCR, object detection
- mcp: Handles GitHub queries, Airbnb searches, database queries, file operations

User request: "{query}"

Respond with ONLY ONE WORD: either "vision" or "mcp"
"""

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=10,
            temperature=0,
            messages=[{
                "role": "user",
                "content": classification_prompt
            }]
        )
        
        decision = response.content[0].text.strip().lower()
        
        # Validate decision
        if decision not in ["vision", "mcp"]:
            # Default to mcp for unknown
            return "mcp"
        
        return decision
        
    except Exception as e:
        print(f"Error classifying request: {e}")
        # Default to mcp on error
        return "mcp"


@router.on_event("startup")
async def startup(ctx: Context):
    """Initialize router agent"""
    ctx.logger.info("🔀 Starting Router Agent...")
    ctx.logger.info(f"📍 Router address: {router.address}")
    ctx.logger.info(f"👁️  Vision Agent: {VISION_AGENT_ADDRESS}")
    ctx.logger.info(f"🔧 MCP Agent: {MCP_AGENT_ADDRESS}")
    
    # Initialize storage
    ctx.storage.set("total_requests", 0)
    ctx.storage.set("vision_requests", 0)
    ctx.storage.set("mcp_requests", 0)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming messages - either from users or from specialized agents"""
    
    # Check if this is a response from a specialized agent
    if sender in [VISION_AGENT_ADDRESS, MCP_AGENT_ADDRESS]:
        # This is a RESPONSE from a specialized agent
        ctx.logger.info(f"📨 Response received from specialized agent ({sender[:12]}...)")
        
        # Extract the response text
        response_text = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                response_text = item.text
                break
        
        if not response_text:
            ctx.logger.warning("No text in agent response")
            return
        
        # Find the original request
        if pending_requests:
            # Get the most recent request
            request_id = list(pending_requests.keys())[-1]
            request_info = pending_requests[request_id]
            
            original_sender = request_info["original_sender"]
            
            ctx.logger.info(f"← Sending response back to user ({original_sender[:12]}...)")
            
            # Send response back to original user
            await ctx.send(original_sender, create_text_chat(response_text))
            
            # Clean up
            del pending_requests[request_id]
            
            ctx.logger.info("✅ Request completed!")
        else:
            ctx.logger.warning("No pending request found for this response")
        
        return
    
    # Otherwise, this is a REQUEST from a user
    try:
        # Extract text and check for images
        user_text = ""
        has_image = False
        
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
            elif isinstance(item, ResourceContent):
                has_image = True
        
        if not user_text and not has_image:
            ctx.logger.warning("No content in message")
            return
        
        ctx.logger.info(f"📨 Request from user ({sender[:12]}...): {user_text[:50]}...")
        
        # Send acknowledgement to user
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Decide which agent to route to
        target_agent = await analyze_request(user_text, has_image)
        
        ctx.logger.info(f"🔀 Routing to: {target_agent} agent")
        
        # Update stats
        total = ctx.storage.get("total_requests") or 0
        ctx.storage.set("total_requests", total + 1)
        
        if target_agent == "vision":
            count = ctx.storage.get("vision_requests") or 0
            ctx.storage.set("vision_requests", count + 1)
            target_address = VISION_AGENT_ADDRESS
        else:  # mcp
            count = ctx.storage.get("mcp_requests") or 0
            ctx.storage.set("mcp_requests", count + 1)
            target_address = MCP_AGENT_ADDRESS
        
        # Create request ID to track this request
        request_id = str(uuid4())
        
        # Store request info
        pending_requests[request_id] = {
            "original_sender": sender,
            "original_message": msg,
            "target_agent": target_agent,
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Forward message to specialized agent
        ctx.logger.info(f"→ Forwarding to {target_agent} agent ({target_address[:12]}...)")
        await ctx.send(target_address, msg)
        
    except Exception as e:
        ctx.logger.error(f"❌ Error routing request: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        error_msg = f"Sorry, I encountered an error routing your request: {str(e)}"
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include chat protocol
router.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🔀 Starting Router Agent...")
    print(f"📍 Router address: {router.address}")
    print()
    print("🎯 This agent routes requests to specialized agents:")
    print(f"   👁️  Vision Agent: {VISION_AGENT_ADDRESS}")
    print(f"   🔧 MCP Agent: {MCP_AGENT_ADDRESS}")
    print()
    print("📝 IMPORTANT: Make sure to:")
    print("   1. Start the Vision Agent (port 8002)")
    print("   2. Start the MCP Agent (port 8004)")
    print("   3. Update agent addresses in this file if they changed")
    print()
    print("✅ Router is running on port 8005")
    print("   Send requests via ASI One to this router!")
    print("   Press Ctrl+C to stop.\n")
    
    router.run()
