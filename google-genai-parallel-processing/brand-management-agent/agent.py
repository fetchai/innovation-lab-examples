#!/usr/bin/env python3
"""
Brand Management Agent - Parallel Processing Example

This agent demonstrates how to perform parallel processing in uAgents using the
genai-processors library. It creates brand assets (name, tagline, logo, web layout)
concurrently and synthesizes the results.

Key Concepts Demonstrated:
- Parallel execution with processor.parallel_concat()
- Stream processing with async generators
- Multimodal output (text + images)
- External storage integration
- Chat protocol handling
"""

import asyncio
import uuid
import time
import requests
import httpx
from typing import AsyncIterable
from uagents import Agent, Context, Protocol
from genai_processors import processor, streams
from genai_processors.processor import ProcessorPart, status
import openai
import os
from datetime import datetime
from uagents_core.storage import ExternalStorage
from pydantic.v1 import UUID4

# Chat protocol components for agent communication
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    Resource,
    ResourceContent,
    chat_protocol_spec,
)

# === Configuration ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "your-agentverse-api-key")
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "your-asi1-api-key")

# API endpoints
ASI1_BASE_URL = "https://api.asi1.ai/v1/chat/completions"

# Agentverse storage URL
STORAGE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"

# Initialize external services
openai.api_key = OPENAI_API_KEY
external_storage = ExternalStorage(api_token=AGENTVERSE_API_KEY, storage_url=STORAGE_URL)

