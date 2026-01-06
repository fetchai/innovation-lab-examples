"""
On-Page SEO Audit & Optimization Team built with Google ADK.

The workflow runs three specialized agents in sequence:
1. Page Auditor → scrapes the target URL with Firecrawl and extracts the structural audit + keyword focus.
2. SERP Analyst → performs competitive analysis with Google Search using the discovered primary keyword.
3. Optimization Advisor → synthesizes the audit and SERP insights into a prioritized optimization report.
"""

from __future__ import annotations
import os
import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Optional, Any
from dotenv import load_dotenv

from uagents import Agent, Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StdioServerParameters
from google.genai import types

# Load environment variables
load_dotenv()

# =============================================================================
# uAgents Configuration
# =============================================================================

# Constants
APP_NAME = "seo_audit_team"
UAGENT_NAME = "seo_audit_chat_agent"

# Sub-agent stage configuration for the SEO audit pipeline
PIPELINE_STAGES: list[dict[str, Any]] = [
    {
        "name": "Page Auditor",
        "emoji": "🔍",
        "agent_name": "PageAuditorAgent",
        "start_indicators": ["scraping", "auditing", "analyzing page"],
        "completion_indicators": ["page_audit", "audit_results", "target_keywords"],
    },
    {
        "name": "SERP Analyst",
        "emoji": "📊",
        "agent_name": "SerpAnalystAgent",
        "start_indicators": ["serp", "searching", "analyzing competitors"],
        "completion_indicators": ["serp_analysis", "top_10_results", "competitor analysis"],
    },
    {
        "name": "Optimization Advisor",
        "emoji": "💡",
        "agent_name": "OptimizationAdvisorAgent",
        "start_indicators": ["generating report", "creating recommendations", "optimization"],
        "completion_indicators": ["SEO Audit Report", "recommendations", "optimization plan"],
    },
]

