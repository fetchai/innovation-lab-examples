"""
Bridge between OpenAI Agent SDK and Fetch.ai uAgents platform.
This makes the Scholarship Finder accessible via ASI-One chat interface.
"""
from __future__ import annotations

import os
import importlib.util
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    MetadataContent,
    StartSessionContent,
    EndSessionContent,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _load_workflow_module():
    """Dynamically load the workflow.py module containing OpenAI Agent SDK logic"""
    here = os.path.dirname(__file__)
    workflow_path = os.path.join(here, "workflow.py")
    spec = importlib.util.spec_from_file_location("scholarship_finder_workflow", workflow_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load workflow module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load the workflow
workflow_mod = _load_workflow_module()
run_workflow = getattr(workflow_mod, "run_workflow")
WorkflowInput = getattr(workflow_mod, "WorkflowInput")

# Create uAgent
# Use absolute path for README to ensure it's found
_here = os.path.dirname(os.path.abspath(__file__))
_readme_path = os.path.join(_here, "agent_README.md")

# Debug: Check if README file exists
if os.path.exists(_readme_path):
    print(f"✅ README found at: {_readme_path}")
else:
    print(f"❌ README NOT found at: {_readme_path}")

agent = Agent(
    name="ScholarshipFinder",
    seed=os.getenv("AGENT_SEED", "scholarship-finder-seed"),
    mailbox=True,
    port=8003,
    publish_agent_details=True,
    readme_path=_readme_path,
)

# Create chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)


def text_msg(text: str, *, end_session: bool = False) -> ChatMessage:
    """Helper to create a text chat message"""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content
    )


WELCOME_MESSAGE = """🎓 **Scholarship Finder - Help**

I help students find scholarships they qualify for!

**📝 Share your profile with:**
• GPA (e.g., 3.7)
• Major (e.g., Computer Science)
• Year (e.g., Junior)
• Location (e.g., San Jose, CA)

**💡 Example message to send:**

"I'm a junior CS major with 3.7 GPA in San Jose, CA. Asian-American female interested in AI/ML. President of coding club, volunteer tutor. Moderate financial need."

**✨ Optional details (help find more):**
• Ethnicity, gender, interests, activities, financial need

Just send your profile and I'll find scholarships worth $10K-$50K+! 🚀"""


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""
    # ACK immediately per protocol
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ),
    )

    for item in msg.content:
        # Handle session start
        if isinstance(item, StartSessionContent):
            # Advertise capabilities (no attachments for this agent)
            await ctx.send(
                sender,
                ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[MetadataContent(
                        type="metadata",
                        metadata={"attachments": "false"}
                    )],
                ),
            )
            # Send welcome message
            await ctx.send(sender, text_msg(WELCOME_MESSAGE))
            return

        # Handle text content (student profile)
        if isinstance(item, TextContent):
            user_text = item.text.strip()
            user_text_lower = user_text.lower()
            
            # Handle empty messages
            if not user_text or len(user_text) < 3:
                await ctx.send(
                    sender,
                    text_msg("Please share your student profile so I can find scholarships for you!")
                )
                return
            
            # Handle help requests - check if ANY help keyword is in the message
            help_keywords = ["help", "how", "info", "what", "example", "start", "guide"]
            if any(keyword in user_text_lower for keyword in help_keywords) and len(user_text) < 50:
                ctx.logger.info(f"Help request detected: {user_text}")
                await ctx.send(sender, text_msg(WELCOME_MESSAGE))
                return
            
            # Check if profile has minimum info
            has_gpa = any(word in user_text.lower() for word in ["gpa", "grade", "3.", "2.", "4."])
            has_major = any(word in user_text.lower() for word in [
                "major", "computer", "engineering", "business", "science", 
                "psychology", "education", "nursing", "cs", "stem"
            ])
            has_year = any(word in user_text.lower() for word in [
                "freshman", "sophomore", "junior", "senior", 
                "1st", "2nd", "3rd", "4th", "year"
            ])
            
            if not (has_gpa or has_major or has_year):
                await ctx.send(
                    sender,
                    text_msg(
                        "I need more information to find scholarships!\n\n"
                        "Please include:\n"
                        "• Your GPA\n"
                        "• Your major\n"
                        "• Your year in school\n"
                        "• Your location\n\n"
                        "Type 'help' for an example."
                    )
                )
                return
            
            # Send processing message
            await ctx.send(
                sender,
                text_msg("🔍 Searching for scholarships matching your profile...\n\nThis may take 10-15 seconds.")
            )
            
            # Run the OpenAI Agent SDK workflow
            try:
                ctx.logger.info(f"Running scholarship search for profile: {user_text[:100]}...")
                result = await run_workflow(WorkflowInput(input_as_text=user_text))
                answer = (result or {}).get("output_text", "")
                
                if answer:
                    # Send the scholarship results
                    await ctx.send(sender, text_msg(answer))
                    ctx.logger.info("Scholarship search completed successfully")
                else:
                    await ctx.send(
                        sender,
                        text_msg(
                            "Sorry, I couldn't find scholarships matching your profile. "
                            "Try providing more details about your background and interests."
                        )
                    )
            except Exception as e:
                ctx.logger.exception("Workflow error")
                await ctx.send(
                    sender,
                    text_msg(
                        f"❌ Sorry, I encountered an error while searching for scholarships.\n\n"
                        f"Error: {str(e)}\n\n"
                        f"Please try again or contact support if the issue persists."
                    )
                )
            return

    # If no supported content found
    await ctx.send(sender, text_msg("Unsupported message content. Please send text only."))


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgement messages"""
    ctx.logger.info(f"ACK from {sender} for {msg.acknowledged_msg_id}")


# Include the chat protocol in the agent
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎓 Starting Scholarship Finder Agent...")
    print(f"📧 Mailbox: {os.getenv('AGENT_MAILBOX_KEY', 'Not configured')[:10]}...")
    print("🌐 Agent will be available on Agentverse")
    print("💬 Users can interact via ASI-One chat interface")
    print("\nPress Ctrl+C to stop\n")
    agent.run()
