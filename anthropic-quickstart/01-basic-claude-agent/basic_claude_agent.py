"""
Basic Claude Agent for Fetch.ai Agentverse
A simple conversational AI agent powered by Anthropic Claude

This agent:
- Receives messages via Fetch.ai protocol
- Processes them with Anthropic Claude
- Sends intelligent responses back
- Maintains conversation context
"""

import os
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec
)

# Load environment variables
load_dotenv()

# Configure Anthropic Claude
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

# Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

# Model configuration
MODEL_NAME = 'claude-3-5-sonnet-20241022'  # Latest Claude 3.5 Sonnet
MAX_TOKENS = 1024
TEMPERATURE = 0.7

# Create agent
agent = Agent(
    name="claude_assistant",
    seed="claude-basic-seed-phrase-12345",  # Change this for your agent
    port=8000,
    mailbox=True  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt - customize this for your use case!
SYSTEM_PROMPT = """You are a helpful AI assistant powered by Anthropic Claude and running on Fetch.ai's decentralized agent network.

You should:
- Be friendly, helpful, and concise
- Provide accurate and thoughtful information
- Admit when you don't know something
- Keep responses focused and relevant
- Think step by step when solving complex problems

Current capabilities:
- Answering questions with deep reasoning
- Providing detailed explanations
- Creative writing and brainstorming
- Problem-solving and analysis
- Code explanation and debugging
- General conversation
"""


# Helper function to create text chat messages
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🤖 Starting Claude Assistant...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        ctx.logger.info("✅ Anthropic Claude API configured")
    else:
        ctx.logger.error("❌ Anthropic API key not set")
    
    # Initialize conversation storage
    ctx.storage.set("total_messages", 0)
    ctx.storage.set("conversations", {})


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""
    
    try:
        # Extract text from message content
        user_text = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break
        
        if not user_text:
            ctx.logger.warning("No text content in message")
            return
        
        # Log incoming message
        ctx.logger.info(f"📨 Message from {sender}: {user_text[:50]}...")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Get conversation history for context
        conversations = ctx.storage.get("conversations") or {}
        history = conversations.get(sender, [])
        
        # Build messages array for Claude API
        messages = []
        
        # Add conversation history (last 5 exchanges for context)
        if history:
            for h in history[-10:]:  # Last 10 messages (5 exchanges)
                messages.append({
                    "role": h['role'],
                    "content": h['text']
                })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_text
        })
        
        # Generate response from Claude
        ctx.logger.info("🤔 Generating response with Claude...")
        
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        # Extract response text
        response_text = response.content[0].text
        
        ctx.logger.info(f"✅ Response generated: {response_text[:50]}...")
        
        # Update conversation history
        history.append({'role': 'user', 'text': user_text})
        history.append({'role': 'assistant', 'text': response_text})
        conversations[sender] = history[-10:]  # Keep last 10 messages
        ctx.storage.set("conversations", conversations)
        
        # Track stats
        total = ctx.storage.get("total_messages") or 0
        ctx.storage.set("total_messages", total + 1)
        
        # Send response back to user
        await ctx.send(sender, create_text_chat(response_text))
        
        ctx.logger.info(f"💬 Response sent to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        
        # Check for specific error types
        error_str = str(e)
        
        if "rate_limit" in error_str.lower() or "429" in error_str:
            error_msg = """⚠️ **Rate Limit Reached**

I've hit the API rate limits. Please wait a moment and try again.

**What to do:**
- ⏰ Wait 1 minute and try again
- 📊 Check your API usage at console.anthropic.com
"""
        elif "api_key" in error_str.lower() or "401" in error_str:
            error_msg = """⚠️ **API Key Error**

There's an issue with the API key configuration.

**Please check:**
- API key is valid
- API key has proper permissions
- Account has available credits
"""
        else:
            error_msg = f"""❌ **Error Processing Message**

{str(e)[:200]}

Please try:
- Rephrasing your question
- Simplifying your request
- Waiting a moment and trying again
"""
        
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message {msg.acknowledged_msg_id} acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🤖 Starting Claude Assistant...")
    print(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        print("✅ Anthropic Claude API configured")
        print(f"   Using model: {MODEL_NAME}")
    else:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        print("   Please add it to your .env file")
        print("   Get your key from: https://console.anthropic.com")
        exit(1)
    
    print("\n🎯 Agent Features:")
    print("   • Conversational AI with Claude 3.5 Sonnet")
    print("   • Advanced reasoning and analysis")
    print("   • Context-aware responses")
    print("   • Conversation history tracking")
    print("   • Ready for Agentverse deployment")
    
    print("\n✅ Agent is running! Connect via ASI One or send messages programmatically.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