# Initialize uAgent
agent = Agent(
    name=UAGENT_NAME,
    seed=UAGENT_NAME,
    port=8007,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global ADK runner and session service
adk_runner = None
general_query_runner = None
session_service = None
general_session_service = None

# Track processed messages to prevent duplicates
processed_messages = set()

# =============================================================================
# Output Schemas
# =============================================================================


class HeadingItem(BaseModel):
    tag: str = Field(..., description="Heading tag such as h1, h2, h3.")
    text: str = Field(..., description="Text content of the heading.")


class LinkCounts(BaseModel):
    internal: Optional[int] = Field(None, description="Number of internal links on the page.")
    external: Optional[int] = Field(None, description="Number of external links on the page.")
    broken: Optional[int] = Field(None, description="Number of broken links detected.")
    notes: Optional[str] = Field(
        None, description="Additional qualitative observations about linking."
    )


class AuditResults(BaseModel):
    title_tag: str = Field(..., description="Full title tag text.")
    meta_description: str = Field(..., description="Meta description text.")
    primary_heading: str = Field(..., description="Primary H1 heading on the page.")
    secondary_headings: List[HeadingItem] = Field(
        default_factory=list, description="Secondary headings (H2-H4) in reading order."
    )
    word_count: Optional[int] = Field(
        None, description="Approximate number of words in the main content."
    )
    content_summary: str = Field(
        ..., description="Summary of the main topics and structure of the content."
    )
    link_counts: LinkCounts = Field(
        ...,
        description="Quantitative snapshot of internal/external/broken links.",
    )
    technical_findings: List[str] = Field(
        default_factory=list,
        description="List of notable technical SEO issues (e.g., missing alt text, slow LCP).",
    )
    content_opportunities: List[str] = Field(
        default_factory=list,
        description="Observed content gaps or opportunities for improvement.",
    )


class TargetKeywords(BaseModel):
    primary_keyword: str = Field(..., description="Most likely primary keyword target.")
    secondary_keywords: List[str] = Field(
        default_factory=list, description="Related secondary or supporting keywords."
    )
    search_intent: str = Field(
        ...,
        description="Dominant search intent inferred from the page (informational, transactional, etc.).",
    )
    supporting_topics: List[str] = Field(
        default_factory=list,
        description="Cluster of supporting topics or entities that reinforce the keyword strategy.",
    )


class PageAuditOutput(BaseModel):
    audit_results: AuditResults = Field(..., description="Structured on-page audit findings.")
    target_keywords: TargetKeywords = Field(
        ..., description="Keyword focus derived from page content."
    )


class SerpResult(BaseModel):
    rank: int = Field(..., description="Organic ranking position.")
    title: str = Field(..., description="Title of the search result.")
    url: str = Field(..., description="Landing page URL.")
    snippet: str = Field(..., description="SERP snippet or summary.")
    content_type: str = Field(
        ..., description="Content format (blog post, landing page, tool, video, etc.)."
    )


class SerpAnalysis(BaseModel):
    primary_keyword: str = Field(..., description="Keyword used for SERP research.")
    top_10_results: List[SerpResult] = Field(
        ..., description="Top organic competitors for the keyword."
    )
    title_patterns: List[str] = Field(
        default_factory=list,
        description="Common patterns or phrases used in competitor titles.",
    )
    content_formats: List[str] = Field(
        default_factory=list,
        description="Typical content formats found (guides, listicles, comparison pages, etc.).",
    )
    people_also_ask: List[str] = Field(
        default_factory=list,
        description="Representative questions surfaced in People Also Ask.",
    )
    key_themes: List[str] = Field(
        default_factory=list,
        description="Notable recurring themes, features, or angles competitors emphasize.",
    )
    differentiation_opportunities: List[str] = Field(
        default_factory=list,
        description="Opportunities to stand out versus competitors.",
    )


class OptimizationRecommendation(BaseModel):
    priority: str = Field(..., description="Priority level (P0, P1, P2).")
    area: str = Field(..., description="Optimization focus area (content, technical, UX, etc.).")
    recommendation: str = Field(..., description="Recommended action.")
    rationale: str = Field(..., description="Why this change matters, referencing audit/SERP data.")
    expected_impact: str = Field(..., description="Anticipated impact on SEO or user metrics.")
    effort: str = Field(..., description="Relative effort required (low/medium/high).")


# =============================================================================
# Tools
# =============================================================================

# Firecrawl MCP Toolset - connects to Firecrawl's MCP server for web scraping
# Note: Requires Node.js >= 22.0.0. The default timeout is 5 seconds, increased to 30 for slower systems.
firecrawl_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=[
                "-y",  # Auto-confirm npm package installation
                "firecrawl-mcp",  # The Firecrawl MCP server package
            ],
            env={
                "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "")
            }
        ),
        timeout=30.0  # Increased timeout to 30 seconds for slower systems or Node.js version issues
    ),
    # Filter to use only the scrape tool for this agent
    tool_filter=['firecrawl_scrape']
)


# =============================================================================
# Helper Agents
# =============================================================================


search_executor_agent = LlmAgent(
    name="perform_google_search",
    model="gemini-2.5-flash",
    description="Executes Google searches for provided queries and returns structured results.",
    instruction="""The latest user message contains the keyword to search.
- Call google_search with that exact query and fetch the top organic results (aim for 10).
- Respond with JSON text containing the query and an array of result objects (title, url, snippet). Use an empty array when nothing is returned.
- No additional commentary—return JSON text only.""",
    tools=[google_search],
)

google_search_tool = AgentTool(search_executor_agent)


# =============================================================================
# Agent Definitions
# =============================================================================


page_auditor_agent = LlmAgent(
    name="PageAuditorAgent",
    model="gemini-2.5-flash",
    description=(
        "Scrapes the target URL, performs a structural on-page SEO audit, and extracts keyword signals."
    ),
    instruction="""You are Agent 1 in a sequential SEO workflow. Your role is to gather data silently for the next agents. You must work silently and not show any output to the user.

STEP 1: Extract the URL
- Look for a URL in the user's message (it will start with http:// or https://)
- Example: If user says "Audit https://theunwindai.com", extract "https://theunwindai.com"

STEP 2: Call firecrawl_scrape
- Call `firecrawl_scrape` with these exact parameters:
  url: <the URL you extracted>
  formats: ["markdown", "html", "links"]
  onlyMainContent: true
  timeout: 90000
- Note: timeout is 90 seconds (90000ms)

STEP 3: Analyze the scraped data
- Parse the markdown content to find title tag, meta description, H1, H2-H4 headings
- Count words in the main content
- Count internal and external links
- Identify technical SEO issues
- Identify content opportunities
- Create a content_summary: Write a 2-3 sentence summary of the main topics and structure of the content

STEP 4: Infer keywords
- Based on the page content, determine the primary keyword (1-3 words)
- Identify 2-5 secondary keywords
- Determine search intent (informational, transactional, navigational, commercial)
- List 3-5 supporting topics

STEP 5: Store data internally
- Populate EVERY field in the PageAuditOutput schema with actual data
- CRITICAL: content_summary is REQUIRED - provide a 2-3 sentence summary of main topics and content structure
- CRITICAL: All fields in audit_results must be populated:
  * title_tag (required)
  * meta_description (required)
  * primary_heading (required)
  * secondary_headings (can be empty list)
  * word_count (can be null if not available)
  * content_summary (REQUIRED - must provide summary)
  * link_counts (required - must have internal/external/broken fields)
  * technical_findings (can be empty list)
  * content_opportunities (can be empty list)
- Use "Not available" only if truly missing from scraped data
- Store this data in the state for the next agent
- DO NOT output any JSON or text to the user - work silently""",
    tools=[firecrawl_toolset],
    output_schema=PageAuditOutput,
    output_key="page_audit",
)


