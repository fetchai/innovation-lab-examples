import os
import json
import asyncio
import secrets
import urllib.parse
from typing import Dict, Any, Optional
from contextlib import AsyncExitStack
from cryptography.fernet import Fernet
import time
import mcp
from mcp.client.stdio import stdio_client
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    EndSessionContent,
    StartSessionContent,
)
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic
import httpx

# --- Agent Configuration ---

# Load environment variables from a .env file
load_dotenv()

# Get API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not found in .env file")

AGENT_NAME = "perplexity_agent"
AGENT_PORT = 8006

# User sessions store: session_id -> {authenticated, last_activity}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Session timeout (30 minutes)
SESSION_TIMEOUT = 30 * 60

# --- MCP Client Logic ---

class PerplexityMCPClient:
    def __init__(self, ctx: Context):
        self._ctx = ctx
        self._session: mcp.ClientSession = None
        self._exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.tools = []  # Will be populated after connection

    async def connect(self):
        """Connects to the Perplexity MCP server via Docker with API key."""
        self._ctx.logger.info("Connecting to Perplexity MCP server...")
        try:
            # Perplexity MCP server command with API key
            docker_args = [
                "run", "-i", "--rm",
                "-e", f"PERPLEXITY_API_KEY={PERPLEXITY_API_KEY}",
                "mcp/perplexity-ask"
            ]
            
            params = mcp.StdioServerParameters(command="docker", args=docker_args)
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            self._session = await self._exit_stack.enter_async_context(
                mcp.ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            
            # Get available tools from Perplexity MCP server
            tools_result = await self._session.list_tools()
            self.tools = self._convert_mcp_tools_to_anthropic_format(tools_result.tools)
            
            self._ctx.logger.info(f"Successfully connected to Perplexity MCP. Available tools: {[t.name for t in tools_result.tools]}")
        except Exception as e:
            self._ctx.logger.error(f"Failed to connect to Perplexity MCP server: {e}")
            raise

    def _convert_mcp_tools_to_anthropic_format(self, mcp_tools) -> list:
        """Convert MCP tool definitions to Anthropic tool format."""
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            anthropic_tools.append(anthropic_tool)
        return anthropic_tools

    async def process_query(self, query: str) -> str:
        """Processes a user query using Anthropic for tool selection and then calls the Perplexity tool."""
        self._ctx.logger.info(f"Processing Perplexity query: '{query}'")
        try:
            # Let Claude decide how to use the Perplexity tool
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                messages=[{
                    "role": "user", 
                    "content": f"Please search for information about: {query}. Use the perplexity_ask tool to get real-time web information."
                }],
                tools=self.tools,
            )

            tool_use = next((content for content in response.content if content.type == 'tool_use'), None)

            # If the model wants to use a tool
            if tool_use:
                tool_name = tool_use.name
                tool_input = tool_use.input
                self._ctx.logger.info(f"Claude selected Perplexity tool: {tool_name} with input: {tool_input}")

                # Call the selected tool on the Perplexity MCP server
                mcp_response = await self._session.call_tool(tool_name, tool_input)
                
                # Debug: Log the raw MCP response
                self._ctx.logger.info(f"MCP Response type: {type(mcp_response)}")
                self._ctx.logger.info(f"MCP Response content type: {type(mcp_response.content)}")
                
                # Format the response for the user
                return self._format_response_for_user(tool_name, mcp_response.content)
            
            # If the model just wants to chat
            text_response = next((content for content in response.content if content.type == 'text'), None)
            if text_response:
                return text_response.text

            return "I can help you search the web for real-time information using Perplexity. What would you like to know?"

        except Exception as e:
            self._ctx.logger.error(f"Error processing Perplexity query: {e}")
            return f"Sorry, an error occurred while processing your search request: {e}"

    def _format_response_for_user(self, tool_name: str, content: Any) -> str:
        """Formats the response from Perplexity MCP server for the user."""
        try:
            # Parse the MCP response content
            if isinstance(content, list) and len(content) > 0:
                # Handle text content from MCP response
                if hasattr(content[0], 'text'):
                    response_text = content[0].text
                    # Parse JSON if it's a string
                    if isinstance(response_text, str):
                        try:
                            data = json.loads(response_text)
                            # If it's JSON, format it nicely
                            if isinstance(data, dict):
                                return self._format_perplexity_response(data)
                            else:
                                return response_text
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain text
                            return response_text
                    else:
                        return str(response_text)
            else:
                return str(content)

        except Exception as e:
            self._ctx.logger.error(f"Error formatting Perplexity response: {e}")
            return f"Search completed, but there was an issue formatting the response: {e}"

    def _format_perplexity_response(self, data: Dict) -> str:
        """Format Perplexity API response for better readability."""
        try:
            # Extract key information from Perplexity response
            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    content = choice['message']['content']
                    
                    # Add metadata if available
                    response_parts = [f"🔍 **Search Results:**\n\n{content}"]
                    
                    # Add sources if available
                    if 'citations' in choice:
                        response_parts.append("\n\n📚 **Sources:**")
                        for i, citation in enumerate(choice['citations'][:5], 1):
                            if isinstance(citation, str):
                                response_parts.append(f"{i}. {citation}")
                            elif isinstance(citation, dict) and 'url' in citation:
                                title = citation.get('title', citation['url'])
                                response_parts.append(f"{i}. [{title}]({citation['url']})")
                    
                    return "\n".join(response_parts)
            
            # Fallback formatting
            return f"🔍 **Search Results:**\n\n{json.dumps(data, indent=2)}"
            
        except Exception as e:
            self._ctx.logger.error(f"Error in _format_perplexity_response: {e}")
            return f"Search completed: {str(data)}"

    async def cleanup(self):
        """Cleans up the MCP connection."""
        try:
            await self._exit_stack.aclose()
            self._ctx.logger.info("Perplexity MCP client cleaned up")
        except Exception as e:
            self._ctx.logger.error(f"Error during cleanup: {e}")

