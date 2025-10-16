"""
Imagen Agent for Fetch.ai Agentverse
An AI agent that generates images using Google Imagen

This agent:
- Receives text prompts via Fetch.ai protocol
- Generates images with Google Imagen
- Stores images and makes them accessible via resources
- Provides image URLs back to users
"""

import os
import base64
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from google import genai

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    ResourceContent,
    Resource,
    chat_protocol_spec
)
from uagents_core.storage import ExternalStorage

# Load environment variables
load_dotenv()

# Configure Gemini/Imagen
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Agentverse Storage
agentverse_api_key = os.getenv('AGENTVERSE_API_KEY')
if not agentverse_api_key:
    raise ValueError("AGENTVERSE_API_KEY not found in environment variables. Get it from https://agentverse.ai")

storage_url = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"
external_storage = ExternalStorage(api_token=agentverse_api_key, storage_url=storage_url)

# Initialize Gemini client
client = genai.Client(api_key=gemini_api_key)

# Model configuration
IMAGE_MODEL = 'gemini-2.5-flash-image'

# Create agent
agent = Agent(
    name="imagen_generator",
    seed="imagen-agent-seed-phrase-12345",  # Change this for your agent
    port=8001,
    mailbox=True  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI image generation assistant powered by Google Gemini.

When users send you a text description, you will:
1. Generate a high-quality image based on their prompt
2. Provide them with the generated image

Tips for good prompts:
- Be descriptive and specific
- Include subject, context, and style
- Mention lighting, composition, or artistic style if desired
- You can add text to images (keep it under 25 characters)

You can generate:
- Photos (realistic, studio, street photography, etc.)
- Art (paintings, sketches, digital art, etc.)
- Logos and graphics
- Scenes and landscapes
"""


# Helper functions to create chat messages
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )

def create_resource_chat(asset_id: str, uri: str, caption: str = None) -> ChatMessage:
    """Create a ChatMessage with ResourceContent (for images)"""
    content = [
        ResourceContent(
            type="resource",
            resource_id=asset_id,
            resource=Resource(
                uri=uri,
                metadata={
                    "mime_type": "image/png",
                    "role": "generated-image"
                }
            )
        )
    ]
    
    # Add optional caption as text
    if caption:
        content.append(TextContent(text=caption, type="text"))
    
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content
    )


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🎨 Starting Image Generator...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        ctx.logger.info("✅ Gemini API configured for image generation")
    else:
        ctx.logger.error("❌ Gemini API key not set")
    
    if agentverse_api_key:
        ctx.logger.info("✅ Agentverse storage configured")
    else:
        ctx.logger.warning("⚠️  Agentverse API key not set - images won't display in ASI One")
    
    # Initialize image storage
    ctx.storage.set("total_images", 0)
    ctx.storage.set("images", {})


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and generate images"""
    
    try:
        # Extract text from message content
        user_prompt = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                user_prompt = item.text
                break
        
        if not user_prompt:
            ctx.logger.warning("No text content in message")
            return
        
        # Log incoming message
        ctx.logger.info(f"📨 Prompt from {sender}: {user_prompt[:50]}...")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Check for help/info requests
        lower_prompt = user_prompt.lower()
        if any(word in lower_prompt for word in ['help', 'how', 'what can you', 'guide']):
            help_msg = f"""{SYSTEM_PROMPT}

**Example prompts:**
• "A photo of a sunset over mountains"
• "A minimalist logo for a tech startup"
• "An oil painting of a cat in a garden"
• "A futuristic city with flying cars, cyberpunk style"
• "A sketch of a coffee cup on a wooden table"

Just describe what you want to see!"""
            
            await ctx.send(sender, create_text_chat(help_msg))
            ctx.logger.info(f"💬 Help sent to {sender}")
            return
        
        # Send "generating" message
        await ctx.send(sender, create_text_chat("🎨 Generating your image... This may take a moment."))
        
        # Generate image with Gemini
        ctx.logger.info(f"🎨 Generating image with Gemini: {user_prompt[:100]}...")
        
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[user_prompt]
        )
        
        # Extract image from response
        image_parts = [
            part.inline_data.data
            for part in response.candidates[0].content.parts
            if part.inline_data
        ]
        
        if not image_parts:
            error_msg = "❌ Sorry, I couldn't generate an image. Please try a different prompt."
            await ctx.send(sender, create_text_chat(error_msg))
            return
        
        # Get image data (already in bytes)
        img_data = image_parts[0]
        
        # Upload to Agentverse External Storage
        ctx.logger.info("📤 Uploading image to Agentverse storage...")
        
        try:
            asset_id = external_storage.create_asset(
                name=f"generated_image_{int(datetime.now().timestamp())}",
                content=img_data,
                mime_type="image/png"
            )
            ctx.logger.info(f"✅ Asset created with ID: {asset_id}")
            
            # Set permissions so sender can view it
            external_storage.set_permissions(asset_id=asset_id, agent_address=sender)
            ctx.logger.info(f"🔓 Asset permissions set for: {sender}")
            
            # Create asset URI
            asset_uri = f"agent-storage://{storage_url}/{asset_id}"
            
            # Store in local storage for tracking
            total_images = ctx.storage.get("total_images") or 0
            ctx.storage.set("total_images", total_images + 1)
            
            # Send image as ResourceContent
            caption = f"✨ Generated: {user_prompt[:100]}..."
            await ctx.send(sender, create_resource_chat(asset_id, asset_uri, caption))
            
            ctx.logger.info(f"📸 Image sent to {sender}")
            
        except Exception as storage_err:
            ctx.logger.error(f"❌ Storage error: {storage_err}")
            
            # Fallback: send base64 as text
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            fallback_msg = f"""✨ **Image Generated!**

**Prompt:** {user_prompt}

⚠️ Could not upload to storage. Image data (base64):

`{img_base64[:100]}...` (truncated)

Please contact support or enable Agentverse storage."""
            await ctx.send(sender, create_text_chat(fallback_msg))
        ctx.logger.info(f"💬 Response sent to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        # Check for specific error types
        error_str = str(e)
        
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "quota" in error_str.lower():
            error_msg = """⚠️ **API Quota Limit Reached**

I've hit the free tier quota limits for image generation. This happens when:
- Too many requests in a short time
- Daily generation limits reached

**What to do:**
1. ⏰ Wait 1 hour and try again
2. 📅 Try again tomorrow (daily quota resets)
3. 💳 Consider upgrading to a paid tier for higher limits

The free tier allows:
- Limited requests per day
- Limited requests per minute

Sorry for the inconvenience! Please try again later. 🙏"""
        
        elif "INVALID_ARGUMENT" in error_str or "billing" in error_str.lower():
            error_msg = """⚠️ **Billing Required**

This model requires a billed Google Cloud account.

**Free Alternative:** Use Gemini 2.5 Flash (text) which works on free tier!

For image generation on free tier:
- Use DALL-E via OpenAI (if available)
- Wait for quota to reset
- Upgrade to paid tier"""
        
        else:
            error_msg = f"""❌ **Image Generation Error**

{str(e)[:200]}

**Please try:**
- A simpler or different prompt
- Checking if your prompt follows content guidelines  
- Waiting a moment and trying again
- Using a different style or subject"""
        
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎨 Starting Gemini Image Generator Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        print("✅ Gemini API configured for image generation")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        print("   Please add it to your .env file")
        exit(1)
    
    if agentverse_api_key:
        print("✅ Agentverse storage configured")
    else:
        print("⚠️  WARNING: AGENTVERSE_API_KEY not set")
        print("   Images won't display in ASI One without it")
        print("   Get your key from: https://agentverse.ai")
    
    print("\n🎯 Agent Features:")
    print("   • Image generation with Gemini 2.5 Flash")
    print("   • High-quality, realistic images")
    print("   • SynthID watermarking (built-in)")
    print("   • Natural language prompts")
    print("   • No billing required (uses Gemini API)")
    print("   • Ready for Agentverse deployment")
    
    print("\n✅ Agent is running! Connect via ASI One to generate images.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