serp_analyst_agent = LlmAgent(
    name="SerpAnalystAgent",
    model="gemini-2.5-flash",
    description=(
        "Researches the live SERP for the discovered primary keyword and summarizes the competitive landscape."
    ),
    instruction="""You are Agent 2 in the workflow. Your role is to silently gather SERP data for the final report agent. You must work silently and not show any output to the user.

STEP 1: Get the primary keyword
- Read `state['page_audit']['target_keywords']['primary_keyword']`
- Example: if it's "AI tools", you'll use that for search

STEP 2: Call perform_google_search
- IMPORTANT: You MUST call the `perform_google_search` tool
- Pass the primary keyword as the request parameter
- Example: if primary_keyword is "AI tools", call perform_google_search with request="AI tools"

STEP 3: Parse search results
- You should receive 10+ search results with title, url, snippet
- For each result (up to 10):
  * Assign rank (1-10)
  * Extract title
  * Extract URL
  * Extract snippet
  * Infer content_type (blog post, landing page, tool, directory, video, etc.)

STEP 4: Analyze patterns
- title_patterns: Common words/phrases in titles (e.g., "Best", "Top 10", "Free", year)
- content_formats: Types you see (guides, listicles, comparison pages, tool directories)
- people_also_ask: Related questions (infer from snippets if not explicit)
- key_themes: Recurring topics across results
- differentiation_opportunities: Gaps or unique angles not covered by competitors

STEP 5: Store data internally
- Populate ALL fields in SerpAnalysis schema
- top_10_results MUST have 10 items (or as many as you found)
- DO NOT return empty arrays unless search truly failed
- Store this data in the state for the next agent
- DO NOT output any JSON or text to the user - work silently""",
    tools=[google_search_tool],
    output_schema=SerpAnalysis,
    output_key="serp_analysis",
)


optimization_advisor_agent = LlmAgent(
    name="OptimizationAdvisorAgent",
    model="gemini-2.5-flash",
    description="Synthesizes the audit and SERP findings into a prioritized optimization roadmap.",
    instruction="""You are Agent 3 and the final expert in the workflow. You create the user-facing report. This is the ONLY agent that should output text to the user.

STEP 1: Review the data
- Read `state['page_audit']` for:
  * Title tag, meta description, H1
  * Word count, headings structure
  * Link counts
  * Technical findings
  * Content opportunities
  * Primary and secondary keywords
- Read `state['serp_analysis']` for:
  * Top 10 competitors
  * Title patterns
  * Content formats
  * Key themes
  * Differentiation opportunities

STEP 2: Create the report
Start with "# SEO Audit Report" and include these sections:

1. **Executive Summary** (2-3 paragraphs)
   - Page being audited
   - Primary keyword focus
   - Key strengths and weaknesses

2. **Technical & On-Page Findings**
   Use tables where appropriate for better readability:
   - Title Tag: Create a table with Current | Suggested | Character Count
   - Meta Description: Create a table with Current | Suggested | Character Count
   - H1 and heading structure analysis
   - Word count and content depth
   - Link profile: Create a table with Internal | External | Broken
   - Technical issues found (as a bulleted list)

3. **Keyword Analysis**
   Use a table format:
   | Metric | Value |
   |--------|-------|
   | Primary Keyword | [from state] |
   | Secondary Keywords | [list from state] |
   | Search Intent | [from state] |
   | Supporting Topics | [list from state] |

4. **Competitive SERP Analysis**
   - What top competitors are doing
   - Common title patterns (as a bulleted list)
   - Dominant content formats (as a bulleted list)
   - Key themes in top results (as a bulleted list)
   - Content gaps/opportunities (as a bulleted list)

5. **Prioritized Recommendations**
   Use a table format for each priority level:
   | Priority | Action | Rationale | Expected Impact | Effort |
   |----------|--------|-----------|-----------------|--------|
   | P0 | [action] | [rationale] | [impact] | [effort] |
   
   Group by P0/P1/P2 with clear table headers

6. **Next Steps**
   - Measurement plan (as a bulleted list)
   - Timeline suggestions (as a bulleted list)

STEP 3: Output
- Return ONLY Markdown text with tables
- Use Markdown tables (| column | column |) for structured data
- NO JSON whatsoever
- NO preamble text
- NO intermediate data structures
- Start directly with "# SEO Audit Report"
- Be specific with data points (e.g., "Current title is X characters, recommend Y")
- Include all findings naturally in the text, not as JSON structures
- Write everything in natural, readable text format with proper tables
""",
)