# --- uAgent Setup ---

chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name=AGENT_NAME, port=AGENT_PORT, mailbox=True)

# Store MCP clients per session
session_clients: Dict[str, PerplexityMCPClient] = {}

def is_session_valid(session_id: str) -> bool:
    """Check if session is valid and hasn't expired."""
    if session_id not in user_sessions:
        return False
    
    last_activity = user_sessions[session_id].get('last_activity', 0)
    if time.time() - last_activity > SESSION_TIMEOUT:
        # Session expired, clean up
        if session_id in user_sessions:
            del user_sessions[session_id]
        return False
    
    return True

async def get_perplexity_client(ctx: Context, session_id: str) -> Optional[PerplexityMCPClient]:
    """Get or create Perplexity MCP client for session."""
    if session_id not in session_clients:
        try:
            client = PerplexityMCPClient(ctx)
            await client.connect()
            session_clients[session_id] = client
            ctx.logger.info(f"Created new Perplexity MCP client for session {session_id}")
        except Exception as e:
            ctx.logger.error(f"Failed to create Perplexity MCP client: {e}")
            return None
    
    return session_clients[session_id]

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    session_id = str(ctx.session)

    # Send acknowledgment first
    ack_msg = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack_msg)

    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(f"Received message from {sender}: '{item.text}'")
            
            # Update session activity
            if session_id not in user_sessions:
                user_sessions[session_id] = {}
            user_sessions[session_id]['last_activity'] = time.time()
            
            # Check if this is a help request
            if any(keyword in item.text.lower() for keyword in ['help', 'what can you do', 'commands']):
                response_text = """
🔍 **Perplexity Web Search Agent**

I can help you search the web for real-time information using Perplexity's Sonar API!

**What I can do:**
• Search for current news and events
• Find recent information on any topic
• Get real-time data and statistics  
• Research companies, people, and organizations
• Answer questions with up-to-date web sources

**Example queries:**
• "What's the latest news about AI developments?"
• "Find information about Tesla's stock performance this week"
• "What are the current trends in renewable energy?"
• "Research the latest developments in quantum computing"

Just ask me anything and I'll search the web for the most current information!
"""
            else:
                # Process the search query
                client = await get_perplexity_client(ctx, session_id)
                if client:
                    response_text = await client.process_query(item.text)
                else:
                    response_text = "Sorry, I'm having trouble connecting to the search service. Please try again in a moment."
            
            response_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=str(uuid4()),
                content=[TextContent(type="text", text=response_text)]
            )
            await ctx.send(sender, response_msg)
        
        elif isinstance(item, EndSessionContent):
            ctx.logger.info(f"Session ended by {sender}")
            if session_id in session_clients:
                await session_clients[session_id].cleanup()
                del session_clients[session_id]
            if session_id in user_sessions:
                del user_sessions[session_id]
        
        elif isinstance(item, StartSessionContent):
            ctx.logger.info(f"Session started by {sender}")
            # Send welcome message
            welcome_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=str(uuid4()),
                content=[TextContent(
                    type="text", 
                    text="🔍 **Welcome to Perplexity Search Agent!**\n\nI can search the web for real-time information on any topic. What would you like to know?"
                )]
            )
            await ctx.send(sender, welcome_msg)

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    for client in session_clients.values():
        await client.cleanup()

agent.include(chat_proto)

if __name__ == "__main__":
    print(f"Perplexity Agent starting on http://localhost:{AGENT_PORT}")
    print(f"Agent address: {agent.address}")
    print("🔍 Ready to search the web with Perplexity!")
    agent.run()
