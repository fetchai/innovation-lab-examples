"""
Basic Gemini Agent for Fetch.ai Agentverse
A simple conversational AI agent powered by Google Gemini

This agent:
- Receives messages via Fetch.ai protocol
- Processes them with Google Gemini
- Sends intelligent responses back
- Maintains basic conversation context
"""

import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec
)

# Load environment variables
load_dotenv()

# Configure Gemini
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini client
# The API key is automatically picked up from GEMINI_API_KEY environment variable
client = genai.Client(api_key=gemini_api_key)

# Model configuration
MODEL_NAME = 'gemini-2.5-flash'
GENERATION_CONFIG = {
    'temperature': 0.7,  # Balance creativity and consistency
    'top_p': 0.95,
    'top_k': 40,
    'max_output_tokens': 1024,
}

# Create agent
agent = Agent(
    name="gemini_assistant",
    seed="",  # Change this for your agent to a unique seed phrase
    port=8000,
    mailbox=True  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt - customize this for your use case!
SYSTEM_PROMPT = """You are a helpful AI assistant powered by Google Gemini and running on Fetch.ai's decentralized agent network.

You should:
- Be friendly, helpful, and concise
- Provide accurate information
- Admit when you don't know something
- Keep responses focused and relevant

Current capabilities:
- Answering questions
- Providing explanations
- Creative writing
- Problem-solving
- General conversation

Conversation History (if any):
"""


# Helper function to create text chat messages
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        content=[TextContent(text=text, type="text")]
    )


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🤖 Starting Gemini Assistant...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        ctx.logger.info("✅ Gemini API configured")
    else:
        ctx.logger.error("❌ Gemini API key not set")
    
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
        
        # Build chat contents with history context
        # For simplicity, we'll include recent history in the prompt
        conversation_context = ""
        if history:
            for h in history[-5:]:
                role = "User" if h['role'] == 'user' else "Assistant"
                conversation_context += f"{role}: {h['text']}\n"
        
        # Combine context with current message
        full_prompt = f"{SYSTEM_PROMPT}\n\n{conversation_context}User: {user_text}\nAssistant:"
        
        # Generate response from Gemini
        ctx.logger.info("🤔 Generating response with Gemini...")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
            config=GENERATION_CONFIG
        )
        response_text = response.text
        
        ctx.logger.info(f"✅ Response generated: {response_text[:50]}...")
        
        # Update conversation history
        history.append({'role': 'user', 'text': user_text})
        history.append({'role': 'model', 'text': response_text})
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
        
        # Send error message to user
        error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message {msg.acknowledged_msg_id} acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🤖 Starting Gemini Assistant...")
    print(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        print("✅ Gemini API configured")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        print("   Please add it to your .env file")
        exit(1)
    
    print("\n🎯 Agent Features:")
    print("   • Conversational AI with Gemini 2.5 Flash")
    print("   • Context-aware responses")
    print("   • Conversation history tracking")
    print("   • Ready for Agentverse deployment")
    
    print("\n✅ Agent is running! Connect via ASI One or send messages programmatically.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
