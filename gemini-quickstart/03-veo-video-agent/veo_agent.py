"""
Veo 3.1 Video Generation Agent for Fetch.ai Agentverse
An AI agent that generates high-fidelity videos using Google Veo 3.1

This agent:
- Receives text prompts via Fetch.ai protocol
- Generates 8-second HD videos with Google Veo 3.1
- Includes native audio and stunning realism
- Stores videos and makes them accessible via ASI One
"""

import os
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from google import genai
from google.genai import types

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    ResourceContent,
    Resource,
    chat_protocol_spec,
)
from uagents_core.storage import ExternalStorage

# Load environment variables
load_dotenv()

# Configure Gemini/Veo
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Agentverse Storage
agentverse_api_key = os.getenv("AGENTVERSE_API_KEY")
if not agentverse_api_key:
    raise ValueError(
        "AGENTVERSE_API_KEY not found in environment variables. Get it from https://agentverse.ai"
    )

storage_url = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"
external_storage = ExternalStorage(
    api_token=agentverse_api_key, storage_url=storage_url
)

# Initialize Gemini client
client = genai.Client(api_key=gemini_api_key)

# Model configuration
VEO_MODEL = "veo-3.1-generate-preview"
DEFAULT_VIDEO_CONFIG = types.GenerateVideosConfig(
    number_of_videos=1,
    resolution="720p",  # 720p or 1080p
)