seo_audit_team = SequentialAgent(
    name="SeoAuditTeam",
    description=(
        "Runs a three-agent sequential pipeline that audits a page, researches SERP competitors, "
        "and produces an optimization plan."
    ),
    sub_agents=[
        page_auditor_agent,
        serp_analyst_agent,
        optimization_advisor_agent,
    ],
)


# General query agent for handling non-audit questions
general_query_agent = LlmAgent(
    name="GeneralQueryAgent",
    model="gemini-2.5-flash",
    description="Handles general queries and conversations that are not SEO audit requests.",
    instruction="""You are a helpful assistant for the Google SEO Audit Team. You help users with general questions and conversations.

Your role:
- Answer questions about who you are, what you can do, how to use the SEO audit service
- Have friendly, natural conversations
- Keep responses concise and helpful
- If asked about SEO auditing, briefly explain that users can provide a URL to get a comprehensive SEO audit report

Be friendly, conversational, and helpful. Keep responses natural and not overly formal.""",
)


# Expose the root agent for the ADK runtime and Dev UI.
root_agent = seo_audit_team


# =============================================================================
# uAgents Helper Functions
# =============================================================================


def initialize_adk_agent():
    """Initialize ADK agent with SEO Audit Team SequentialAgent."""
    global adk_runner, session_service
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create session service and runner with the SEO audit team
    session_service = InMemorySessionService()
    adk_runner = Runner(
        agent=seo_audit_team,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    return adk_runner


def initialize_general_query_agent():
    """Initialize ADK agent for general queries."""
    global general_query_runner, general_session_service
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    # Create session service and runner for general queries
    general_session_service = InMemorySessionService()
    general_query_runner = Runner(
        agent=general_query_agent,
        app_name=f"{APP_NAME}_general",
        session_service=general_session_service
    )
    
    return general_query_runner


async def _ensure_session_exists(
    user_id: str,
    session_id: str,
    runner_session_service: Any
):
    """Ensure session exists in runner's session service."""
    try:
        await runner_session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
    except Exception:
        try:
            await runner_session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            pass


def _extract_text_from_event(event):
    """Extract text from ADK event."""
    # Check if it's a final response
    if hasattr(event, 'is_final_response') and event.is_final_response():
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
    
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


def _extract_tool_call_info(event: Any) -> dict[str, Any] | None:
    """Extract tool call information from event for logging."""
    tool_info = None
    
    try:
        # Check for function_call in parts
        if hasattr(event, 'parts') and event.parts is not None:
            parts = event.parts
            if isinstance(parts, (list, tuple)):
                for part in parts:
                    if hasattr(part, 'function_call') and part.function_call is not None:
                        func_call = part.function_call
                        if hasattr(func_call, 'name') and func_call.name:
                            tool_info = {
                                'tool_name': func_call.name,
                                'args': getattr(func_call, 'args', {}) or {}
                            }
                            break
        
        # Check content.parts
        if not tool_info and hasattr(event, 'content') and event.content is not None:
            content = event.content
            if hasattr(content, 'parts') and content.parts is not None:
                parts = content.parts
                if isinstance(parts, (list, tuple)):
                    for part in parts:
                        if hasattr(part, 'function_call') and part.function_call is not None:
                            func_call = part.function_call
                            if hasattr(func_call, 'name') and func_call.name:
                                tool_info = {
                                    'tool_name': func_call.name,
                                    'args': getattr(func_call, 'args', {}) or {}
                                }
                                break
    except (AttributeError, TypeError) as e:
        # Silently handle any errors in extraction
        pass
    
    return tool_info


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
            
            if stage and isinstance(stage, dict):
                stage_name = stage.get("name", "")
                stage_emoji = stage.get("emoji", "")
                
                if stage_name:
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
                        if prev_stage and isinstance(prev_stage, dict):
                            prev_name = prev_stage.get("name", "")
                            prev_emoji = prev_stage.get("emoji", "")
                            if prev_name and prev_name not in self.completed_stages:
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
            "Page Auditor": ["starting page audit", "beginning page audit", "scraping page"],
            "SERP Analyst": ["starting serp analysis", "beginning serp analysis", "analyzing serp"],
            "Optimization Advisor": ["starting optimization", "beginning optimization", "generating report"],
        }
        
        explicit_complete_markers = {
            "Page Auditor": ["page audit complete", "finished page audit"],
            "SERP Analyst": ["serp analysis complete", "finished serp analysis"],
            "Optimization Advisor": ["optimization complete", "report generated"],
        }
        
        # Check for explicit start markers
        if PIPELINE_STAGES:
            for stage in PIPELINE_STAGES:
                if not isinstance(stage, dict):
                    continue
                stage_name = stage.get("name", "")
                if not stage_name:
                    continue
                markers = explicit_start_markers.get(stage_name, [])
                if markers and stage_name not in self.started_stages:
                    if any(marker in text_lower for marker in markers):
                        self.started_stages.add(stage_name)
                        if stage_name != self.last_notified_start:
                            self.last_notified_start = stage_name
                            stage_emoji = stage.get("emoji", "")
                            start_notification = f"{stage_emoji} **Starting {stage_name}...**"
                            break
        
        # Check for explicit completion markers
        if PIPELINE_STAGES:
            for stage in PIPELINE_STAGES:
                if not isinstance(stage, dict):
                    continue
                stage_name = stage.get("name", "")
                if not stage_name:
                    continue
                markers = explicit_complete_markers.get(stage_name, [])
                if markers and stage_name not in self.completed_stages:
                    if any(marker in text_lower for marker in markers):
                        self.completed_stages.add(stage_name)
                        if stage_name != self.last_notified_complete:
                            self.last_notified_complete = stage_name
                            stage_emoji = stage.get("emoji", "")
                            complete_notification = f"{stage_emoji} **{stage_name} Complete**"
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


