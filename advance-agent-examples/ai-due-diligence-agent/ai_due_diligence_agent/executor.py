"""
Agent Executor for the AI Due Diligence Analyst.
Integrates uAgents chat protocol with Google ADK.
Queries received via chat protocol are processed by ADK agent with streaming progress updates.
"""

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from dotenv import load_dotenv

from uagents import Agent, Protocol, Context  # type: ignore
from uagents_core.contrib.protocols.chat import (  # type: ignore
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.artifacts import GcsArtifactService
from google.genai import types

from ai_due_diligence_agent.agent import root_agent
from google.cloud import storage
from datetime import timedelta

# Load environment variables
load_dotenv()

APP_NAME = "AI Due Diligence Analyst"
AGENT_PORT = int(os.getenv("AI_DUE_DILIGENCE_AGENT_PORT", "9016"))
AGENT_SEED = os.getenv("AI_DUE_DILIGENCE_AGENT_SEED", "ai-due-diligence-agent-seed-123")

# Initialize uAgent
agent = Agent(
    name=APP_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True
)

@agent.on_interval(period=3600)  # Every 1 hour
async def periodic_cleanup(ctx: Context) -> None:
    """Periodic cleanup task to maintain agent health."""
    
    ctx.logger.info("Performing periodic cleanup tasks...")
    
    try:
        client = storage.Client()
        bucket = client.bucket("ai-due-diligence-agent")
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        deleted_count = 0
        retained_count = 0
        
        for blob in bucket.list_blobs():
            ctx.logger.debug(f"Checking artifact: {blob.name}, created at {blob.time_created}")
            if blob.time_created < cutoff:
                blob.delete()
                ctx.logger.info(f"Deleted old artifact: {blob.name}")
                deleted_count += 1
            else:
                remaining_time = blob.time_created - cutoff
                ctx.logger.debug(f"Retained recent artifact: {blob.name}, remaining time: {remaining_time}")
                retained_count += 1
        
        ctx.logger.info(f"Periodic cleanup completed. Deleted: {deleted_count}, Retained: {retained_count}")
    except Exception as e:
        ctx.logger.error(f"Error during periodic cleanup: {str(e)}")

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner
adk_runner: Any = None

# Track processed messages to prevent duplicates
processed_messages: set[str] = set()

# Sub-agent stage configuration for the due diligence pipeline
PIPELINE_STAGES: list[dict[str, Any]] = [
    {
        "name": "Company Research",
        "emoji": "🔍",
        "agent_name": "CompanyResearchAgent",
        "start_indicators": ["researching", "searching", "company", "startup", "founded"],
        "completion_indicators": ["company_info", "founders", "team", "product", "technology"],
    },
    {
        "name": "Market Analysis",
        "emoji": "📊",
        "agent_name": "MarketAnalysisAgent",
        "start_indicators": ["market", "tam", "competitors", "industry"],
        "completion_indicators": ["market_analysis", "market size", "competition", "positioning"],
    },
    {
        "name": "Financial Modeling",
        "emoji": "💰",
        "agent_name": "FinancialModelingAgent",
        "start_indicators": ["financial", "revenue", "arr", "growth", "modeling"],
        "completion_indicators": ["financial_model", "projections", "scenarios", "chart"],
    },
    {
        "name": "Risk Assessment",
        "emoji": "⚠️",
        "agent_name": "RiskAssessmentAgent",
        "start_indicators": ["risk", "analyzing risk", "assessment"],
        "completion_indicators": ["risk_assessment", "risk score", "mitigation", "severity"],
    },
    {
        "name": "Investor Memo",
        "emoji": "📝",
        "agent_name": "InvestorMemoAgent",
        "start_indicators": ["memo", "investment thesis", "recommendation"],
        "completion_indicators": ["investor_memo", "executive summary", "verdict"],
    },
    {
        "name": "Report Generation",
        "emoji": "📋",
        "agent_name": "ReportGeneratorAgent",
        "start_indicators": ["generating report", "html report", "creating report"],
        "completion_indicators": ["html_report", "report saved", "artifact"],
    },
    {
        "name": "Infographic Creation",
        "emoji": "🎨",
        "agent_name": "InfographicGeneratorAgent",
        "start_indicators": ["infographic", "visual", "creating infographic"],
        "completion_indicators": ["infographic_result", "image", "generated successfully"],
    },
]


def initialize_adk_agent():
    """Initialize ADK agent and runner."""
    global adk_runner

    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required")
    os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create App with optimizations
    app = App(
        name="DueDiligenceAnalyst",
        root_agent=root_agent,
        context_cache_config=ContextCacheConfig(
            min_tokens=2048,
            ttl_seconds=1800,
            cache_intervals=10
        ),
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=30,
            overlap_size=3
        )
    )
    
    # Create runner
    session_service = InMemorySessionService()
    adk_runner = Runner(
        app=app,
        session_service=session_service,
        artifact_service=GcsArtifactService(
            bucket_name=os.getenv("ADK_GCS_BUCKET_NAME", "ai-due-diligence-agent")
        ),
    )
    
    return adk_runner


