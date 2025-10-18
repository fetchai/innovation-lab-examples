"""
Lyria RealTime Music Generation Agent for Fetch.ai Agentverse
An AI agent that generates music using Google Lyria RealTime

This agent:
- Receives text prompts via Fetch.ai protocol
- Generates instrumental music with Lyria RealTime
- Streams and collects audio chunks
- Stores music and makes it accessible via ASI One
"""

import os
import asyncio
import wave
import struct
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
    chat_protocol_spec
)
from uagents_core.storage import ExternalStorage

# Load environment variables
load_dotenv()

# Configure Gemini/Lyria
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Agentverse Storage
agentverse_api_key = os.getenv('AGENTVERSE_API_KEY')
if not agentverse_api_key:
    raise ValueError("AGENTVERSE_API_KEY not found in environment variables")

storage_url = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"
external_storage = ExternalStorage(api_token=agentverse_api_key, storage_url=storage_url)

# Initialize Gemini client with alpha API version for Lyria
client = genai.Client(http_options={'api_version': 'v1alpha'}, api_key=gemini_api_key)

# Model configuration
LYRIA_MODEL = 'models/lyria-realtime-exp'
SAMPLE_RATE = 48000  # 48kHz
CHANNELS = 2  # Stereo
DURATION_SECONDS = 30  # Generate 30 seconds of music

