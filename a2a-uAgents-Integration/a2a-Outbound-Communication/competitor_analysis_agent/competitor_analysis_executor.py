import asyncio
from textwrap import dedent
from typing import List
from uuid import uuid4
import dotenv

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunOutput
from agno.models.google import Gemini
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.reasoning import ReasoningTools
from typing_extensions import override

# Load environment variables from .env file
dotenv.load_dotenv()

# Define your agno.agent competitor analysis agent
competitor_analysis_agno_agent = Agent(
    model=Gemini(id="gemini-2.0-flash"),
    tools=[
        FirecrawlTools(
            enable_scrape=True,
            enable_search=True,
            enable_crawl=True,
            enable_mapping=True,
            formats=["markdown", "links", "html"],
            search_params={"limit": 1}, # REDUCED: Limit search results to 1
            limit=1, # REDUCED: Limit crawl depth/pages to 1
        ),
        ReasoningTools(),
    ],
    instructions=[
        "You are a highly detailed AI agent specializing in comprehensive competitor analysis with structured data presentation.",
        "**CRITICAL: STRICTLY MANAGE CONTEXT LENGTH. After using Firecrawl (search or crawl), IMMEDIATELY summarize the most relevant information (max 500 words) before any other action. Do NOT include raw, lengthy outputs from tools. Prioritize key facts, product details, and market positioning.**",
        "**OUTPUT FORMAT REQUIREMENTS:**",
        "- Use markdown tables extensively for comparisons and data",
        "- Include market size, growth rates, and financial metrics when available",
        "- Create detailed comparison matrices for features, pricing, and positioning",
        "- Provide company profiles with: Founded, HQ, Employees, Revenue, Website links",
        "- Use SWOT tables for each major competitor",
        "- Include risk assessment matrix with mitigation strategies",
        "- Add resource links section with relevant industry reports and websites",
        "",
        "**RESEARCH METHODOLOGY:**",
        "1. Initial Research & Discovery:",
        "   - Use search tool to find information about the target company and industry",
        "   - Search for '[company name] competitors', 'companies like [company name]'",
        "   - Search for industry reports, market size, and growth rates",
        "   - Use the think tool to plan your research approach",
        "",
        "2. Market Overview:",
        "   - Identify market size, growth rate, and key trends",
        "   - Create market segmentation table with size and growth for each segment",
        "   - Identify regulatory environment and compliance requirements",
        "",
        "3. Competitive Landscape Mapping:",
        "   - Identify top 5-10 competitors in the space",
        "   - Create Market Leaders table with market share, size, revenue",
        "   - Create Challengers table for emerging players",
        "   - Include company profiles with founded date, HQ, employees, revenue, website",
        "",
        "4. Detailed Competitor Analysis:",
        "   - For each major competitor (top 3-5):",
        "     * Company overview with full details",
        "     * Business model and revenue streams",
        "     * Key products/services with descriptions",
        "     * Market positioning and value proposition",
        "     * SWOT analysis in table format",
        "",
        "5. Comparative Analysis:",
        "   - Feature Comparison Matrix: Compare features across all competitors",
        "   - Pricing Comparison Table: Show all pricing tiers and plans",
        "   - Target Market Segmentation: Show which markets each competitor targets",
        "   - Technology Stack: Compare technical capabilities",
        "",
        "6. Strategic Analysis:",
        "   - Identify market gaps and opportunities with descriptions",
        "   - Create Strategic Recommendations with timeframes (0-3, 3-12, 12+ months)",
        "   - Risk Assessment Matrix: Risk level, description, mitigation strategy",
        "   - Include competitive advantages and risks",
        "",
        "7. Final Deliverables:",
        "   - Key Resources & Links: Include all relevant websites and reports",
        "   - Conclusion with actionable insights",
        "",
        "**MANDATORY TABLES TO INCLUDE:**",
        "- Market Segmentation Table",
        "- Market Leaders Table",
        "- Challengers Table", 
        "- SWOT Analysis Tables (for each top competitor)",
        "- Feature Comparison Matrix",
        "- Pricing Comparison Table",
        "- Target Market Segmentation Table",
        "- Risk Assessment Matrix",
        "",
        "Use the think and analyze tools throughout to ensure comprehensive coverage.",
    ],
    expected_output=dedent(
        """\
    # Competitive Analysis Report: {Target Company/Industry}
    
    ## Executive Summary
    {Concise overview with market size, growth rate, and key competitive insights}
    
    ## Market Overview
    
    ### Industry Context
    - **Market Size**: ${X}B (2024) with X% annual growth
    - **Key Trends**: {List 3-5 major trends}
    - **Growth Rate**: X% CAGR projected through 20XX
    - **Regulatory Environment**: {Key regulations affecting the market}
    
    ### Market Segmentation
    | Segment | Description | Size | Growth | Key Players |
    |---------|-------------|------|--------|-------------|
    | {Segment 1} | {Description} | ${X}B | X% | {Companies} |
    | {Segment 2} | {Description} | ${X}B | X% | {Companies} |
    
    ## Competitive Landscape Map
    
    ### Market Leaders (Top Tier)
    | Company | Market Share | Founded | HQ | Employees | Revenue | Website |
    |---------|--------------|---------|----|-----------|---------|---------| 
    | {Company 1} | X% | {Year} | {Location} | {Count} | ${X}M | [{url}]({url}) |
    | {Company 2} | X% | {Year} | {Location} | {Count} | ${X}M | [{url}]({url}) |
    
    ### Challengers (Second Tier)
    | Company | Market Position | Founded | HQ | Key Strength | Website |
    |---------|----------------|---------|----|--------------|---------|
    | {Company 3} | {Position} | {Year} | {Location} | {Strength} | [{url}]({url}) |
    
    ## Detailed Competitor Analysis
    
    ### {Competitor 1} - {Market Position}
    
    **Company Overview:**
    - **Website**: [{url}]({url})
    - **Founded**: {Year} | **HQ**: {Location}
    - **Size**: {X}+ employees | **Revenue**: ${X}M ({Year})
    - **Funding**: {Details if available}
    
    **Business Model:**
    - {Revenue model description}
    - Target: {Customer segments}
    - Revenue streams: {List streams}
    
    **Key Products/Services:**
    - {Product 1}: {Description}
    - {Product 2}: {Description}
    
    **Market Positioning:**
    - {Positioning statement}
    - {Key differentiators}
    
    **SWOT Analysis:**
    | Strengths | Weaknesses | Opportunities | Threats |
    |-----------|------------|---------------|---------|
    | {Strength 1} | {Weakness 1} | {Opportunity 1} | {Threat 1} |
    | {Strength 2} | {Weakness 2} | {Opportunity 2} | {Threat 2} |
    
    {Repeat for top 3-5 competitors}
    
    ## Comparative Analysis Tables
    
    ### Feature Comparison Matrix
    | Feature Category | {Competitor 1} | {Competitor 2} | {Competitor 3} | {Competitor 4} |
    |------------------|----------------|----------------|----------------|----------------|
    | **Core Features** | | | | |
    | {Feature 1} | ✓ | ✓ | ✗ | ✓ |
    | {Feature 2} | ✓ | Partial | ✓ | ✓ |
    | **Advanced Features** | | | | |
    | {Advanced Feature 1} | ✓ | ✗ | ✓ | Partial |
    
    ### Pricing Comparison
    | Company | Free Tier | Starter | Professional | Enterprise | Custom |
    |---------|-----------|---------|--------------|------------|--------|
    | {Company 1} | {Details} | ${X}/user/mo | ${X}/user/mo | ${X}/user/mo | Contact |
    | {Company 2} | {Details} | ${X}/user/mo | ${X}/user/mo | Contact | Contact |
    
    ### Target Market Segmentation
    | Company | SMB | Mid-Market | Enterprise | Specific Industries | Geographic Focus |
    |---------|-----|------------|------------|-------------------|------------------|
    | {Company 1} | ✓ | ✓ | ✓ | {Industries} | {Regions} |
    | {Company 2} | ✓ | ✓ | Partial | {Industries} | {Regions} |
    
    ## Strategic Insights & Recommendations
    
    ### Market Gaps & Opportunities
    1. **{Opportunity 1}**: {Description and market potential}
    2. **{Opportunity 2}**: {Description and market potential}
    3. **{Opportunity 3}**: {Description and market potential}
    
    ### Strategic Recommendations
    
    #### Immediate Actions (0-3 months)
    1. **{Action 1}**: {Description and expected impact}
    2. **{Action 2}**: {Description and expected impact}
    3. **{Action 3}**: {Description and expected impact}
    
    #### Short-term Strategy (3-12 months)
    1. **{Strategy 1}**: {Description and implementation approach}
    2. **{Strategy 2}**: {Description and implementation approach}
    3. **{Strategy 3}**: {Description and implementation approach}
    
    #### Long-term Vision (12+ months)
    1. **{Vision 1}**: {Description and strategic importance}
    2. **{Vision 2}**: {Description and strategic importance}
    3. **{Vision 3}**: {Description and strategic importance}
    
    ### Risk Assessment
    | Risk Category | Risk Level | Description | Mitigation Strategy |
    |---------------|------------|-------------|-------------------|
    | Competitive | {High/Medium/Low} | {Risk description} | {Mitigation approach} |
    | Market | {High/Medium/Low} | {Risk description} | {Mitigation approach} |
    | Technology | {High/Medium/Low} | {Risk description} | {Mitigation approach} |
    | Regulatory | {High/Medium/Low} | {Risk description} | {Mitigation approach} |
    
    ## Key Resources & Links
    - **Industry Reports**: [{Source 1}]({url}), [{Source 2}]({url})
    - **Company Websites**: [{Company 1}]({url}), [{Company 2}]({url})
    - **News & Updates**: [{Source}]({url}), [{Source}]({url})
    - **Market Research**: [{Source}]({url}), [{Source}]({url})
    
    ## Conclusion
    {Comprehensive summary of competitive landscape, key opportunities, strategic imperatives, and actionable next steps}
    """
    ),
    markdown=True,
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
            result: RunOutput = await asyncio.wait_for(self.agent.arun(message), timeout=300) # 5 minutes timeout
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