def _extract_text_from_event(event: Any) -> str | None:
    """Extract text from ADK event."""
    # Check parts attribute
    if hasattr(event, 'parts') and event.parts:
        for part in event.parts:
            if hasattr(part, 'text') and part.text:
                return part.text
            if isinstance(part, str):
                return part
    
    # Check content attribute
    if hasattr(event, 'content'):
        content = event.content
        if isinstance(content, list):
            for item in content:
                if hasattr(item, 'text') and item.text:
                    return item.text
                if isinstance(item, str):
                    return item
        elif hasattr(content, 'text') and content.text:
            return content.text
        elif hasattr(content, 'parts') and content.parts:
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
    
    # Check direct text attribute
    if hasattr(event, 'text') and event.text:
        return event.text
    
    # If event is a string
    if isinstance(event, str):
        return event
    
    return None


async def _ensure_session_exists(
    user_id: str,
    session_id: str
):
    """Ensure session exists in runner's session service."""
    runner_session_service = adk_runner.session_service
    
    try:
        await runner_session_service.create_session(
            app_name="DueDiligenceAnalyst",
            user_id=user_id,
            session_id=session_id
        )
    except Exception:
        try:
            await runner_session_service.get_session(
                app_name="DueDiligenceAnalyst",
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            pass


def get_stage_by_agent_name(agent_name: str) -> dict[str, Any] | None:
    """Get stage configuration by agent name."""
    for stage in PIPELINE_STAGES:
        if stage["agent_name"] == agent_name:
            return stage
    return None


def get_agent_from_event(event: Any) -> str | None:
    """Extract the author/agent name from an ADK event."""
    # Check for author attribute (most reliable)
    if hasattr(event, 'author') and event.author:
        return str(event.author)
    
    # Check for agent_name in metadata
    if hasattr(event, 'metadata') and event.metadata:
        if isinstance(event.metadata, dict) and 'agent_name' in event.metadata:
            return event.metadata['agent_name']
    
    # Check for source attribute
    if hasattr(event, 'source') and event.source:
        return str(event.source)
    
    # Check for name attribute
    if hasattr(event, 'name') and event.name:
        return str(event.name)
    
    return None


class StageTracker:
    """Tracks pipeline stage transitions based on agent activity."""
    
    def __init__(self) -> None:
        self.current_agent: str | None = None
        self.started_stages: set[str] = set()
        self.completed_stages: set[str] = set()
        self.last_notified_start: str | None = None
        self.last_notified_complete: str | None = None
    
    def process_event(self, event: Any, text: str | None) -> tuple[str | None, str | None]:
        """
        Process an event and return (start_notification, complete_notification).
        Returns tuple of stage messages to send, or None if no notification needed.
        """
        start_notification = None
        complete_notification = None
        
        # Try to get agent name from event metadata
        agent_name = get_agent_from_event(event)
        
        if agent_name:
            # Agent-based tracking (most reliable)
            stage = get_stage_by_agent_name(agent_name)
            
            if stage:
                stage_name = stage["name"]
                stage_emoji = stage["emoji"]
                
                # Detect stage start
                if stage_name not in self.started_stages:
                    self.started_stages.add(stage_name)
                    if stage_name != self.last_notified_start:
                        self.last_notified_start = stage_name
                        start_notification = f"{stage_emoji} **Starting {stage_name}...**"
                
                # Track current agent for completion detection
                if self.current_agent and self.current_agent != agent_name:
                    # Agent changed - previous stage completed
                    prev_stage = get_stage_by_agent_name(self.current_agent)
                    if prev_stage:
                        prev_name = prev_stage["name"]
                        prev_emoji = prev_stage["emoji"]
                        if prev_name not in self.completed_stages:
                            self.completed_stages.add(prev_name)
                            if prev_name != self.last_notified_complete:
                                self.last_notified_complete = prev_name
                                complete_notification = f"{prev_emoji} **{prev_name} Complete**"
                
                self.current_agent = agent_name
        
        elif text:
            # Fallback: text-based detection (less reliable, used only when no agent info)
            start_notification, complete_notification = self._detect_from_text(text)
        
        return start_notification, complete_notification
    
    def _detect_from_text(self, text: str) -> tuple[str | None, str | None]:
        """Fallback text-based stage detection."""
        start_notification = None
        complete_notification = None
        text_lower = text.lower()
        
        # Only use explicit markers, not vague keywords
        explicit_start_markers = {
            "Company Research": ["starting company research", "beginning company research", "researching company"],
            "Market Analysis": ["starting market analysis", "beginning market analysis", "analyzing market"],
            "Financial Modeling": ["starting financial modeling", "beginning financial model", "creating financial model"],
            "Risk Assessment": ["starting risk assessment", "beginning risk assessment", "assessing risks"],
            "Investor Memo": ["starting investor memo", "beginning investor memo", "creating investor memo"],
            "Report Generation": ["generating html report", "creating html report", "generating report"],
            "Infographic Creation": ["creating infographic", "generating infographic"],
        }
        
        explicit_complete_markers = {
            "Company Research": ["company research complete", "finished company research"],
            "Market Analysis": ["market analysis complete", "finished market analysis"],
            "Financial Modeling": ["financial modeling complete", "financial model complete"],
            "Risk Assessment": ["risk assessment complete", "finished risk assessment"],
            "Investor Memo": ["investor memo complete", "finished investor memo"],
            "Report Generation": ["report generated", "report saved", "html report complete"],
            "Infographic Creation": ["infographic generated", "infographic complete"],
        }
        
        # Check for explicit start markers
        for stage in PIPELINE_STAGES:
            stage_name = stage["name"]
            markers = explicit_start_markers.get(stage_name, [])
            if stage_name not in self.started_stages:
                if any(marker in text_lower for marker in markers):
                    self.started_stages.add(stage_name)
                    if stage_name != self.last_notified_start:
                        self.last_notified_start = stage_name
                        start_notification = f"{stage['emoji']} **Starting {stage_name}...**"
                        break
        
        # Check for explicit completion markers
        for stage in PIPELINE_STAGES:
            stage_name = stage["name"]
            markers = explicit_complete_markers.get(stage_name, [])
            if stage_name not in self.completed_stages:
                if any(marker in text_lower for marker in markers):
                    self.completed_stages.add(stage_name)
                    if stage_name != self.last_notified_complete:
                        self.last_notified_complete = stage_name
                        complete_notification = f"{stage['emoji']} **{stage_name} Complete**"
                        break
        
        return start_notification, complete_notification
    
    def finalize(self) -> str | None:
        """Mark the current/last agent's stage as complete."""
        if self.current_agent:
            stage = get_stage_by_agent_name(self.current_agent)
            if stage:
                stage_name = stage["name"]
                if stage_name not in self.completed_stages:
                    self.completed_stages.add(stage_name)
                    if stage_name != self.last_notified_complete:
                        return f"{stage['emoji']} **{stage_name} Complete**"
        return None


async def send_progress_message(ctx: Context, sender: str, message: str):
    """Send a progress update message to the chat."""
    try:
        progress_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=message)]
        )
        await ctx.send(sender, progress_msg)
        ctx.logger.info(f"Progress: {message[:100]}...")
    except Exception as e:
        ctx.logger.error(f"Failed to send progress message: {str(e)}")


