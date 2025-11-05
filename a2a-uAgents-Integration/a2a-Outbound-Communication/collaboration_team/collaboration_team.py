
import asyncio
from pathlib import Path
from textwrap import dedent
from typing import List
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunOutput
from agno.models.google import Gemini
from agno.team.team import Team
from agno.tools.arxiv import ArxivTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.googlesearch import GoogleSearchTools
from typing_extensions import override

reddit_researcher = Agent(
    name="Reddit Researcher",
    role="Research a topic on Reddit",
    model=Gemini(id="gemini-2.0-flash"), 
    tools=[GoogleSearchTools()], # Use Google Search instead of DuckDuckGo for better reliability
    instructions=dedent("""
    You are a Reddit researcher specializing in detailed community analysis.
    You will be given a topic to research on Reddit.
    Use the Google Search tool to find the most relevant posts and discussions on Reddit for the given topic.
    Search for "site:reddit.com" followed by your topic to find Reddit content.
    
    For each finding, provide:
    - Direct links to Reddit posts/threads when available
    - Specific subreddit names and their focus
    - Upvote counts and engagement metrics when visible
    - Direct quotes from top comments
    - Community sentiment analysis (positive/negative/neutral)
    - Specific examples and use cases mentioned
    
    Structure your response with clear sections and bullet points.
    Include at least 5-7 specific Reddit discussions with detailed analysis.
    
    **MANDATORY: Create a summary table with the following columns:**
    | Subreddit | Post Title | Upvotes | Comments | Sentiment | Key Insight |
    |-----------|------------|---------|----------|-----------|-------------|
    
    **MANDATORY: Always include direct links in this format: [Post Title](URL)**
    **MANDATORY: Use markdown formatting for better readability**
    """),
)

hackernews_researcher = Agent(
    name="HackerNews Researcher",
    model=Gemini(id="gemini-2.0-flash"),
    role="Research a topic on HackerNews.",
    tools=[GoogleSearchTools()], # Use Google Search instead of DuckDuckGo for better reliability
    instructions=dedent("""
    You are a HackerNews researcher specializing in technical and industry analysis.
    You will be given a topic to research on HackerNews.
    Use the Google Search tool to find the most relevant posts and discussions on HackerNews.
    Search for "site:news.ycombinator.com" or "site:hackernews.com" to find HackerNews content.
    
    For each finding, provide:
    - Direct links to HN posts
    - Points (upvotes) and comment counts when visible
    - Key technical insights and code examples
    - Industry implications and business impact
    - Technical challenges and solutions discussed
    - Links to related projects, papers, or tools mentioned
    - Expert opinions from notable HN users
    
    Structure your response with:
    - Top posts by engagement
    - Technical deep-dives
    - Industry implications
    - Future trends discussed
    
    Include at least 8-10 specific HN discussions with detailed analysis.
    
    **MANDATORY: Create a summary table with the following columns:**
    | Post Title | Points | Comments | Technical Focus | Industry Impact | Key Insight |
    |------------|--------|----------|-----------------|-----------------|-------------|
    
    **MANDATORY: Always include direct links in this format: [Post Title](URL)**
    **MANDATORY: Use markdown formatting for better readability**
    """),
)

academic_paper_researcher = Agent(
    name="Academic Paper Researcher",
    model=Gemini(id="gemini-2.0-flash"),
    role="Research academic papers and scholarly content",
    tools=[GoogleSearchTools(), ArxivTools()],
    instructions=dedent("""
    You are an academic paper researcher specializing in comprehensive literature analysis.
    You will be given a topic to research in academic literature.
    Use GoogleSearchTools to find relevant scholarly articles and papers.
    
    **CRITICAL: When using ArxivTools, ONLY use the 'search_arxiv_and_return_articles' function to get paper metadata and links. DO NOT use 'read_arxiv_papers' or any function that downloads content.**
    
    For each academic source, provide:
    - Complete paper title and authors
    - Publication venue and date
    - Direct link to paper (PDF or Arxiv page URL)
    - Abstract or key findings
    - Methodology used
    - Sample size and data sources
    - Key conclusions and implications
    - Citation count when available
    - Related research areas
    
    Structure your response with:
    - Recent papers (last 2 years)
    - High-impact papers (high citations)
    - Systematic reviews and meta-analyses
    - Empirical studies with data
    
    Include at least 10-15 academic sources with detailed analysis.
    
    **MANDATORY: Create a summary table with the following columns:**
    | Paper Title | Authors | Publication | Year | Citations | Key Finding | Direct Link |
    |-------------|---------|-------------|------|-----------|-------------|-------------|
    
    **MANDATORY: Always include direct links in this format: [Paper Title](URL)**
    **MANDATORY: Use markdown formatting for better readability**
    """),
)