def _is_json_content(text: str) -> bool:
    """Check if text appears to be JSON content."""
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    # Check if it starts with JSON-like structures
    if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
        # Try to parse as JSON to confirm
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            pass
    # Check for common JSON patterns in SEO audit context
    json_indicators = ['"audit_results"', '"target_keywords"', '"serp_analysis"', '"title_tag"', '"meta_description"', '"primary_keyword"']
    if any(indicator in text for indicator in json_indicators):
        return True
    return False


def _is_audit_request(query: str) -> bool:
    """Check if the query is an SEO audit request (contains a URL)."""
    # Check for URL pattern
    url_pattern = r'https?://[^\s]+'
    if re.search(url_pattern, query, re.IGNORECASE):
        return True
    # Check for audit-related keywords with potential URL
    audit_keywords = ['audit', 'analyze', 'seo', 'optimize', 'review']
    query_lower = query.lower()
    if any(keyword in query_lower for keyword in audit_keywords):
        # If it has audit keywords, assume it might be an audit request
        # But if it's clearly a general question, return False
        general_questions = ['who are you', 'what can you do', 'what are you', 'how does this work', 'help', 'hello', 'hi']
        if any(gq in query_lower for gq in general_questions) and not re.search(url_pattern, query, re.IGNORECASE):
            return False
    return False