# Create agent
agent = Agent(
    name="veo_generator",
    seed="",  # Change this for your agent to a unique seed phrase
    port=8002,
    mailbox=True,  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI video generation assistant powered by Google Veo 3.1.

When users send you a text description, you will:
1. Generate a high-fidelity 8-second video based on their prompt
2. Include native audio and stunning realism
3. Provide them with the generated video

Tips for good prompts:
- Be descriptive about action, movement, and scene
- Include camera angles and shots (wide shot, close-up, etc.)
- Mention lighting, mood, and atmosphere
- Describe sounds and audio if desired
- Be specific about subject, setting, and style

You can generate:
- Cinematic scenes with dialogue
- Creative animations
- Product showcases
- Nature and landscapes
- Abstract visuals
- Character performances

Note: Video generation takes 30-60 seconds. Be patient!
"""


# Helper functions to create chat messages
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")],
    )


def create_resource_chat(asset_id: str, uri: str, caption: str = None) -> ChatMessage:
    """Create a ChatMessage with ResourceContent (for videos)"""
    content = [
        ResourceContent(
            type="resource",
            resource_id=asset_id,
            resource=Resource(
                uri=uri, metadata={"mime_type": "video/mp4", "role": "generated-video"}
            ),
        )
    ]

    # Add optional caption as text
    if caption:
        content.append(TextContent(text=caption, type="text"))

    return ChatMessage(
        timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content
    )


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🎬 Starting Veo Video Generator...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")

    if gemini_api_key:
        ctx.logger.info("✅ Veo API configured for video generation")
    else:
        ctx.logger.error("❌ Gemini API key not set")

    if agentverse_api_key:
        ctx.logger.info("✅ Agentverse storage configured")
    else:
        ctx.logger.warning(
            "⚠️  Agentverse API key not set - videos won't display in ASI One"
        )

    # Initialize video storage
    ctx.storage.set("total_videos", 0)
    ctx.storage.set("videos", {})


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and generate videos"""

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
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
            ),
        )

        # Check for help/info requests
        lower_prompt = user_prompt.lower()
        if any(
            word in lower_prompt for word in ["help", "how", "what can you", "guide"]
        ):
            help_msg = f"""{SYSTEM_PROMPT}

**Example prompts:**
• "A close up of two people talking by torchlight in a cave"
• "A calico kitten sleeping in the sunshine, camera slowly pans"
• "An origami butterfly flies through a garden"
• "Cinematic drone shot of a sunset over mountains"
• "A robot dancing on a city street at night"

Just describe the video you want to see!"""

            await ctx.send(sender, create_text_chat(help_msg))
            ctx.logger.info(f"💬 Help sent to {sender}")
            return

        # Send "generating" message
        await ctx.send(
            sender,
            create_text_chat(
                "🎬 Generating your video... This takes 30-60 seconds. Please wait! ⏳"
            ),
        )

        # Generate video with Veo
        ctx.logger.info(
            f"🎬 Starting video generation with Veo: {user_prompt[:100]}..."
        )

        operation = client.models.generate_videos(
            model=VEO_MODEL, prompt=user_prompt, config=DEFAULT_VIDEO_CONFIG
        )

        ctx.logger.info(f"⏳ Operation started: {operation.name}")

        # Poll operation status
        poll_count = 0
        max_polls = 60  # Max 10 minutes (60 * 10 seconds)

        while not operation.done and poll_count < max_polls:
            ctx.logger.info(f"⏳ Waiting for video generation... ({poll_count * 10}s)")

            # Send periodic updates to keep user engaged
            if poll_count % 3 == 0 and poll_count > 0:
                await ctx.send(
                    sender,
                    create_text_chat(
                        f"⏳ Still generating... {poll_count * 10}s elapsed. Almost there!"
                    ),
                )

            await asyncio.sleep(10)  # Wait 10 seconds
            operation = client.operations.get(operation)
            poll_count += 1

        if not operation.done:
            error_msg = "❌ Video generation timed out. Please try a simpler prompt or try again later."
            await ctx.send(sender, create_text_chat(error_msg))
            return

        # Check if generation was successful
        if not operation.response or not operation.response.generated_videos:
            error_msg = (
                "❌ Sorry, I couldn't generate a video. Please try a different prompt."
            )
            await ctx.send(sender, create_text_chat(error_msg))
            return

        generated_video = operation.response.generated_videos[0]
        ctx.logger.info("✅ Video generated successfully!")

        # Get video and download bytes
        video = generated_video.video
        ctx.logger.info("📥 Downloading video...")

        # Try Files.download() with just the file parameter
        try:
            video_bytes = client.files.download(file=video)
            ctx.logger.info(f"✅ Downloaded {len(video_bytes)} bytes")
        except Exception as download_err:
            ctx.logger.error(f"Download error: {download_err}")
            # Fallback: try getting URI and fetching manually
            video_uri = (
                video.uri
                if hasattr(video, "uri")
                else f"https://generativelanguage.googleapis.com/v1beta/{video.name}"
            )
            ctx.logger.info(f"Trying manual fetch from: {video_uri}")

            import requests

            headers = {"Authorization": f"Bearer {gemini_api_key}"}
            response = requests.get(video_uri, headers=headers)
            video_bytes = response.content
            ctx.logger.info(f"✅ Fetched {len(video_bytes)} bytes manually")

        # Upload to Agentverse storage
        ctx.logger.info("📤 Uploading to Agentverse...")
        asset_id = external_storage.create_asset(
            name=f"video_{int(datetime.now().timestamp())}",
            content=video_bytes,
            mime_type="video/mp4",
        )

        external_storage.set_permissions(asset_id=asset_id, agent_address=sender)
        asset_uri = f"agent-storage://{storage_url}/{asset_id}"

        # Track and send
        total_videos = ctx.storage.get("total_videos") or 0
        ctx.storage.set("total_videos", total_videos + 1)

        caption = f"🎬 {user_prompt[:100]}... (8s, 720p)"
        await ctx.send(sender, create_resource_chat(asset_id, asset_uri, caption))
        ctx.logger.info("🎬 Video sent!")

    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        import traceback

        ctx.logger.error(traceback.format_exc())

        # Check for specific error types
        error_str = str(e)

        if (
            "RESOURCE_EXHAUSTED" in error_str
            or "429" in error_str
            or "quota" in error_str.lower()
        ):
            error_msg = """⚠️ **API Quota Limit Reached**

I've hit the quota limits for video generation. This happens when:
- Too many requests in a short time
- Daily generation limits reached

**What to do:**
1. ⏰ Wait 1 hour and try again
2. 📅 Try again tomorrow (daily quota resets)
3. 💳 Consider upgrading to a paid tier for higher limits

Video generation uses more quota than images, so limits are reached faster.

Sorry for the inconvenience! Please try again later. 🙏"""

        else:
            error_msg = f"""❌ **Video Generation Error**

{str(e)[:200]}

**Please try:**
- A simpler or shorter prompt
- More specific camera angles and actions
- Checking if your prompt follows content guidelines  
- Waiting a moment and trying again"""

        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎬 Starting Veo 3.1 Video Generator Agent...")
    print(f"📍 Agent address: {agent.address}")

    if gemini_api_key:
        print("✅ Veo API configured for video generation")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        print("   Please add it to your .env file")
        exit(1)

    if agentverse_api_key:
        print("✅ Agentverse storage configured")
    else:
        print("⚠️  WARNING: AGENTVERSE_API_KEY not set")
        print("   Videos won't display in ASI One without it")
        print("   Get your key from: https://agentverse.ai")

    print("\n🎯 Agent Features:")
    print("   • Video generation with Veo 3.1")
    print("   • 8-second HD videos (720p/1080p)")
    print("   • Native audio generation")
    print("   • Cinematic realism")
    print("   • Natural language prompts")
    print("   • Ready for Agentverse deployment")

    print("\n⏳ Note: Video generation takes 30-60 seconds per request")
    print("\n✅ Agent is running! Connect via ASI One to generate videos.")
    print("   Press Ctrl+C to stop.\n")

    agent.run()