async def process_with_adk(query: str, sender: str, ctx: Context) -> str:
    """Process query using ADK runner with streaming stage updates."""
    global adk_runner
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        await _ensure_session_exists(sender, str(ctx.session))
        
        # Create message and run the pipeline
        new_message = types.Content(parts=[types.Part(text=query)])
        response_parts: list[str] = []
        
        # Use StageTracker for stable stage detection
        tracker = StageTracker()
        
        async for event in adk_runner.run_async(
            user_id=sender,
            session_id=str(ctx.session),
            new_message=new_message
        ):
            text = _extract_text_from_event(event)
            if text:
                response_parts.append(str(text))
            
            # Process event through tracker (uses agent metadata when available)
            start_notification, _ = tracker.process_event(event, text)
            
            # Send start notification
            if start_notification:
                await send_progress_message(ctx, sender, start_notification)

            # Send response text as it arrives
            if text:
                await send_progress_message(ctx, sender, text)
        
        # Return final response
        if response_parts:
            return ' '.join(response_parts).strip()
        else:
            return "No response from due diligence agent"
        
    except Exception as e:
        await send_progress_message(ctx, sender, f"❌ Error: {str(e)}")
        return f"Error processing due diligence query: {str(e)}"


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize ADK agent on startup."""
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    try:
        initialize_adk_agent()
        ctx.logger.info("ADK agent initialized successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to initialize ADK agent: {str(e)}")


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and process with ADK."""
    global processed_messages
    
    # Check if message already processed
    message_key = f"{sender}:{msg.msg_id}"
    if message_key in processed_messages:
        ctx.logger.debug(f"Duplicate message ignored: {msg.msg_id}")
        return
    
    try:
        # Extract text content
        text_content = None
        for item in msg.content:
            if isinstance(item, TextContent):
                text_content = item.text
                break
        
        if not text_content:
            ctx.logger.warning("Received message with no text content")
            return
        
        # Mark message as processed
        processed_messages.add(message_key)
        
        # Limit processed messages cache size
        if len(processed_messages) > 1000:
            processed_messages.clear()
        
        ctx.logger.info(f"Received query from {sender}: {text_content}")
        
        # Send acknowledgement
        ack = ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        )
        await ctx.send(sender, ack)
        
        # Process query and send response
        response_text = await process_with_adk(text_content, sender, ctx)
        
        response = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response_text)]
        )
        await ctx.send(sender, response)
        ctx.logger.info(f"Sent final response to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {str(e)}")
        processed_messages.discard(message_key)
        error_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=f"Error: {str(e)}")]
        )
        await ctx.send(sender, error_msg)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle received acknowledgements."""
    ctx.logger.info(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")


# Include chat protocol
agent.include(chat_proto, publish_manifest=True)


def run_agent():
    """Run the uAgent."""
    agent.run()