async def _process_general_query(query: str, sender: str, session_id: str, ctx: Context) -> str:
    """Handle general queries that are not SEO audit requests using Gemini."""
    global general_query_runner
    
    if general_query_runner is None:
        initialize_general_query_agent()
    
    try:
        # Ensure session exists
        try:
            await general_session_service.create_session(
                app_name=f"{APP_NAME}_general",
                user_id=sender,
                session_id=session_id
            )
        except Exception:
            try:
                await general_session_service.get_session(
                    app_name=f"{APP_NAME}_general",
                    user_id=sender,
                    session_id=session_id
                )
            except Exception:
                pass
        
        # Create message content
        content = types.Content(role='user', parts=[types.Part(text=query)])
        response_parts = []
        
        # Run general query agent
        async for event in general_query_runner.run_async(
            user_id=sender,
            session_id=session_id,
            new_message=content
        ):
            # Check for final response
            if hasattr(event, 'is_final_response') and event.is_final_response():
                if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_parts.append(part.text)
            
            # Extract text from event and send as progress
            text = _extract_text_from_event(event)
            if text and text not in response_parts:
                response_parts.append(str(text))
                # Send text as it arrives
                await send_progress_message(ctx, sender, str(text))
        
        return ' '.join(response_parts).strip() if response_parts else "I'm here to help! How can I assist you today?"
        
    except Exception as e:
        return f"Hello! I'm the Google SEO Audit Team agent. I help analyze websites for SEO optimization. To get started, provide me with a URL to audit (e.g., 'Audit https://example.com')."


