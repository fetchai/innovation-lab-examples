"""
Claude Vision Agent for Fetch.ai Agentverse
An AI agent that can analyze and understand images using Claude's vision capabilities

This agent:
- Receives text and images via Fetch.ai protocol
- Analyzes images with Claude 3.5 Sonnet (vision)
- Provides detailed descriptions and answers questions about images
- Supports multiple image input methods (URL, base64, ResourceContent)
"""

import os
import base64
import re
import requests
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic

from uagents import Agent, Context, Protocol
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

# Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

# Model configuration - Claude 3.5 Sonnet supports vision
MODEL_NAME = 'claude-3-5-sonnet-20241022'  # Latest stable version
MAX_TOKENS = 2048  # Longer responses for detailed image analysis
TEMPERATURE = 0.7

# Create agent
agent = Agent(
    name="claude_vision",
    seed="claude-vision-seed-phrase-12345",  # Change this for your agent
    port=8002,
    mailbox=True  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI vision assistant powered by Claude 3.5 Sonnet, running on Fetch.ai's decentralized network.

You can analyze images and provide:
- Detailed descriptions of what you see
- Answers to specific questions about images
- Text extraction (OCR)
- Object identification
- Scene analysis
- Creative interpretations

When analyzing images:
- Be thorough and accurate
- Point out interesting details
- Provide context when relevant
- Answer questions precisely
- Admit if you're uncertain about something
"""


# Helper function to create text chat messages
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )


async def download_image_from_uri(uri: str, ctx: Context) -> bytes:
    """Download image from URI and return bytes"""
    try:
        if uri.startswith('http://') or uri.startswith('https://'):
            # Direct HTTP/HTTPS URL with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ClaudeVisionBot/1.0; +https://fetch.ai)'
            }
            response = requests.get(uri, timeout=10, headers=headers)
            response.raise_for_status()
            return response.content
        elif uri.startswith('agent-storage://'):
            # Agentverse storage - would need proper implementation
            ctx.logger.warning(f"Agent storage URI not fully implemented: {uri}")
            # For now, return None - in production, implement proper storage access
            return None
        else:
            ctx.logger.warning(f"Unsupported URI scheme: {uri}")
            return None
    except Exception as e:
        ctx.logger.error(f"Error downloading image from {uri}: {e}")
        return None


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')


def get_image_media_type(image_bytes: bytes) -> str:
    """Detect image media type from bytes"""
    # Check magic numbers for common formats
    if image_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return "image/gif"
    elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
        return "image/webp"
    else:
        return "image/jpeg"  # Default fallback


def extract_image_urls(text: str) -> list[str]:
    """Extract image URLs from text"""
    # Pattern to match common image URLs
    url_pattern = r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp)'
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    return urls


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("👁️ Starting Claude Vision Agent...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        ctx.logger.info("✅ Claude Vision API configured")
    else:
        ctx.logger.error("❌ Anthropic API key not set")
    
    # Initialize storage
    ctx.storage.set("total_messages", 0)
    ctx.storage.set("total_images", 0)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with optional images"""
    
    try:
        # Extract text and images from message
        user_text = ""
        images = []
        
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
            elif isinstance(item, ResourceContent):
                # Handle image resources
                ctx.logger.info(f"📸 Received image resource: {item.resource_id}")
                
                # Try to download the image
                # Handle both single resource and list of resources
                resources = item.resource if isinstance(item.resource, list) else [item.resource]
                
                for resource in resources:
                    if resource and hasattr(resource, 'uri') and resource.uri:
                        image_bytes = await download_image_from_uri(resource.uri, ctx)
                        if image_bytes:
                            images.append(image_bytes)
                            ctx.logger.info(f"✅ Downloaded image ({len(image_bytes)} bytes)")
        
        # Extract image URLs from text if present
        if user_text:
            image_urls = extract_image_urls(user_text)
            for url in image_urls:
                ctx.logger.info(f"🔗 Found image URL in text: {url}")
                image_bytes = await download_image_from_uri(url, ctx)
                if image_bytes:
                    images.append(image_bytes)
                    ctx.logger.info(f"✅ Downloaded image from URL ({len(image_bytes)} bytes)")
        
        # Default prompt if no text provided
        if not user_text and images:
            user_text = "What do you see in this image? Provide a detailed description."
        
        if not user_text and not images:
            ctx.logger.warning("No text or images in message")
            return
        
        # Log incoming message
        ctx.logger.info(f"📨 Message from {sender}: {user_text[:50]}...")
        if images:
            ctx.logger.info(f"📸 With {len(images)} image(s)")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Build messages array for Claude API
        message_content = []
        
        # Add images first (Claude prefers images before text)
        for img_bytes in images:
            img_base64 = image_to_base64(img_bytes)
            media_type = get_image_media_type(img_bytes)
            
            message_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": img_base64
                }
            })
        
        # Add text
        message_content.append({
            "type": "text",
            "text": user_text
        })
        
        # Generate response from Claude
        ctx.logger.info("🤔 Analyzing with Claude Vision...")
        
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": message_content
            }]
        )
        
        # Extract response text
        response_text = response.content[0].text
        
        ctx.logger.info(f"✅ Response generated: {response_text[:50]}...")
        
        # Track stats
        total_msgs = ctx.storage.get("total_messages") or 0
        ctx.storage.set("total_messages", total_msgs + 1)
        
        if images:
            total_imgs = ctx.storage.get("total_images") or 0
            ctx.storage.set("total_images", total_imgs + len(images))
        
        # Send response back to user
        await ctx.send(sender, create_text_chat(response_text))
        
        ctx.logger.info(f"💬 Response sent to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
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
        elif "image" in error_str.lower() or "media" in error_str.lower():
            error_msg = """⚠️ **Image Processing Error**

I had trouble processing the image.

**Please try:**
- Using a different image format (JPEG, PNG, WebP, GIF)
- Ensuring the image is under 5MB
- Checking the image URL is accessible
- Sending the image again
"""
        else:
            error_msg = f"""❌ **Error Processing Message**

{str(e)[:200]}

Please try:
- Rephrasing your question
- Sending a different image
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
    print("👁️ Starting Claude Vision Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        print("✅ Claude Vision API configured")
        print(f"   Using model: {MODEL_NAME}")
    else:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        print("   Please add it to your .env file")
        print("   Get your key from: https://console.anthropic.com")
        exit(1)
    
    print("\n🎯 Agent Features:")
    print("   • Image analysis with Claude 3.5 Sonnet Vision")
    print("   • Detailed scene descriptions")
    print("   • Text extraction (OCR)")
    print("   • Object identification")
    print("   • Visual Q&A")
    print("   • Multiple image input methods")
    
    print("\n📸 Supported Image Formats:")
    print("   • JPEG, PNG, WebP, GIF")
    print("   • Max size: 5MB per image")
    print("   • URLs and base64 encoding")
    
    print("\n✅ Agent is running! Send images via ASI One to analyze them.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