# === Base Processor Class ===
class ASI1MiniProcessor(processor.Processor):
    """ Base processor for ASI:One Mini text generation."""
    def __init__(self, prompt: str, task: str, metadata_type: str):
        self.prompt = prompt
        self.task = task
        self.metadata_type = metadata_type

    async def call(self, content: AsyncIterable[ProcessorPart]):
        """Main processing method - yields status updates and final results"""
        yield status(f"{self.task}...")
        try:
            # Make API call to ASI:One Mini
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ASI1_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {ASI1_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "asi1-mini",
                        "messages": [{"role": "user", "content": f"{self.task} for: {self.prompt}"}],
                        "temperature": 0.7,
                        "max_tokens": 1024,
                        "stream": False
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                response_text = result["choices"][0]["message"]["content"].strip()
            
            # Yield the result with metadata for stream processing
            yield ProcessorPart(response_text, metadata={"type": self.metadata_type})
        except Exception as e:
            yield ProcessorPart(f"Error during {self.task}: {str(e)}", metadata={"type": self.metadata_type, "error": True})

# === Specialized Processors ===
class BrandNameProcessor(ASI1MiniProcessor):
    """Processor for generating brand names"""
    def __init__(self, prompt: str):
        super().__init__(prompt, "Generate a creative brand name", "brand_name")

class TaglineProcessor(ASI1MiniProcessor):
    """Processor for generating taglines"""
    def __init__(self, prompt: str):
        super().__init__(prompt, "Write a catchy tagline", "tagline")

class WebLayoutProcessor(ASI1MiniProcessor):
    """Processor for generating HTML layouts"""
    def __init__(self, prompt: str):
        super().__init__(prompt, "Design a minimal HTML layout for a landing page", "web_layout")

class LogoImageProcessor(processor.Processor):
    """
    Processor for generating and uploading logo images.
    Demonstrates multimodal processing (image generation + storage).
    """
    def __init__(self, prompt: str):
        self.prompt = prompt
        self.asset_id = None
        self.asset_uri = None

    async def call(self, content: AsyncIterable[ProcessorPart]):
        yield status("Generating logo with DALL·E...")
        try:
            # Generate image using DALL·E
            response = openai.images.generate(
                model="dall-e-3",
                prompt=f"Minimal flat vector-style logo design for: {self.prompt}",
                n=1,
                size="1024x1024",
                quality="standard",
                response_format="url"
            )
            
            if response.data and response.data[0].url:
                # Download and upload to external storage
                image_url = response.data[0].url
                response = requests.get(image_url)
                if response.status_code == 200:
                    image_data = response.content
                    mime_type = response.headers.get("Content-Type", "image/png")
                    
                    # Upload to external storage
                    self.asset_id = external_storage.create_asset(
                        name=f"logo_{uuid.uuid4().hex}",
                        content=image_data,
                        mime_type=mime_type
                    )
                    self.asset_uri = f"agent-storage://{external_storage.storage_url}/{self.asset_id}"
                    yield ProcessorPart(f"Logo uploaded: {self.asset_id}", metadata={"type": "logo_image"})
                else:
                    yield ProcessorPart("Failed to download image", metadata={"type": "logo_image", "error": True})
            else:
                yield ProcessorPart("No image URL received", metadata={"type": "logo_image", "error": True})
        except Exception as e:
            yield ProcessorPart(f"Logo generation failed: {str(e)}", metadata={"type": "logo_image", "error": True})

# === Synthesis Processor ===
class SynthesisProcessor:
    """
    Standalone processor for synthesizing parallel results.
    Demonstrates how to combine multiple processor outputs.
    """
    async def synthesize_results(self, collected_results: dict) -> str:
        """Synthesize all collected results into a final output"""
        try:
            summary_prompt = f"""
            You are an expert branding assistant. Given the following:

            BRAND NAMES:
            {collected_results.get("brand_name", "")}

            TAGLINES:
            {collected_results.get("tagline", "")}

            WEB LAYOUTS:
            {collected_results.get("web_layout", "")}

            Choose the best brand name, tagline, and provide the HTML layout. Return as:

            BRAND NAME:
            [selected name]

            TAGLINE:
            [selected tagline]

            WEB LAYOUT:
            [complete HTML]
            """
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ASI1_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {ASI1_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "asi1-mini",
                        "messages": [{"role": "user", "content": summary_prompt}],
                        "temperature": 0.3,
                        "max_tokens": 2048,
                        "stream": False
                    },
                    timeout=45.0
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            return f"Error generating final output: {e}"

# === Chat Protocol Handler ===
chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """
    Main message handler demonstrating parallel processing.
    
    This is where the magic happens:
    1. Creates multiple processors
    2. Runs them in parallel using processor.parallel_concat()
    3. Collects results as they complete
    4. Synthesizes final output
    """
    # Acknowledge message receipt
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

    for item in msg.content:
        if isinstance(item, TextContent):
            prompt = item.text
            ctx.logger.info(f"Processing: {prompt}")
            
            print(f"🔄 Starting parallel execution for: '{prompt}'")
            
            # === PARALLEL PROCESSING SETUP ===
            # Create processors for each task
            logo_processor = LogoImageProcessor(prompt)
            
            # This is the key line - runs all processors in parallel
            mm_agent = processor.parallel_concat([
                BrandNameProcessor(prompt),    # Task 1: Brand name
                TaglineProcessor(prompt),      # Task 2: Tagline
                logo_processor,                # Task 3: Logo image
                WebLayoutProcessor(prompt)     # Task 4: Web layout
            ])

            # === STREAM PROCESSING ===
            # Create input stream to trigger all processors
            input_stream = streams.stream_content([ProcessorPart("start")])
            collected = {}
            total_tasks = 4
            
            # Process results as they arrive (not necessarily in order)
            async for part in mm_agent(input_stream):
                if part.metadata and not part.metadata.get("error"):
                    # Store result by metadata type
                    collected[part.metadata["type"]] = part.text.strip()
                    print(f"✅ {part.metadata['type']} completed")
                elif part.metadata and part.metadata.get("error"):
                    print(f"❌ {part.metadata['type']} failed")

            print(f"📊 Completed: {len(collected)}/{total_tasks} tasks")

            # === SYNTHESIS ===
            # Combine all results into final output
            synthesis_processor = SynthesisProcessor()
            reply = await synthesis_processor.synthesize_results(collected)

            # Send text response
            await ctx.send(sender, ChatMessage(
                timestamp=datetime.utcnow(),
                msg_id=uuid.uuid4(),
                content=[TextContent(type="text", text=reply)]
            ))

            # Send logo image as resource
            if logo_processor.asset_id and logo_processor.asset_uri:
                try:
                    external_storage.set_permissions(asset_id=logo_processor.asset_id, agent_address=sender)
                    print(f"📎 Logo uploaded: {logo_processor.asset_id}")
                    
                    await ctx.send(sender, ChatMessage(
                        timestamp=datetime.utcnow(),
                        msg_id=uuid.uuid4(),
                        content=[
                            ResourceContent(
                                type="resource",
                                resource_id=UUID4(logo_processor.asset_id),
                                resource=Resource(
                                    uri=logo_processor.asset_uri,
                                    metadata={"mime_type": "image/png", "role": "generated-image"}
                                )
                            )
                        ]
                    ))
                except Exception as e:
                    ctx.logger.error(f"Error sending logo: {e}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgments from other agents"""
    ctx.logger.info(f"Received ack from {sender} for {msg.acknowledged_msg_id}")

# === Agent Setup ===
agent = Agent(
    name="brand_management_agent",
    seed="brand_management_parallel_processing_demo",
    port=8002,
    mailbox=True  # Enable Agentverse integration
)

# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print("🚀 Starting Brand Management Agent with Parallel Processing...")
    print("💡 Send a message like 'build a around sustainable clothing' to see parallel processing in action!")
    agent.run()