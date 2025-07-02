# Perplexity MCP Agent for Agentverse

## Overview

This project makes the official Perplexity MCP server available on Agentverse and discoverable on ASI:One LLM. The implementation creates an MCP client that connects to Perplexity's Docker-based MCP server and wraps it in a uAgent framework.

## Architecture

### Problem

MCP servers typically run locally or in isolated environments. To make Perplexity's MCP server available on Agentverse, we needed to:

1. Run the official Perplexity MCP server in Docker containers
2. Create an MCP client that connects to this Docker-based server
3. Wrap the MCP client in a uAgent framework
4. Make it a mailbox agent for Agentverse registration
5. Add chat protocol for ASI:One discoverability
6. Publish it on Agentverse with proper documentation

### Architecture Flow

```
ASI:One LLM Chat Interface
           ↓
    Chat Protocol Handler
           ↓
    uAgent (Mailbox Agent)
           ↓
    MCP Client
           ↓
    Docker Container (mcp/perplexity-ask)
           ↓
    Perplexity Sonar API
```

## Technical Implementation

### 1. Docker-Based MCP Server Connection

The core component is the `PerplexityMCPClient` class that connects to Perplexity's official MCP server running in Docker:

```python
class PerplexityMCPClient:
    async def connect(self):
        # Connect to official Perplexity MCP server via Docker
        docker_args = [
            "run", "-i", "--rm",
            "-e", f"PERPLEXITY_API_KEY={self._api_key}",
            "mcp/perplexity-ask"  # Official Perplexity MCP Docker image
        ]
        
        # Create stdio connection to Docker container
        params = mcp.StdioServerParameters(command="docker", args=docker_args)
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        
        # Establish MCP session
        self._session = await self._exit_stack.enter_async_context(
            mcp.ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
```

**Technical Details:**
- Uses `mcp/perplexity-ask` Docker image from Perplexity
- Communicates via stdio (stdin/stdout) following MCP protocol
- Passes API keys securely to container via environment variables
- Manages MCP session lifecycle properly

### 2. uAgent Wrapper

The MCP client is wrapped in a uAgent framework to make it compatible with Agentverse:

```python
# Create the uAgent wrapper
agent = Agent(
    name="perplexity_agent",
    port=8006,
    mailbox=True  # Makes it a mailbox agent
)

# Add chat protocol for ASI:One discoverability
from uagents_core.contrib.protocols.chat import chat_protocol_spec
chat_proto = Protocol(spec=chat_protocol_spec)
agent.include(chat_proto)

# Handle incoming chat messages
@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Get MCP client for this session
    client = await get_mcp_client(ctx.session)
    
    # Process query through MCP server
    response = await client.process_query(msg.content[0].text)
    
    # Send formatted response back
    await ctx.send(sender, ChatMessage(...))
```

### 3. Agentverse Registration

The mailbox agent automatically:

1. Registers with Agentverse when started
2. Becomes discoverable on ASI:One LLM
3. Handles chat protocol messages
4. Manages user sessions with proper cleanup

```python
# Automatic Agentverse registration
if __name__ == "__main__":
    agent.run()  # Registers with Agentverse and becomes discoverable
```

## MCP Protocol Integration

### Tool Discovery

The MCP client discovers three official Perplexity tools:

```python
# Discover available tools from MCP server
tools_response = await self._session.list_tools()
self._available_tools = [tool.name for tool in tools_response.tools]

# Available tools from Perplexity MCP server:
# - perplexity_ask: Quick answers
# - perplexity_research: Deep research with citations
# - perplexity_reason: Logical analysis and reasoning
```

### Tool Selection with Claude

Anthropic Claude is used to select which Perplexity tool to use:

```python
# Convert MCP tools to Claude-compatible format
tools = []
for tool in tools_response.tools:
    tools.append({
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema
    })

# Let Claude choose the best tool
response = await self._anthropic_client.messages.create(
    model="claude-3-5-sonnet-20240620",
    tools=tools,
    messages=[{"role": "user", "content": query}],
    tool_choice="auto"
)
```

## What This Achieves

### MCP Server on Agentverse
- Official Perplexity MCP server is now accessible through Agentverse
- Docker integration provides reliable containerized execution
- Full session management and error handling

### ASI:One LLM Integration
- Chat protocol provides standardized interface
- Mailbox agent enables automatic Agentverse registration
- Users can search the web directly from ASI:One chat

### Technical Components
- MCP bridge architecture connects MCP servers to agent networks
- Multi-tool access to all three Perplexity tools (Ask, Research, Reason)
- Claude-powered tool selection for optimal results

## Implementation Stack

