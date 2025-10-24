"""
Claude MCP Agent for Fetch.ai Agentverse
An AI agent that connects to MCP (Model Context Protocol) servers to access external tools and resources

This agent:
- Connects to multiple MCP servers (GitHub, filesystem, databases, etc.)
- Discovers available tools from MCP servers automatically
- Uses Claude to intelligently choose and execute MCP tools
- Returns results via Fetch.ai protocol
- Easy to extend with new MCP servers

Architecture:
    User (ASI One) 
        → Fetch.ai Agent (this code)
            → Claude (decides which tools to use)
                → MCP Servers (GitHub, filesystem, etc.)
                    → External Resources (repos, files, DBs)
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from anthropic import Anthropic

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec
)

# MCP SDK imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  MCP SDK not installed. Install with: pip install mcp")

# Load environment variables
load_dotenv()

# Configure Anthropic Claude
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

# Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

# Model configuration
MODEL_NAME = 'claude-3-5-sonnet-20241022'
MAX_TOKENS = 4096
TEMPERATURE = 0.7

# Create agent
agent = Agent(
    name="claude_mcp",
    seed="claude-mcp-seed-phrase-12345",  # Change this for your agent
    port=8004,
    mailbox=True
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are an AI assistant with access to external tools and resources via MCP (Model Context Protocol).

You can:
- Search and access GitHub repositories
- Read and analyze files
- Query databases
- Search web services
- And more depending on connected MCP servers

When using tools:
- Choose the most appropriate tool for the task
- Extract necessary parameters from user requests
- Explain what you're doing
- Present results clearly and helpfully

Always be helpful, accurate, and efficient."""


# ========== MCP SERVER MANAGEMENT ==========

