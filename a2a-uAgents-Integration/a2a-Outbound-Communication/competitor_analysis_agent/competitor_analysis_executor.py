import asyncio
from textwrap import dedent
from typing import List
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunResponse
from agno.models.openai import OpenAIChat
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.reasoning import ReasoningTools
from typing_extensions import override

# Define your agno.agent competitor analysis agent
competitor_analysis_agno_agent = Agent(
    model=OpenAIChat(id="gpt-4o"), # Using gpt-4o as a standard available model
    tools=[
        FirecrawlTools(
            search=True,
            crawl=True,
            mapping=True,
            formats=["markdown", "links", "html"],
            search_params={"limit": 1}, # REDUCED: Limit search results to 1
            limit=1, # REDUCED: Limit crawl depth/pages to 1
        ),
        ReasoningTools(
            add_instructions=True,
        ),
    ],
    instructions=[
        "You are a highly efficient and context-aware AI agent specializing in competitor analysis.",
        "**CRITICAL: STRICTLY MANAGE CONTEXT LENGTH. After using Firecrawl (search or crawl), IMMEDIATELY summarize the most relevant information (max 500 words) before any other action. Do NOT include raw, lengthy outputs from tools. Prioritize key facts, product details, and market positioning.**",
        "1. Initial Research & Discovery:",
        "   - Use search tool to find information about the target company",
        "   - Search for '[company name] competitors', 'companies like [company name]'",
        "   - Search for industry reports and market analysis",
        "   - Use the think tool to plan your research approach",
        "2. Competitor Identification:",
        "   - Search for each identified competitor using Firecrawl",
        "   - Find their official websites and key information sources",
        "   - Map out the competitive landscape",
        "3. Website Analysis:",
        "   - Scrape competitor websites using Firecrawl",
        "   - Map their site structure to understand their offerings",
        "   - Extract product information, pricing, and value propositions",
        "   - Look for case studies and customer testimonials",
        "4. Deep Competitive Analysis:",
        "   - Use the analyze tool after gathering information on each competitor",
        "   - Compare features, pricing, and market positioning",
        "   - Identify patterns and competitive dynamics",
        "   - Think through the implications of your findings",
        "5. Strategic Synthesis:",
        "   - Conduct SWOT analysis for each major competitor",
        "   - Use reasoning to identify competitive advantages",
        "   - Analyze market trends and opportunities",
        "   - Develop strategic recommendations",
        "- Always use the think tool before starting major research phases",
        "- Use the analyze tool to process findings and draw insights",
        "- Search for multiple perspectives on each competitor",
        "- Verify information by checking multiple sources",
        "- Be thorough but focused in your analysis",
        "- Provide evidence-based recommendations",
    ],
    expected_output=dedent(
        """\
    # Competitive Analysis Report: {Target Company}
    ## Executive Summary
    {High-level overview of competitive landscape and key findings}
    ## Research Methodology
    - Search queries used
    - Websites analyzed
    - Key information sources
    ## Market Overview
    ### Industry Context
    - Market size and growth rate
    - Key trends and drivers
    - Regulatory environment
    ### Competitive Landscape
    - Major players identified
    - Market segmentation
    - Competitive dynamics
    ## Competitor Analysis
    ### Competitor 1: {Name}
    #### Company Overview
    - Website: {URL}
    - Founded: {Year}
    - Headquarters: {Location}
    - Company size: {Employees/Revenue if available}
    #### Products & Services
    - Core offerings
    - Key features and capabilities
    - Pricing model and tiers
    - Target market segments
    #### Digital Presence Analysis
    - Website structure and user experience
    - Key messaging and value propositions
    - Content strategy and resources
    - Customer proof points
    #### SWOT Analysis
    **Strengths:**
    - {Evidence-based strengths}
    **Weaknesses:**
    - {Identified weaknesses}
    **Opportunities:**
    - {Market opportunities}
    **Threats:**
    - {Competitive threats}
    ### Competitor 2: {Name}
    {Similar structure as above}
    ### Competitor 3: {Name}
    {Similar structure as above}
    ## Comparative Analysis
    ### Feature Comparison Matrix
    | Feature | {Target} | Competitor 1 | Competitor 2 | Competitor 3 |
    |---------|----------|--------------|--------------|--------------|
    | {Feature 1} | ✓/✗ | ✓/✗ | ✓/✗ | ✓/✗ |
    | {Feature 2} | ✓/✗ | ✓/✗ | ✓/✗ | ✓/✗ |
    ### Pricing Comparison
    | Company | Entry Level | Professional | Enterprise |
    |---------|-------------|--------------|------------|
    | {Pricing details extracted from websites} |
    ### Market Positioning Analysis
    {Analysis of how each competitor positions themselves}
    ## Strategic Insights
    ### Key Findings
    1. {Major insight with evidence}
    2. {Competitive dynamics observed}
    3. {Market gaps identified}
    ### Competitive Advantages
    - {Target company's advantages}
    - {Unique differentiators}
    ### Competitive Risks
    - {Main threats from competitors}
    - {Market challenges}
    ## Strategic Recommendations
    ### Immediate Actions (0-3 months)
    1. {Quick competitive responses}
    2. {Low-hanging fruit opportunities}
    ### Short-term Strategy (3-12 months)
    1. {Product/service enhancements}
    2. {Market positioning adjustments}
    ### Long-term Strategy (12+ months)
    1. {Sustainable differentiation}
    2. {Market expansion opportunities}
    ## Conclusion
    {Summary of competitive position and strategic imperatives}
    """
    ),
    markdown=True,
    show_tool_calls=True,
    add_datetime_to_instructions=True,
    stream_intermediate_steps=True,
)

class CompetitorAnalysisExecutor(AgentExecutor):
    """
    AgentExecutor wrapper for the agno.agent competitor analysis agent.
    """
    def __init__(self):
        self.agent = competitor_analysis_agno_agent

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
        print(f"DEBUG: [CompetitorAnalysisExecutor] Received message: {message.content}")
        
        try:
            print("DEBUG: [CompetitorAnalysisExecutor] Starting agno agent run with timeout...")
            # Set a generous timeout for the agno agent's execution, as it involves web searches/crawling
            result: RunResponse = await asyncio.wait_for(self.agent.arun(message), timeout=300) # 5 minutes timeout
            print(f"DEBUG: [CompetitorAnalysisExecutor] Agno agent finished run. Response content type: {type(result.content)}")
            
            response_text = str(result.content) 
            await event_queue.enqueue_event(new_agent_text_message(response_text))
            print("DEBUG: [CompetitorAnalysisExecutor] Event enqueued successfully.")

        except asyncio.TimeoutError:
            error_message = "Agno agent execution timed out. The analysis might be too complex or require more time."
            print(f"❌ {error_message}")
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please try again or simplify your query."))
        except Exception as e:
            error_message = f"Error during agno agent execution: {e}"
            print(f"❌ {error_message}")
            import traceback
            traceback.print_exc()
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please check logs for details."))
        
        print("DEBUG: [CompetitorAnalysisExecutor] execute method finished.")

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported for this agent executor.")