twitter_researcher = Agent(
    name="Twitter Researcher",
    model=Gemini(id="gemini-2.0-flash"),
    role="Research trending discussions and real-time updates",
    tools=[GoogleSearchTools()], # Use Google Search instead of DuckDuckGo for better reliability
    instructions=dedent("""
    You are a Twitter/X researcher specializing in real-time trend analysis.
    You will be given a topic to research on Twitter/X.
    Use the Google Search tool to find trending discussions, influential voices, and real-time updates on Twitter/X.
    Search for "site:twitter.com" or "site:x.com" followed by your topic to find Twitter content.
    
    For each finding, provide:
    - Direct links to tweets when available
    - Username and follower count of key voices
    - Hashtags and trending topics
    - Engagement metrics (likes, retweets, replies)
    - Sentiment analysis (positive/negative/neutral/mixed)
    - Key influencers and thought leaders
    - Viral content and discussions
    - Real-time developments and breaking news
    - Public reactions and community responses
    
    Structure your response with:
    - Trending hashtags and topics
    - Influential voices and their perspectives
    - Viral discussions and their impact
    - Sentiment trends over time
    - Emerging concerns and opportunities
    
    Include at least 8-10 specific Twitter discussions with detailed analysis.
    Focus on verified accounts and credible sources when possible.
    
    **MANDATORY: Create a summary table with the following columns:**
    | Username | Followers | Tweet Content | Engagement | Sentiment | Key Point | Direct Link |
    |----------|-----------|---------------|------------|-----------|-----------|-------------|
    
    **MANDATORY: Always include direct links in this format: [Tweet Content](URL)**
    **MANDATORY: Use markdown formatting for better readability**
    """),
)

# Define the agent team
discussion_team = Team(
    name="Discussion Team",
    model=Gemini(id="gemini-2.0-flash"),
    members=[
        reddit_researcher,
        hackernews_researcher,
        academic_paper_researcher,
        twitter_researcher,
    ],
    instructions=[
        "You are a discussion master specializing in comprehensive, well-structured analysis. Your goal is to facilitate a detailed discussion among your team members on the given topic.",
        "Ensure each researcher contributes their unique findings from their respective platforms with specific examples, links, and detailed analysis.",
        "Synthesize the information from all team members to provide a holistic, comprehensive answer.",
        "Structure the final response with clear sections, tables, and organized information.",
        "**CRITICAL: Manage context length carefully. After each team member's contribution, summarize their key findings concisely before proceeding with the next step or synthesizing. Do not include entire raw outputs from tools or lengthy individual reports if they are excessively long.**",
        "**IMPORTANT: For academic papers, ensure that the Academic Paper Researcher provides direct links to the PDFs or Arxiv pages, and does NOT download any files.**",
        "**FORMATTING REQUIREMENTS:**",
        "- Use markdown formatting for better readability",
        "- Create tables to summarize key findings when appropriate",
        "- Use bullet points and numbered lists for organization",
        "- Include direct links to sources whenever possible",
        "- Provide specific examples and use cases",
        "- Structure the final response with clear sections: Executive Summary, Detailed Findings, Impact Analysis, Recommendations, and Conclusion",
        "- Include quantitative data and metrics when available",
        "- Provide both positive and negative perspectives with balanced analysis",
        "**MANDATORY FINAL OUTPUT STRUCTURE:**",
        "1. **Executive Summary** - 2-3 paragraph overview",
        "2. **Detailed Findings by Platform** - Each agent's findings with their tables",
        "3. **Cross-Platform Analysis** - Comparison and synthesis tables",
        "4. **Impact Assessment** - Positive/Negative impacts in table format",
        "5. **Recommendations** - Actionable insights",
        "6. **Conclusion** - Summary of key takeaways",
        "**MANDATORY: Ensure ALL agents create their summary tables as specified in their instructions**",
        "**MANDATORY: Include ALL direct links provided by agents in the final response**",
        "**MANDATORY: Create at least 3 summary tables in the final response**"
    ],
    markdown=True,
    show_members_responses=True,
)

class DiscussionTeamExecutor(AgentExecutor):
    """
    AgentExecutor wrapper for the agno.team discussion team.
    """
    def __init__(self):
        self.agent_team = discussion_team

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        message_content = ""
        for part in context.message.parts:
            if isinstance(part, Part):
                if isinstance(part.root, TextPart):
                    message_content = part.root.text
                    break
        
        if not message_content:
            await event_queue.enqueue_event(new_agent_text_message("Error: No message content received."))
            return

        message: Message = Message(role="user", content=message_content)
        print(f"DEBUG: [DiscussionTeamExecutor] Received message: {message.content}")
        
        try:
            print("DEBUG: [DiscussionTeamExecutor] Starting agno team run with timeout...")
            # Set a very generous timeout for the agno team's execution (e.g., 10 minutes)
            # Team discussions with multiple tools can take a long time.
            result: RunOutput = await asyncio.wait_for(self.agent_team.arun(message), timeout=600) # 10 minutes timeout
            print(f"DEBUG: [DiscussionTeamExecutor] Agno team finished run. Response content type: {type(result.content)}")
            
            response_text = str(result.content) 
            await event_queue.enqueue_event(new_agent_text_message(response_text))
            print("DEBUG: [DiscussionTeamExecutor] Event enqueued successfully.")

        except asyncio.TimeoutError:
            error_message = "Agno team execution timed out. The discussion might be too complex or require more time."
            print(f"❌ {error_message}")
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please try again or simplify your query."))
        except Exception as e:
            error_message = f"Error during agno agent execution: {e}"
            print(f"❌ {error_message}")
            import traceback
            traceback.print_exc()
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please check logs for details."))
        
        print("DEBUG: [DiscussionTeamExecutor] execute method finished.")

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported for this agent executor.")