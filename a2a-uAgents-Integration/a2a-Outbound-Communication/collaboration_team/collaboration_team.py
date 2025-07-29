import asyncio
from pathlib import Path
from textwrap import dedent
from typing import List
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunResponse
from agno.models.openai import OpenAIChat
from agno.team.team import Team
from agno.tools.arxiv import ArxivTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.googlesearch import GoogleSearchTools
from agno.tools.hackernews import HackerNewsTools
from typing_extensions import override

# Remove the creation of a local download directory if you don't want to save PDFs
# arxiv_download_dir = Path(__file__).parent.joinpath("tmp", f"arxiv_pdfs__{uuid4().hex}")
# arxiv_download_dir.mkdir(parents=True, exist_ok=True)
# print(f"DEBUG: Arxiv download directory created at: {arxiv_download_dir}")

# Define individual agents for the team
reddit_researcher = Agent(
    name="Reddit Researcher",
    role="Research a topic on Reddit",
    model=OpenAIChat(id="gpt-4o"),
    tools=[DuckDuckGoTools()], # DuckDuckGo can search Reddit
    add_name_to_instructions=True,
    instructions=dedent("""
    You are a Reddit researcher.
    You will be given a topic to research on Reddit.
    Use the DuckDuckGo search tool to find the most relevant posts and discussions on Reddit for the given topic.
    Prioritize results from reddit.com.
    Summarize key insights and common opinions found.
    """),
)

hackernews_researcher = Agent(
    name="HackerNews Researcher",
    model=OpenAIChat("gpt-4o"),
    role="Research a topic on HackerNews.",
    tools=[HackerNewsTools()],
    add_name_to_instructions=True,
    instructions=dedent("""
    You are a HackerNews researcher.
    You will be given a topic to research on HackerNews.
    Use the HackerNewsTools to find the most relevant posts and discussions on HackerNews.
    Summarize key insights, popular articles, and technical discussions.
    """),
)

academic_paper_researcher = Agent(
    name="Academic Paper Researcher",
    model=OpenAIChat("gpt-4o"),
    role="Research academic papers and scholarly content",
    # Initialize ArxivTools WITHOUT a download_dir, or with a dummy one if required by the tool's constructor
    # The key is to instruct the agent NOT to use the download/read functions.
    tools=[GoogleSearchTools(), ArxivTools()], # Removed download_dir
    add_name_to_instructions=True,
    instructions=dedent("""
    You are an academic paper researcher.
    You will be given a topic to research in academic literature.
    Use GoogleSearchTools to find relevant scholarly articles and papers.
    **CRITICAL: When using ArxivTools, ONLY use the 'search_arxiv_and_return_articles' function to get paper metadata and links. DO NOT use 'read_arxiv_papers' or any function that downloads content.**
    Focus on peer-reviewed content and citations from reputable sources.
    Provide brief summaries of key findings and methodologies, and **ALWAYS include the direct link (PDF or Arxiv page URL) to the paper** for the user to access.
    """),
)

twitter_researcher = Agent(
    name="Twitter Researcher",
    model=OpenAIChat("gpt-4o"),
    role="Research trending discussions and real-time updates",
    tools=[DuckDuckGoTools()], # DuckDuckGo can search Twitter/X
    add_name_to_instructions=True,
    instructions=dedent("""
    You are a Twitter/X researcher.
    You will be given a topic to research on Twitter/X.
    Use the DuckDuckGo search tool to find trending discussions, influential voices, and real-time updates on Twitter/X.
    Focus on verified accounts and credible sources when possible.
    Track relevant hashtags and ongoing conversations.
    Summarize the sentiment and key points from the discussions.
    """),
)

# Define the agent team
discussion_team = Team(
    name="Discussion Team",
    mode="collaborate",
    model=OpenAIChat("gpt-4o"),
    members=[
        reddit_researcher,
        hackernews_researcher,
        academic_paper_researcher,
        twitter_researcher,
    ],
    instructions=[
        "You are a discussion master. Your goal is to facilitate a comprehensive discussion among your team members on the given topic.",
        "Ensure each researcher contributes their unique findings from their respective platforms.",
        "Synthesize the information from all team members to provide a holistic answer.",
        "You must stop the discussion when you think the team has reached a consensus and a comprehensive answer has been formed.",
        "**CRITICAL: Manage context length carefully. After each team member's contribution, summarize their key findings concisely before proceeding with the next step or synthesizing. Do not include entire raw outputs from tools or lengthy individual reports if they are excessively long.**",
        "**IMPORTANT: For academic papers, ensure that the Academic Paper Researcher provides direct links to the PDFs or Arxiv pages, and does NOT download any files.**"
    ],
    success_criteria="The team has reached a consensus and provided a comprehensive answer to the topic.",
    enable_agentic_context=True,
    show_tool_calls=True,
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
            result: RunResponse = await asyncio.wait_for(self.agent_team.arun(message), timeout=600) # 10 minutes timeout
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
