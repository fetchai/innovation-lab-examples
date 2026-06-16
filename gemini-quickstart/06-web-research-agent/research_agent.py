"""
Web Research Agent for Fetch.ai Agentverse
An AI agent that fetches and analyzes information from URLs using Gemini

This agent:
- Receives URLs and questions via Fetch.ai protocol
- Fetches web content using Gemini's URL context tool
- Analyzes and summarizes information
- Returns intelligent responses with citations
"""

import os
import re
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
    chat_protocol_spec,
)

# Load environment variables
load_dotenv()

# Configure Gemini
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini client
client = genai.Client(api_key=gemini_api_key)

# Model configuration
MODEL = "gemini-2.5-flash"

# Create agent
agent = Agent(
    name="web_researcher",
    seed="",  # Change this for your agent to a unique seed phrase
    port=8005,
    mailbox=True,
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI web research assistant powered by Gemini 2.5 Flash.

When users send you a URL and question, you will:
1. Fetch and analyze the web content
2. Extract relevant information
3. Provide a comprehensive answer with citations

**Format:**
URL: <url>
Question: <your question>

**Or just:**
<url> - <question>

**Examples:**
• "URL: https://ai.google.dev/gemini-api/docs/changelog Question: What are the latest updates?"
• "https://example.com - Summarize this article"
• "Analyze this page: https://example.com"
"""


def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")],
    )


def parse_url_and_question(text: str) -> tuple:
    """Extract URL and question from user input"""
    # Pattern 1: "URL: <url> Question: <question>"
    pattern1 = r"URL:\s*(https?://\S+)\s+Question:\s*(.+)"
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)

    # Pattern 2: "<url> - <question>"
    pattern2 = r"(https?://\S+)\s*-\s*(.+)"
    match = re.search(pattern2, text)
    if match:
        return match.group(1), match.group(2)

    # Pattern 3: Just URL (default question: "Summarize this")
    pattern3 = r"(https?://\S+)"
    match = re.search(pattern3, text)
    if match:
        url = match.group(1)
        # Remove URL from text to get the question
        question = text.replace(url, "").strip()
        if not question:
            question = "Summarize the main points from this page"
        return url, question

    return None, None


@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🔍 Starting Web Research Agent...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")

    if gemini_api_key:
        ctx.logger.info("✅ Gemini API configured")
    else:
        ctx.logger.error("❌ Gemini API key not set")

    ctx.storage.set("total_researches", 0)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and perform web research"""

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
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
            ),
        )

        # Check for help
        lower_prompt = user_prompt.lower().strip()
        if lower_prompt.startswith("help") or lower_prompt.startswith("how do"):
            help_msg = f"""{SYSTEM_PROMPT}

**Quick Examples:**
• `https://ai.google.dev - What are the latest features?`
• `URL: https://example.com Question: Summarize this article`
• `https://news.site.com/article - What is this about?`

Just send me a URL and your question!"""

            await ctx.send(sender, create_text_chat(help_msg))
            return

        # Parse URL and question
        url, question = parse_url_and_question(user_prompt)

        if not url:
            error_msg = """❌ Could not find a valid URL in your message.

**Format:**
`URL: <url> Question: <question>`

**Or:**
`<url> - <question>`

**Example:**
`https://ai.google.dev - What are the latest updates?`"""

            await ctx.send(sender, create_text_chat(error_msg))
            return

        # Send researching message
        await ctx.send(
            sender, create_text_chat(f"🔍 Researching {url}... Please wait! ⏳")
        )

        ctx.logger.info(f"🔍 Fetching: {url}")
        ctx.logger.info(f"❓ Question: {question}")

        # Build prompt with URL
        full_prompt = f"{question}\n\nURL for research: {url}"

        # Configure with URL context tool
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=full_prompt)],
            ),
        ]

        tools = [
            types.Tool(url_context=types.UrlContext()),
        ]

        generate_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,  # Use extended thinking
            ),
            tools=tools,
        )

        # Generate response
        response_text = ""

        for chunk in client.models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=generate_config,
        ):
            if chunk.text:
                response_text += chunk.text

        if not response_text:
            error_msg = "❌ Could not fetch or analyze the URL. The page might be inaccessible or blocked."
            await ctx.send(sender, create_text_chat(error_msg))
            return

        ctx.logger.info(f"✅ Research complete: {len(response_text)} chars")

        # Send response
        final_response = f"**Research Results for:** {url}\n\n{response_text}"
        await ctx.send(sender, create_text_chat(final_response))

        # Track
        total = ctx.storage.get("total_researches") or 0
        ctx.storage.set("total_researches", total + 1)

        ctx.logger.info(f"🔍 Response sent to {sender}!")

    except Exception as e:
        ctx.logger.error(f"❌ Error: {e}")
        import traceback

        ctx.logger.error(traceback.format_exc())

        error_msg = f"❌ Research error: {str(e)[:200]}\n\nThe URL might be inaccessible or there was an issue processing it."
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🔍 Starting Web Research Agent...")
    print(f"📍 Agent address: {agent.address}")

    if gemini_api_key:
        print("✅ Gemini API configured")
    else:
        print("❌ ERROR: GEMINI_API_KEY not set")
        exit(1)

    print("\n🎯 Agent Features:")
    print("   • Fetch and analyze web content")
    print("   • Answer questions about URLs")
    print("   • Extract key information")
    print("   • Summarize articles and pages")
    print("   • Deep thinking mode enabled")

    print("\n✅ Agent is running! Connect via ASI One for web research.")
    print("   Press Ctrl+C to stop.\n")

    agent.run()