class MCPServerManager:
    """Manages connections to multiple MCP servers"""
    
    def __init__(self, config_path: str = "mcp_servers.json"):
        self.config_path = config_path
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()  # Proper async context management
        self.tools_cache: Dict[str, List[Dict]] = {}
        
    def load_config(self) -> Dict:
        """Load MCP server configuration from JSON file"""
        config_file = Path(__file__).parent / self.config_path
        
        if not config_file.exists():
            print(f"⚠️  Config file not found: {config_file}")
            return {"servers": {}}
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Substitute environment variables
        config = self._substitute_env_vars(config)
        return config
    
    def _substitute_env_vars(self, config: Dict) -> Dict:
        """Replace ${VAR_NAME} with environment variable values"""
        config_str = json.dumps(config)
        
        # Find all ${VAR_NAME} patterns
        import re
        for match in re.finditer(r'\$\{(\w+)\}', config_str):
            var_name = match.group(1)
            var_value = os.getenv(var_name, '')
            config_str = config_str.replace(match.group(0), var_value)
        
        return json.loads(config_str)
    
    async def connect_server(self, name: str, server_config: Dict) -> bool:
        """Connect to a single MCP server"""
        try:
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", {})
            
            # Prepare server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env if env else None
            )
            
            # Use AsyncExitStack to manage the async context (official MCP pattern)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            
            # Create and enter session context
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            # Initialize the session
            await session.initialize()
            
            # Store session
            self.sessions[name] = session
            
            print(f"✅ Connected to MCP server: {name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to {name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def connect_all_servers(self):
        """Connect to all enabled MCP servers from config"""
        config = self.load_config()
        servers = config.get("servers", {})
        
        connection_tasks = []
        for name, server_config in servers.items():
            if server_config.get("enabled", False):
                print(f"🔌 Connecting to {name}...")
                task = self.connect_server(name, server_config)
                connection_tasks.append((name, task))
        
        # Connect to all servers concurrently
        for name, task in connection_tasks:
            await task
    
    async def get_all_tools(self) -> List[Dict]:
        """Get all available tools from all connected MCP servers"""
        all_tools = []
        
        for server_name, session in self.sessions.items():
            try:
                # List tools from this server
                result = await session.list_tools()
                tools = result.tools if hasattr(result, 'tools') else []
                
                # Add server name to each tool for tracking
                for tool in tools:
                    tool_dict = {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema,
                        "_mcp_server": server_name  # Track which server provides this
                    }
                    all_tools.append(tool_dict)
                
                self.tools_cache[server_name] = tools
                print(f"📋 Loaded {len(tools)} tools from {server_name}")
                
            except Exception as e:
                print(f"⚠️  Error getting tools from {server_name}: {e}")
        
        return all_tools
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Execute a tool call on the appropriate MCP server"""
        # Find which server has this tool
        for server_name, session in self.sessions.items():
            tools = self.tools_cache.get(server_name, [])
            
            if any(t.name == tool_name for t in tools):
                try:
                    result = await session.call_tool(tool_name, arguments)
                    return result
                except Exception as e:
                    return {
                        "error": str(e),
                        "tool": tool_name,
                        "server": server_name
                    }
        
        return {
            "error": f"Tool '{tool_name}' not found in any connected server"
        }
    
    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        try:
            print("🔌 Disconnecting from all MCP servers...")
            # AsyncExitStack will handle closing all contexts properly
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"⚠️  Error disconnecting from servers: {e}")
        
        self.sessions.clear()
        self.tools_cache.clear()


# Global MCP manager instance
mcp_manager = MCPServerManager()


# ========== HELPER FUNCTIONS ==========

def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )


def mcp_tools_to_claude_format(mcp_tools: List[Dict]) -> List[Dict]:
    """Convert MCP tool format to Claude's expected format"""
    claude_tools = []
    
    for tool in mcp_tools:
        claude_tool = {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"]
        }
        claude_tools.append(claude_tool)
    
    return claude_tools


def format_tool_result(result: Any) -> str:
    """Format MCP tool result for Claude"""
    if isinstance(result, dict):
        # Pretty print JSON
        return json.dumps(result, indent=2)
    elif isinstance(result, str):
        return result
    else:
        return str(result)


# ========== AGENT HANDLERS ==========

@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent and connect to MCP servers"""
    ctx.logger.info("🔌 Starting Claude MCP Agent...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if not MCP_AVAILABLE:
        ctx.logger.error("❌ MCP SDK not installed. Run: pip install mcp")
        return
    
    if anthropic_api_key:
        ctx.logger.info("✅ Claude API configured")
    else:
        ctx.logger.error("❌ Anthropic API key not set")
        return
    
    # Connect to MCP servers
    ctx.logger.info("🔌 Connecting to MCP servers...")
    try:
        await mcp_manager.connect_all_servers()
        
        # Get available tools
        mcp_tools = await mcp_manager.get_all_tools()
        
        if mcp_tools:
            ctx.logger.info(f"✅ Loaded {len(mcp_tools)} MCP tools")
            
            # Store tools in context for later use
            ctx.storage.set("mcp_tools", mcp_tools)
            
            # Show tool summary
            for tool in mcp_tools:
                server = tool.get("_mcp_server", "unknown")
                ctx.logger.info(f"   🔧 {tool['name']} ({server})")
        else:
            ctx.logger.warning("⚠️  No MCP tools available. Check server configuration.")
    
    except Exception as e:
        ctx.logger.error(f"❌ Error connecting to MCP servers: {e}")
    
    # Initialize stats
    ctx.storage.set("total_messages", 0)
    ctx.storage.set("total_tool_calls", 0)


@agent.on_event("shutdown")
async def shutdown(ctx: Context):
    """Cleanup MCP connections on shutdown"""
    ctx.logger.info("🔌 Disconnecting from MCP servers...")
    await mcp_manager.disconnect_all()


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with MCP tool support"""
    
    try:
        # Extract text from message
        user_text = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break
        
        if not user_text:
            ctx.logger.warning("No text content in message")
            return
        
        # Log incoming message
        ctx.logger.info(f"📨 Message from {sender}: {user_text[:50]}...")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Get MCP tools
        mcp_tools = ctx.storage.get("mcp_tools") or []
        
        if not mcp_tools:
            await ctx.send(sender, create_text_chat(
                "⚠️ No MCP servers connected. Please check the configuration and restart the agent."
            ))
            return
        
        # Convert to Claude format
        claude_tools = mcp_tools_to_claude_format(mcp_tools)
        
        # Build messages for Claude
        messages = [{
            "role": "user",
            "content": user_text
        }]
        
        # Loop to handle multiple tool calls
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call Claude with MCP tools
            ctx.logger.info(f"🤔 Calling Claude with {len(claude_tools)} MCP tools (iteration {iteration})...")
            
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                tools=claude_tools,
                messages=messages
            )
            
            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Extract tool uses
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                
                ctx.logger.info(f"🔧 Claude wants to use {len(tool_uses)} MCP tool(s)")
                
                # Add assistant's response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Execute each tool via MCP
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.name
                    tool_input = tool_use.input
                    
                    ctx.logger.info(f"⚙️  Executing MCP tool: {tool_name}")
                    ctx.logger.info(f"   Input: {json.dumps(tool_input, indent=2)[:100]}...")
                    
                    # Call the MCP tool
                    result = await mcp_manager.call_tool(tool_name, tool_input)
                    
                    # Format result
                    result_str = format_tool_result(result)
                    ctx.logger.info(f"✅ Tool result: {result_str[:100]}...")
                    
                    # Track stats
                    total_calls = ctx.storage.get("total_tool_calls") or 0
                    ctx.storage.set("total_tool_calls", total_calls + 1)
                    
                    # Add tool result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_str
                    })
                
                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue loop for Claude's final response
                continue
                
            else:
                # Claude provided final answer
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text
                
                ctx.logger.info(f"✅ Final response: {response_text[:50]}...")
                
                # Track stats
                total = ctx.storage.get("total_messages") or 0
                ctx.storage.set("total_messages", total + 1)
                
                # Send response
                await ctx.send(sender, create_text_chat(response_text))
                ctx.logger.info(f"💬 Response sent to {sender}")
                
                break
        
        if iteration >= max_iterations:
            ctx.logger.warning("⚠️  Max iterations reached")
            await ctx.send(sender, create_text_chat(
                "I've reached the maximum number of tool calls. Please try a simpler request."
            ))
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        error_msg = f"""❌ **Error Processing Request**

{str(e)[:200]}

This might be due to:
- MCP server connection issues
- Tool execution failures
- API rate limits

Please try again or check the logs."""
        
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message {msg.acknowledged_msg_id} acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🔌 Starting Claude MCP Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if not MCP_AVAILABLE:
        print("\n❌ ERROR: MCP SDK not installed")
        print("   Install with: pip install mcp")
        exit(1)
    
    if not anthropic_api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY not set")
        print("   Please add it to your .env file")
        exit(1)
    
    print("\n🎯 This agent connects to MCP servers and uses their tools")
    print("   Configure servers in: mcp_servers.json")
    print("   Enable/disable servers by setting 'enabled: true/false'")
    
    print("\n✅ Agent starting...")
    print("   MCP servers will be connected on startup")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