# Create agent
agent = Agent(
    name="lyria_generator",
    seed="",  # Change this for your agent to a unique seed phrase
    port=8003,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI music generation assistant powered by Google Lyria RealTime.

When users send you a music description, you will:
1. Generate 30 seconds of instrumental music based on their prompt
2. Provide them with the generated audio file

Tips for good prompts:
- Describe genre, mood, and instruments
- Mention tempo (BPM) if desired
- Include descriptive adjectives
- Combine multiple elements (e.g., "Chill lo-fi hip hop with piano")

You can generate:
- Any instrumental genre
- Various moods and atmospheres
- Specific instrument combinations
- Different tempos and styles

Examples:
• "Minimal techno at 120 BPM"
• "Chill lo-fi hip hop with piano and soft beats"
• "Epic orchestral score with strings and brass"
• "Funky disco with bass guitar and drums"
"""


# Helper functions
def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )

def create_resource_chat(asset_id: str, uri: str, caption: str = None) -> ChatMessage:
    """Create a ChatMessage with ResourceContent (for audio)"""
    content = [
        ResourceContent(
            type="resource",
            resource_id=asset_id,
            resource=Resource(
                uri=uri,
                metadata={
                    "mime_type": "audio/wav",
                    "role": "generated-music"
                }
            )
        )
    ]
    
    if caption:
        content.append(TextContent(text=caption, type="text"))
    
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content
    )

def save_pcm_as_wav(pcm_data: bytes, filename: str):
    """Convert raw PCM data to WAV file"""
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data)


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🎵 Starting Lyria Music Generator...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        ctx.logger.info("✅ Lyria API configured for music generation")
    else:
        ctx.logger.error("❌ Gemini API key not set")
    
    if agentverse_api_key:
        ctx.logger.info("✅ Agentverse storage configured")
    else:
        ctx.logger.warning("⚠️  Agentverse API key not set")
    
    ctx.storage.set("total_tracks", 0)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and generate music"""
    
    try:
        # Extract text from message
        user_prompt = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                user_prompt = item.text
                break
        
        if not user_prompt:
            ctx.logger.warning("No text content in message")
            return
        
        ctx.logger.info(f"📨 Prompt from {sender}: {user_prompt[:50]}...")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Check for help
        if any(word in user_prompt.lower() for word in ['help', 'how', 'what can you']):
            help_msg = f"""{SYSTEM_PROMPT}

**Example prompts:**
• "Minimal techno at 120 BPM"
• "Chill lo-fi hip hop with piano"
• "Epic orchestral with strings"
• "Funky disco bass"
• "Ambient meditation music"

Describe the music you want to hear!"""
            
            await ctx.send(sender, create_text_chat(help_msg))
            return
        
        # Send generating message
        await ctx.send(sender, create_text_chat(
            "🎵 Generating your music... This takes ~30 seconds. Please wait! ⏳"
        ))
        
        ctx.logger.info(f"🎵 Starting music generation: {user_prompt[:100]}...")
        
        # Generate music using Lyria RealTime
        audio_chunks = []
        is_collecting = True
        
        async def receive_audio(session):
            """Collect audio chunks"""
            try:
                async for message in session.receive():
                    if not is_collecting:
                        break
                    if hasattr(message, 'server_content') and message.server_content.audio_chunks:
                        for chunk in message.server_content.audio_chunks:
                            audio_chunks.append(chunk.data)
            except asyncio.CancelledError:
                pass  # Task cancelled, exit gracefully
        
        # Connect and generate
        async with client.aio.live.music.connect(model=LYRIA_MODEL) as session:
            # Start audio receiver task
            receiver_task = asyncio.create_task(receive_audio(session))
            
            try:
                # Send prompts and config
                await session.set_weighted_prompts(
                    prompts=[types.WeightedPrompt(text=user_prompt, weight=1.0)]
                )
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(
                        bpm=120,
                        temperature=1.0,
                        music_generation_mode=types.MusicGenerationMode.QUALITY
                    )
                )
                
                # Start streaming
                await session.play()
                ctx.logger.info("🎵 Streaming music...")
                
                # Collect for 30 seconds
                await asyncio.sleep(DURATION_SECONDS)
                
                # Stop streaming
                is_collecting = False
                await session.stop()
                
                # Wait a bit for final chunks
                await asyncio.sleep(1)
                
                ctx.logger.info(f"✅ Collected {len(audio_chunks)} audio chunks")
                
            finally:
                # Cancel receiver task
                receiver_task.cancel()
                try:
                    await receiver_task
                except asyncio.CancelledError:
                    pass
        
        if not audio_chunks:
            error_msg = "❌ No audio generated. Please try a different prompt."
            await ctx.send(sender, create_text_chat(error_msg))
            return
        
        # Combine audio chunks
        pcm_data = b''.join(audio_chunks)
        ctx.logger.info(f"📦 Combined audio: {len(pcm_data)} bytes")
        
        # Convert to WAV
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = tmp.name
        
        save_pcm_as_wav(pcm_data, temp_path)
        
        # Read WAV bytes
        with open(temp_path, 'rb') as f:
            wav_data = f.read()
        
        os.remove(temp_path)
        ctx.logger.info(f"✅ WAV file created: {len(wav_data)} bytes")
        
        # Upload to Agentverse storage
        ctx.logger.info("📤 Uploading to Agentverse...")
        
        asset_id = external_storage.create_asset(
            name=f"music_{int(datetime.now().timestamp())}",
            content=wav_data,
            mime_type="audio/wav"
        )
        
        external_storage.set_permissions(asset_id=asset_id, agent_address=sender)
        asset_uri = f"agent-storage://{storage_url}/{asset_id}"
        
        # Track and send
        total_tracks = ctx.storage.get("total_tracks") or 0
        ctx.storage.set("total_tracks", total_tracks + 1)
        
        caption = f"🎵 {user_prompt[:100]}... (30s)"
        await ctx.send(sender, create_resource_chat(asset_id, asset_uri, caption))
        ctx.logger.info(f"🎵 Music sent to {sender}!")
        
    except Exception as e:
        ctx.logger.error(f"❌ Error: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        error_str = str(e)
        
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
            error_msg = "⚠️ API quota reached. Please try again later."
        else:
            error_msg = f"❌ Music generation error: {str(e)[:200]}\n\nTry a different prompt or wait a moment."
        
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎵 Starting Lyria Music Generator Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        print("✅ Lyria API configured")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        exit(1)
    
    if agentverse_api_key:
        print("✅ Agentverse storage configured")
    else:
        print("⚠️  WARNING: AGENTVERSE_API_KEY not set")
    
    print("\n🎯 Agent Features:")
    print("   • Music generation with Lyria RealTime")
    print("   • 30-second instrumental tracks")
    print("   • Real-time streaming synthesis")
    print("   • High-quality 48kHz stereo")
    print("   • Natural language prompts")
    
    print("\n⏳ Note: Music generation takes ~30 seconds")
    print("\n✅ Agent is running! Connect via ASI One to generate music.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
