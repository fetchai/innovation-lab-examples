"""
Gemini Native Speech (TTS) Agent for Fetch.ai Agentverse
An AI agent that generates natural speech using Gemini 2.5 Pro TTS

This agent:
- Receives text prompts via Fetch.ai protocol
- Generates natural speech with Gemini TTS
- Supports multi-speaker dialogue
- Stores audio and makes it accessible via ASI One
"""

import os
import re
import struct
import mimetypes
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

# Configure Gemini
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Agentverse Storage
agentverse_api_key = os.getenv('AGENTVERSE_API_KEY')
if not agentverse_api_key:
    raise ValueError("AGENTVERSE_API_KEY not found in environment variables")

storage_url = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"
external_storage = ExternalStorage(api_token=agentverse_api_key, storage_url=storage_url)

# Initialize Gemini client
client = genai.Client(api_key=gemini_api_key)

# Model configuration
TTS_MODEL = 'gemini-2.5-pro-preview-tts'

# Available voices
AVAILABLE_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", 
    "Fenrir", "Aoede", "Orbit", "Nimbus"
]

# Create agent
agent = Agent(
    name="tts_generator",
    seed="", # Change this for your agent to a unique seed phrase
    port=8004,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI text-to-speech assistant powered by Gemini 2.5 Pro TTS.

When users send you text, you will:
1. Convert it to natural-sounding speech
2. Support single or multi-speaker dialogue
3. Provide them with the audio file

**Single Speaker Format:**
Just send the text you want spoken.

**Multi-Speaker Format:**
Use "Speaker 1:", "Speaker 2:", etc. on separate lines.

Available voices: Zephyr, Puck, Charon, Kore, Fenrir, Aoede, Orbit, Nimbus

Example multi-speaker:
Speaker 1: Hello, how are you?
Speaker 2: I'm doing great, thanks for asking!
"""


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
                    "role": "generated-speech"
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

def parse_audio_mime_type(mime_type: str) -> dict:
    """Parse audio MIME type for bits per sample and rate"""
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Convert raw audio to WAV format"""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size
    )
    return header + audio_data

def detect_speakers(text: str) -> bool:
    """Detect if text has multi-speaker format"""
    return bool(re.search(r'Speaker \d+:', text))

def parse_speakers(text: str) -> list:
    """Parse speakers from text"""
    speakers = set()
    for match in re.finditer(r'(Speaker \d+):', text):
        speakers.add(match.group(1))
    return sorted(list(speakers))


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🎤 Starting TTS Speech Generator...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        ctx.logger.info("✅ Gemini TTS configured")
    else:
        ctx.logger.error("❌ Gemini API key not set")
    
    if agentverse_api_key:
        ctx.logger.info("✅ Agentverse storage configured")
    else:
        ctx.logger.warning("⚠️  Agentverse API key not set")
    
    ctx.storage.set("total_speeches", 0)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and generate speech"""
    
    try:
        # Extract text
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
        
        # Check for help requests (not dialogue containing these words)
        lower_prompt = user_prompt.lower().strip()
        is_help_request = (
            lower_prompt.startswith('help') or
            lower_prompt.startswith('what can you') or
            lower_prompt.startswith('how do') or
            lower_prompt.startswith('show voices') or
            lower_prompt == 'voices' or
            'list voices' in lower_prompt
        )
        
        if is_help_request:
            help_msg = f"""{SYSTEM_PROMPT}

**Available Voices:**
{', '.join(AVAILABLE_VOICES)}