async def process_with_adk(query: str, sender: str, ctx: Context) -> str:
    """Process query using ADK runner with SEO Audit Team and streaming progress updates."""
    global adk_runner
    
    # Check if it's a general query (no URL)
    if not _is_audit_request(query):
        return await _process_general_query(query, sender, str(ctx.session), ctx)
    
    if adk_runner is None:
        initialize_adk_agent()
    
    try:
        await _ensure_session_exists(sender, str(ctx.session), adk_runner.session_service)
        
        # Extract URL for logging
        url_pattern = r'https?://[^\s]+'
        url_match = re.search(url_pattern, query, re.IGNORECASE)
        target_url = url_match.group(0) if url_match else "unknown"
        session_id = str(ctx.session)
        ctx.logger.info(f"🔍 Starting SEO audit for URL: {target_url} | Session ID: {session_id}")
        
        # Send initial processing message
        await send_progress_message(ctx, sender, "⏳ Processing SEO audit...")
        
        # Create message and run the pipeline
        new_message = types.Content(parts=[types.Part(text=query)])
        response_parts: list[str] = []
        
        # Use StageTracker for stable stage detection
        tracker = StageTracker()
        last_agent: str | None = None
        report_sent = False
        
        async for event in adk_runner.run_async(
            user_id=sender,
            session_id=session_id,
            new_message=new_message
        ):
            try:
                # Log Firecrawl tool calls
                tool_info = _extract_tool_call_info(event)
                if tool_info and tool_info.get('tool_name') == 'firecrawl_scrape':
                    url_arg = tool_info.get('args', {}).get('url', 'unknown') if tool_info.get('args') else 'unknown'
                    ctx.logger.info(f"🔥 Firecrawl: Scraping URL -> {url_arg} | Session ID: {session_id}")
                    await send_progress_message(ctx, sender, f"⏳ Processing... Scraping page content...")
                
                # Log Google Search tool calls
                if tool_info and tool_info.get('tool_name'):
                    tool_name = str(tool_info.get('tool_name', '')).lower()
                    if 'google_search' in tool_name:
                        args = tool_info.get('args', {}) or {}
                        search_query = args.get('query') or args.get('request', 'unknown')
                        ctx.logger.info(f"🔎 Google Search: Query -> {search_query} | Session ID: {session_id}")
                        await send_progress_message(ctx, sender, f"⏳ Processing... Analyzing SERP data...")
                
                text = _extract_text_from_event(event)
                if text:
                    response_parts.append(str(text))
                
                # Process event through tracker (uses agent metadata when available)
                start_notification, complete_notification = tracker.process_event(event, text)
                
                # Get current agent name
                current_agent = get_agent_from_event(event)
                
                # Detect agent change - send completion for previous agent
                if current_agent and current_agent != last_agent and last_agent:
                    # Previous agent completed, send completion notification
                    prev_stage = get_stage_by_agent_name(last_agent)
                    if prev_stage:
                        prev_name = prev_stage.get("name", "")
                        prev_emoji = prev_stage.get("emoji", "")
                        if prev_name and prev_name not in tracker.completed_stages:
                            tracker.completed_stages.add(prev_name)
                            # Clean up logging - remove extra spaces
                            ctx.logger.info(f"✅{prev_name}completed | Session ID: {session_id}")
                            await send_progress_message(ctx, sender, f"⏳ Processing... {prev_emoji} {prev_name} complete")
                
                # Send start notification when new agent starts
                if start_notification:
                    # Clean up logging - remove markdown formatting and extra spaces
                    log_msg = start_notification.replace('**', '').replace('...', '').replace(' ', '').strip()
                    ctx.logger.info(f"🚀{log_msg} | Session ID: {session_id}")
                    await send_progress_message(ctx, sender, f"⏳ Processing... {start_notification.replace('**', '')}")
                
                # Update last agent
                if current_agent:
                    last_agent = current_agent
                
                # Collect response text but don't send it yet - we'll send full report at the end
                # Only collect if it's from Optimization Advisor (the final report)
                if text and not _is_json_content(text):
                    # Check if this is the final report (starts with # SEO Audit Report)
                    if text.strip().startswith('# SEO Audit Report') or current_agent == "OptimizationAdvisorAgent":
                        # Mark that we're generating the report
                        if not report_sent:
                            report_sent = True
                    # For other agents, we don't collect their output (they work silently)
            except Exception as e:
                ctx.logger.error(f"Error processing event: {str(e)} | Session ID: {session_id}", exc_info=True)
                # Continue processing other events
                continue
        
        # Finalize - mark last stage as complete if needed
        if last_agent:
            final_stage = get_stage_by_agent_name(last_agent)
            if final_stage and final_stage["name"] not in tracker.completed_stages:
                tracker.completed_stages.add(final_stage["name"])
                # Clean up logging - remove extra spaces
                ctx.logger.info(f"✅{final_stage['name']}completed | Session ID: {session_id}")
                await send_progress_message(ctx, sender, f"⏳ Processing... {final_stage['emoji']} {final_stage['name']} complete")
        
        # Join all parts and clean up
        if not response_parts:
            response_parts = []
        
        full_response = ' '.join(str(part) for part in response_parts if part).strip() if response_parts else ""
        
        # If response contains JSON blocks, extract only the markdown part
        if full_response and '# SEO Audit Report' in full_response:
            # Find the start of the markdown report
            report_start = full_response.find('# SEO Audit Report')
            if report_start > 0:
                full_response = full_response[report_start:]
        
        # Remove any remaining JSON-like content at the beginning
        if full_response:
            lines = full_response.split('\n')
            cleaned_lines = []
            skip_until_markdown = True
            
            for line in lines:
                if skip_until_markdown:
                    if line.strip().startswith('#'):
                        skip_until_markdown = False
                        cleaned_lines.append(line)
                    elif not _is_json_content(line):
                        # If it's not JSON and not markdown header, might be preamble - skip
                        continue
                else:
                    cleaned_lines.append(line)
            
            final_response = '\n'.join(cleaned_lines).strip()
        else:
            final_response = ""
        
        # Send full report once at the end
        if final_response and final_response.strip():
            ctx.logger.info(f"✅ SEO audit completed for URL: {target_url} | Session ID: {session_id}")
            await send_progress_message(ctx, sender, final_response)
            return final_response
        else:
            ctx.logger.warning(f"⚠️ No report generated for URL: {target_url} | Session ID: {session_id}")
            return "No response from ADK agent"
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing SEO audit: {str(e)}")
        await send_progress_message(ctx, sender, f"❌ Error: {str(e)}")
        return f"Error processing query: {str(e)}"


# =============================================================================
# uAgents Event Handlers
# =============================================================================


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize ADK agents on startup."""
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    try:
        initialize_adk_agent()
        initialize_general_query_agent()
        ctx.logger.info("ADK SEO audit team and general query agent initialized successfully")
    except Exception as e:
        ctx.logger.error(f"Failed to initialize ADK agents: {str(e)}")


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
        
        # Process query and send response (with streaming progress updates)
        # The process_with_adk function now sends the full report directly
        response_text = await process_with_adk(text_content, sender, ctx)
        
        # Note: Full report is already sent by process_with_adk, so we don't need to send again
        ctx.logger.info(f"SEO audit process completed for {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {str(e)}")
        # Remove from processed set on error so it can be retried
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


if __name__ == "__main__":
    agent.run()
