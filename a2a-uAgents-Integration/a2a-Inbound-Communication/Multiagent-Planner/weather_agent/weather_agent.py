import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)


def create_weather_agent() -> LlmAgent:
    """Constructs the ADK agent."""
    # Get the directory of this file to construct absolute path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    weather_mcp_path = os.path.join(current_dir, 'weather_mcp.py')
    
    return LlmAgent(
        model='gemini-2.5-flash-preview-04-17',
        name='weather_agent',
        description='An agent that can help questions about weather',
        instruction="""You are a specialized weather forecast assistant. Your primary function is to utilize the provided tools to retrieve and relay weather information in response to user queries. You must rely exclusively on these tools for data and refrain from inventing information. Ensure that all responses include the detailed output from the tools used and are formatted in Markdown""",
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=[weather_mcp_path],
                ),
            )
        ],
    )