**Examples:**
• "Read this in a warm, welcoming tone: Hello world!"
• Multi-speaker dialogue with Speaker 1: and Speaker 2:
• Any text you want converted to speech!"""
            
            await ctx.send(sender, create_text_chat(help_msg))
            return
        
        # Send generating message
        await ctx.send(sender, create_text_chat(
            "🎤 Generating speech... Please wait! ⏳"
        ))
        
        ctx.logger.info(f"🎤 Starting speech generation...")
        
        # Detect if multi-speaker
        is_multi_speaker = detect_speakers(user_prompt)
        
        # Build config
        if is_multi_speaker:
            speakers = parse_speakers(user_prompt)
            ctx.logger.info(f"Multi-speaker detected: {speakers}")
            
            # Assign voices to speakers
            speaker_configs = []
            for i, speaker in enumerate(speakers):
                voice = AVAILABLE_VOICES[i % len(AVAILABLE_VOICES)]
                speaker_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice
                            )
                        ),
                    )
                )
            
            speech_config = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=speaker_configs
                )
            )
        else:
            # Single speaker - use default voice
            speech_config = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Zephyr"
                    )
                )
            )
        
        # Generate speech
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_prompt)],
            ),
        ]
        
        generate_config = types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=speech_config,
        )
        
        # Collect audio chunks
        audio_chunks = []
        
        for chunk in client.models.generate_content_stream(
            model=TTS_MODEL,
            contents=contents,
            config=generate_config,
        ):
            if (
                chunk.candidates
                and chunk.candidates[0].content
                and chunk.candidates[0].content.parts
            ):
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    audio_chunks.append({
                        'data': part.inline_data.data,
                        'mime_type': part.inline_data.mime_type
                    })
        
        if not audio_chunks:
            error_msg = "❌ No audio generated. Please try again."
            await ctx.send(sender, create_text_chat(error_msg))
            return
        
        ctx.logger.info(f"✅ Collected {len(audio_chunks)} audio chunks")
        
        # Combine and convert to WAV
        combined_audio = b''
        for chunk in audio_chunks:
            mime_type = chunk['mime_type']
            data = chunk['data']
            
            # Check if needs conversion
            file_ext = mimetypes.guess_extension(mime_type)
            if file_ext is None or file_ext != '.wav':
                data = convert_to_wav(data, mime_type)
            
            combined_audio += data
        
        ctx.logger.info(f"📦 Combined audio: {len(combined_audio)} bytes")
        
        # Upload to Agentverse storage
        ctx.logger.info("📤 Uploading to Agentverse...")
        
        asset_id = external_storage.create_asset(
            name=f"speech_{int(datetime.now().timestamp())}",
            content=combined_audio,
            mime_type="audio/wav"
        )
        
        external_storage.set_permissions(asset_id=asset_id, agent_address=sender)
        asset_uri = f"agent-storage://{storage_url}/{asset_id}"
        
        # Track and send
        total_speeches = ctx.storage.get("total_speeches") or 0
        ctx.storage.set("total_speeches", total_speeches + 1)
        
        speaker_info = f"{len(parse_speakers(user_prompt))} speakers" if is_multi_speaker else "Single voice"
        caption = f"🎤 {user_prompt[:80]}... ({speaker_info})"
        await ctx.send(sender, create_resource_chat(asset_id, asset_uri, caption))
        ctx.logger.info(f"🎤 Speech sent to {sender}!")
        
    except Exception as e:
        ctx.logger.error(f"❌ Error: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        error_msg = f"❌ Speech generation error: {str(e)[:200]}\n\nPlease try again with simpler text."
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎤 Starting Gemini TTS Speech Generator Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if gemini_api_key:
        print("✅ Gemini TTS configured")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        exit(1)
    
    if agentverse_api_key:
        print("✅ Agentverse storage configured")
    else:
        print("⚠️  WARNING: AGENTVERSE_API_KEY not set")
    
    print("\n🎯 Agent Features:")
    print("   • Text-to-speech with Gemini 2.5 Pro")
    print("   • Multi-speaker dialogue support")
    print("   • 8 different voice presets")
    print("   • Natural, expressive speech")
    print("   • High-quality audio output")
    
    print("\n✅ Agent is running! Connect via ASI One to generate speech.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
