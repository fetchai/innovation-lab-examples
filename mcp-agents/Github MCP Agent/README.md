# GitHub MCP Agent on Agentverse

## 🎯 Overview

This guide explains how to build **uAgents that integrate MCP clients** for deployment on **Agentverse**.
Through this we are bringing MCP clients into Agentverse and making them discoverable on ASI:One LLM. We took an official Github MCP server, built an MCP client, attached chat protocol to it and wrapped it in a uAgent, with a mailbox and registered the agent on Agentverse, with a clear Agent README.  

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [MCP Integration Pattern](#mcp-integration-pattern)
4. [Authentication & Security](#authentication--security)
5. [Session Management](#session-management)
6. [uAgent Integration](#uagent-integration)
7. [Deployment Guide](#deployment-guide)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Adapting to Other MCP Servers](#adapting-to-other-mcp-servers)

## 🏗️ Architecture Overview

### High-Level Flow
```
User → ASI:One → Agentverse → uAgent → Anthropic Claude → MCP Server → External API
```

### Component Interaction
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │ ──→│ Agentverse  │ ──→│ MCP Client  │ ──→│ MCP Server  │
│   (Chat)    │    │  (Chat UI)  │    │ (uAgent)    │    │  (Docker)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                             │                    │
                                             ▼                    ▼
                                      ┌─────────────┐    ┌─────────────┐
                                      │  Anthropic  │    │ External    │
                                      │   Claude    │    │    API      │
                                      └─────────────┘    └─────────────┘
```

## 🔧 Core Components

### 1. Project Structure
```
github-mcp-agent/
├── agent.py               # Main uAgent with MCP integration
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── private_keys.json     # uAgent keys (generated)
└── README.md            # Documentation
```

### 2. Essential Dependencies
```txt
# Core uAgent dependencies
uagents                   # Agentverse framework
anthropic                 # LLM for tool selection

# MCP client for server communication  
mcp                       # Model Context Protocol client

# Utilities
python-dotenv            # Environment management
httpx                    # HTTP client for API calls
cryptography             # Token encryption
```

## 🔌 MCP Integration Pattern

### **Key Architectural Insight**

**We built a uAgent that CONTAINS an MCP client, not converts one:**

```
┌─────────────────────────────────────────────────────────────┐
│                        uAgent                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  Chat Protocol  │  │ Session Manager │  │ Auth Handler│  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
│                            │                                │
│                            ▼                                │
│                  ┌─────────────────┐                        │
│                  │   MCP Client    │ ◄─── This is INSIDE    │
│                  │   (Component)   │      the uAgent        │
│                  └─────────────────┘                        │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │   MCP Server    │ ◄─── External process
                │   (Docker)      │      (GitHub's server)
                └─────────────────┘
```

### **Responsibilities:**

**uAgent Layer:**
- 🗣️ **Chat interface** with users via Agentverse
- 👥 **Session management** (per-user isolation)
- 🔐 **Authentication** (OAuth + manual tokens)
- 🧠 **Natural language processing** (Claude integration)
- 📋 **Message routing** and response formatting

**MCP Client Layer (Component inside uAgent):**
- 🔌 **Connection** to external MCP server
- 🛠️ **Tool discovery** and execution
- 📡 **Protocol handling** (JSON-RPC over stdio)
- 🐳 **Docker management** for MCP server isolation

### 1. MCP Client Setup

The core pattern for integrating any MCP server:

```python
import mcp
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

class MCPClient:
    def __init__(self, ctx: Context, access_token: str):
        self._ctx = ctx
        self._access_token = access_token
        self._session: mcp.ClientSession = None
        self._exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.tools = []
    
    async def connect(self):
        """Connect to MCP server via Docker or direct process"""
        # Docker approach (recommended for isolation)
        docker_args = [
            "run", "-i", "--rm",
            "-e", f"ACCESS_TOKEN={self._access_token}",
            "your-mcp-server-image"
        ]
        
        params = mcp.StdioServerParameters(command="docker", args=docker_args)
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        
        self._session = await self._exit_stack.enter_async_context(
            mcp.ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        
        # Discover available tools
        tools_result = await self._session.list_tools()
        self.tools = self._convert_mcp_tools_to_anthropic_format(tools_result.tools)
```

### 2. Tool Discovery and Conversion

Convert MCP tool definitions to Anthropic's format:

```python
def _convert_mcp_tools_to_anthropic_format(self, mcp_tools):
    """Convert MCP tool definitions to Anthropic tool format"""
    anthropic_tools = []
    for tool in mcp_tools:
        anthropic_tool = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        }
        anthropic_tools.append(anthropic_tool)
    return anthropic_tools
```

### 3. Natural Language Processing

Use Claude to select and execute tools:

```python
async def process_query(self, query: str) -> str:
    """Process user query using Anthropic for tool selection"""
    try:
        response = self.anthropic.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            messages=[{
                "role": "user", 
                "content": f"Help me with this GitHub request: {query}"
            }],
            tools=self.tools,
            tool_choice={"type": "auto"}
        )
        
        # Handle tool use
        if response.content[0].type == "tool_use":
            tool_name = response.content[0].name
            tool_input = response.content[0].input
            
            # Execute via MCP
            mcp_response = await self._session.call_tool(tool_name, tool_input)
            return self._format_response_for_user(tool_name, mcp_response.content)
        
    except Exception as e:
        return f"Error processing request: {e}"
```

## 🔐 Authentication & Security

### 1. Multi-Method Authentication

Support both OAuth and manual token input:

```python
class AuthHandler:
    def __init__(self):
        self.client_id = "your-oauth-client-id"
        self.device_url = "https://api.provider.com/oauth/device"
        self.token_url = "https://api.provider.com/oauth/token"
    
    async def start_device_flow(self, session_id: str):
        """Start OAuth device flow"""
        # Implementation here...
    
    async def validate_manual_token(self, token: str):
        """Validate manually provided token"""
        # Implementation here...
```

### 2. Token Security

Implement proper token encryption and session management:

```python
from cryptography.fernet import Fernet

# Initialize encryption
fernet_key = Fernet.generate_key()
cipher_suite = Fernet(fernet_key)

# Session management with timeout
SESSION_TIMEOUT = 30 * 60  # 30 minutes
user_sessions: Dict[str, Dict[str, Any]] = {}

def store_encrypted_token(session_id: str, token: str):
    """Store token with encryption and timestamp"""
    encrypted_token = cipher_suite.encrypt(token.encode()).decode()
    user_sessions[session_id] = {
        'access_token': encrypted_token,
        'last_activity': time.time()
    }

def get_decrypted_token(session_id: str) -> Optional[str]:
    """Retrieve and decrypt token"""
    if is_session_valid(session_id):
        encrypted_token = user_sessions[session_id]['access_token']
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    return None
```

## 📡 Session Management

### 1. Per-User Isolation

Each user gets their own MCP client instance:

```python
# Global session storage
session_clients: Dict[str, MCPClient] = {}

async def get_authenticated_client(ctx: Context, session_id: str) -> Optional[MCPClient]:
    """Get or create authenticated MCP client for user session"""
    if session_id in session_clients:
        return session_clients[session_id]
    
    if not is_user_authenticated(session_id):
        return None
    
    # Create new MCP client with user's token
    access_token = get_decrypted_token(session_id)
    client = MCPClient(ctx, access_token)
    await client.connect()
    session_clients[session_id] = client
    return client
```

### 2. Session Lifecycle

Implement proper session cleanup:

```python
def is_session_valid(session_id: str) -> bool:
    """Check if session exists and hasn't expired"""
    if session_id not in user_sessions:
        return False
    
    session = user_sessions[session_id]
    last_activity = session.get('last_activity', 0)
    
    if time.time() - last_activity > SESSION_TIMEOUT:
        # Clean up expired session
        cleanup_session(session_id)
        return False
    
    # Update activity timestamp
    session['last_activity'] = time.time()
    return True

async def cleanup_session(session_id: str):
    """Clean up session resources"""
    if session_id in session_clients:
        await session_clients[session_id].cleanup()
        del session_clients[session_id]
    
    if session_id in user_sessions:
        del user_sessions[session_id]
```

## 🤖 uAgent Integration

### 1. Chat Protocol Setup

Use uAgents' chat protocol for user interaction:

```python
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent
)

# Setup
chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name="your_agent", port=8000, mailbox=True)

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Extract session ID from sender
    session_id = sender
    
    # Send acknowledgment
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)
    
    # Process message content
    for item in msg.content:
        if isinstance(item, TextContent):
            response_text = await process_user_input(ctx, session_id, item.text)
            
            response_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=str(uuid4()),
                content=[TextContent(type="text", text=response_text)]
            )
            await ctx.send(sender, response_msg)
```

### 2. Message Processing

Handle different types of user input:

```python
async def process_user_input(ctx: Context, session_id: str, text: str) -> str:
    """Process user input and route appropriately"""
    
    # Check for manual token input (provider-specific format)
    if text.startswith('ghp_') and len(text) > 20:  # GitHub token format
        return await handle_manual_token(ctx, session_id, text)
    
    # Check if user is authenticated
    if not is_user_authenticated(session_id):
        return await start_authentication_flow(ctx, session_id)
    
    # Process authenticated request
    client = await get_authenticated_client(ctx, session_id)
    if client:
        return await client.process_query(text)
    else:
        return "Error: Unable to connect to service. Please try authenticating again."
```

## 🚀 Deployment Guide

### 1. Environment Setup

Create `.env` file with required variables:

```env
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional (for OAuth)
OAUTH_CLIENT_ID=your_oauth_client_id

# Agent Configuration
AGENT_NAME=your_agent_name
AGENT_PORT=8000
```

### 2. Docker Requirements

Ensure Docker is available for MCP server isolation:

```python
# Check Docker availability on startup
import subprocess

def check_docker():
    try:
        subprocess.run(["docker", "--version"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

if not check_docker():
    raise RuntimeError("Docker is required but not available")
```

### 3. Agent Registration

Register with Agentverse for mailbox functionality:

```python
agent = Agent(
    name="your_agent_name",
    port=8000,
    mailbox=True,  # Enable Agentverse integration
    seed="your_agent_seed"  # For consistent identity
)
```

## 📋 Best Practices

### 1. Error Handling

Implement comprehensive error handling:

```python
async def safe_mcp_call(self, tool_name: str, tool_input: dict) -> str:
    """Safely call MCP tool with error handling"""
    try:
        response = await self._session.call_tool(tool_name, tool_input)
        return self._format_response(response)
    except Exception as e:
        self._ctx.logger.error(f"MCP call failed: {e}")
        return f"Sorry, I encountered an error: {str(e)}"
```

### 2. Response Formatting

Format responses for optimal user experience:

```python
def _format_response_for_user(self, tool_name: str, content: Any) -> str:
    """Format MCP response for user consumption"""
    try:
        if isinstance(content, list) and content:
            data = json.loads(content[0].text) if hasattr(content[0], 'text') else content[0]
        else:
            data = content
        
        # Tool-specific formatting
        if tool_name == "search_repositories":
            return self._format_repositories(data)
        elif tool_name == "list_issues":
            return self._format_issues(data)
        # Add more formatters as needed
        
        return str(data)
    except Exception as e:
        return f"Response formatting error: {e}"
```

### 3. Logging and Monitoring

Implement proper logging:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In your methods
self._ctx.logger.info(f"User {user_id} authenticated successfully")
self._ctx.logger.error(f"MCP connection failed: {error}")
```

## 🔧 Adapting to Other MCP Servers

### 1. Server-Specific Configuration

Each MCP server has different requirements:

```python
# GitHub MCP Server
github_docker_args = [
    "run", "-i", "--rm",
    "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={token}",
    "ghcr.io/github/github-mcp-server"
]

# Filesystem MCP Server  
filesystem_docker_args = [
    "run", "-i", "--rm",
    "-v", f"{local_path}:/data",
    "filesystem-mcp-server"
]

# Database MCP Server
database_docker_args = [
    "run", "-i", "--rm", 
    "-e", f"DATABASE_URL={db_url}",
    "database-mcp-server"
]
```

### 2. Authentication Patterns

Different services use different auth methods:

```python
class UniversalAuthHandler:
    def __init__(self, service_type: str):
        self.service_type = service_type
        self.config = self._load_service_config(service_type)
    
    def _load_service_config(self, service_type: str):
        configs = {
            "github": {
                "oauth_url": "https://github.com/login/oauth",
                "api_url": "https://api.github.com",
                "token_prefix": "ghp_"
            },
            "gitlab": {
                "oauth_url": "https://gitlab.com/oauth", 
                "api_url": "https://gitlab.com/api/v4",
                "token_prefix": "glpat-"
            }
            # Add more services...
        }
        return configs.get(service_type, {})
```

## 🐛 Troubleshooting

### Common Issues and Solutions

1. **MCP Connection Failures**
   ```python
   # Add connection retry logic
   async def connect_with_retry(self, max_retries=3):
       for attempt in range(max_retries):
           try:
               await self.connect()
               return
           except Exception as e:
               if attempt == max_retries - 1:
                   raise
               await asyncio.sleep(2 ** attempt)
   ```

2. **Token Validation Errors**
   ```python
   # Validate token before storing
   async def validate_token(self, token: str) -> bool:
       try:
           async with httpx.AsyncClient() as client:
               response = await client.get(
                   f"{self.api_url}/user",
                   headers={'Authorization': f'Bearer {token}'}
               )
               return response.status_code == 200
       except:
           return False
   ```

3. **Session Cleanup Issues**
   ```python
   # Ensure proper cleanup on agent shutdown
   @agent.on_event("shutdown")
   async def on_shutdown(ctx: Context):
       for client in session_clients.values():
           try:
               await client.cleanup()
           except Exception as e:
               ctx.logger.error(f"Cleanup error: {e}")
   ```

## 🎯 Conclusion

This pattern can be adapted for any MCP server by:

1. **Changing the Docker image** and environment variables
2. **Adapting the authentication flow** for your service
3. **Customizing response formatting** for your data types
4. **Implementing service-specific validation** and error handling

The core uAgent → MCP → External API pattern remains the same, making it easy to create new agents for different services.

The key insight is that we're not converting MCP clients into uAgents, but rather **wrapping MCP clients inside uAgents** to provide additional functionality. This approach allows for a flexible and modular architecture that can be easily extended to support various MCP servers and services.

## 📚 Additional Resources

- [uAgents Documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Docker Documentation](https://docs.docker.com/)