### Core Technologies
- **MCP Protocol**: Model Context Protocol for tool integration
- **Docker**: Official `mcp/perplexity-ask` container
- **uAgents Framework**: Agent network and Agentverse integration
- **Anthropic Claude**: Tool selection and query processing
- **Perplexity Sonar API**: Real-time web search capabilities

### System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     ASI:One LLM                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ Chat Protocol
┌─────────────────────▼───────────────────────────────────────┐
│                 uAgent (Mailbox)                            │
├─────────────────────────────────────────────────────────────┤
│  • Agentverse Registration                                  │
│  • Session Management                                       │
│  • Chat Protocol Handler                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Client
┌─────────────────────▼───────────────────────────────────────┐
│               PerplexityMCPClient                           │
├─────────────────────────────────────────────────────────────┤
│  • Docker Connection Management                             │
│  • MCP Session Handling                                     │
│  • Tool Discovery & Execution                               │
│  • Claude Integration                                       │
└─────────────────────┬───────────────────────────────────────┘
                      │ Docker stdio
┌─────────────────────▼───────────────────────────────────────┐
│            Docker: mcp/perplexity-ask                      │
├─────────────────────────────────────────────────────────────┤
│  • Official Perplexity MCP Server                           │
│  • Three Tools: Ask, Research, Reason                       │
│  • Sonar API Integration                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS API
┌─────────────────────▼───────────────────────────────────────┐
│                Perplexity Sonar API                         │
└─────────────────────────────────────────────────────────────┘
```

## Usage Flow

### User Experience on ASI:One LLM

1. User opens ASI:One chat interface
2. Agent is discoverable in agent list
3. User starts conversation: "Find information about Tesla's latest earnings"
4. Agent processes through complete pipeline:
   - Receives message through chat protocol
   - Routes to MCP client
   - Starts Docker container with Perplexity MCP server
   - Uses Claude to select optimal tool (perplexity_ask)
   - Executes search via Sonar API
   - Formats and returns results with citations

### Example Query

**Input**: "What's the latest news about AI developments?"

**Processing**:
1. Chat protocol receives message
2. PerplexityMCPClient spins up Docker container
3. Claude selects `perplexity_research` tool for comprehensive results
4. MCP server queries Sonar API
5. Results formatted and returned

**Output**:
```
🔍 Latest AI Developments

Based on real-time web search:

• OpenAI releases GPT-4 Turbo with improved reasoning
• Google announces Gemini Ultra breakthrough in multimodal AI
• Meta open-sources Llama 2 with commercial license
• Microsoft integrates AI into Office 365 suite

Sources:
1. TechCrunch - "OpenAI's GPT-4 Turbo..."
2. The Verge - "Google's Gemini Ultra..."
3. Reuters - "Meta releases Llama 2..."
```

## Setup & Deployment

### Prerequisites
- Python 3.12+
- Docker Desktop
- Perplexity API key
- Anthropic API key

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add ANTHROPIC_API_KEY and PERPLEXITY_API_KEY

# 3. Setup Docker
python docker_setup.py setup

# 4. Run diagnostics
python debug_env.py

# 5. Deploy agent
python agent.py
```

### Deployment Process

When you run `python agent.py`:

1. Environment validation (checks API keys and Docker)
2. Agentverse registration (agent registers automatically)
3. ASI:One discovery (becomes available in chat interface)
4. Ready for users (accepts real-time web search queries)

## Key Technical Components

### MCP Bridge Pattern
- **Problem**: MCP servers typically run in isolation
- **Solution**: Bridge architecture connecting MCP to agent networks
- **Result**: Opens MCP ecosystem to Agentverse/ASI:One users

### Docker-First MCP Client
- **Problem**: Complex MCP server deployment and management
- **Solution**: Leverage official Docker images with stdio communication
- **Result**: Reliable, reproducible, and maintainable deployments

### Tool Routing
- **Problem**: Users don't know which search tool to use
- **Solution**: Claude automatically selects optimal tool based on query
- **Result**: Better user experience with optimal results

### Session Management
- **Problem**: Multiple users sharing single MCP connection
- **Solution**: Per-session MCP client instances with proper cleanup
- **Result**: Secure, scalable multi-user support

## Project Structure

```
perplexity-mcp-agent/
├── agent.py              # Main uAgent implementation
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
├── README.md            # Documentation
├── debug_env.py         # Environment diagnostics
├── test_agent.py        # Testing utilities
└── docker_setup.py      # Docker management
```

## Conclusion

This project makes the official Perplexity MCP server available on Agentverse by creating a bridge architecture. ASI:One LLM users can now access real-time web search through a simple chat interface.

The implementation demonstrates how to combine MCP protocol, Docker containers, uAgent networks, and AI APIs to create accessible AI tools for real-world users.

---

*Find the Perplexity Agent on ASI:One LLM for real-time web search capabilities.*
