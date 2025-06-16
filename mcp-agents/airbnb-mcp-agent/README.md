# Airbnb MCP Agent Implementation

A complete implementation of an intelligent agent that connects to the Airbnb MCP server and makes it accessible through natural language chat interfaces.

## 🏗️ Architecture

```
User Chat ──► Chat Protocol ──► MCP Client ──► Airbnb MCP Server
    ▲              │                               
    │              ▼                               
    └────── AI Agent (Structured Output)          
```

**Flow**: User sends natural language → Chat protocol processes → AI converts to structured request → MCP client calls Airbnb server → Results formatted back to user

## 📁 Three Core Files

### 1. `mcp_client.py` - MCP Server Interface

**Purpose**: Direct communication with Airbnb MCP server

**Key Structure**:
```python
# Global session management
mcp_session = None
mcp_exit_stack = None

# Connection to NPX-based Airbnb server
async def connect_to_airbnb_mcp():
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
        env={}
    )

# Two main functions
async def search_airbnb_listings(location: str, limit: int = 4, **kwargs)
async def get_airbnb_listing_details(listing_id: str, **kwargs)
```

**Response Processing Pattern**:
```python
# Standard MCP response handling
for item in result.content:
    if hasattr(item, 'text'):
        parsed_content = json.loads(item.text)  # Airbnb returns JSON
        # Format for user display
```

**Why Global Variables**: MCP connections are expensive to create, so we maintain one persistent connection across all requests.

### 2. `chat_proto.py` - Natural Language Processing

**Purpose**: Converts user chat into structured MCP requests via AI

**Key Models**:
```python
class AirbnbRequest(Model):
    request_type: str  # "search" or "details"
    parameters: Dict[str, Any]

class AirbnbResponse(Model):
    results: str
```

**AI Integration Pattern**:
```python
# Send user message to AI for structured conversion
await ctx.send(
    AI_AGENT_ADDRESS,  # Specific AI agent for structured output
    StructuredOutputPrompt(
        prompt=prompt_text,
        output_schema=AirbnbRequest.schema()
    )
)

# AI returns structured JSON matching our schema
@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_ai_response(ctx: Context, sender: str, msg: StructuredOutputResponse):
    request = AirbnbRequest.parse_obj(msg.output)
    
    # Route based on request_type
    if request.request_type == "search":
        result = await search_airbnb_listings(...)
    elif request.request_type == "details":
        result = await get_airbnb_listing_details(...)
```

**Session Management**: Uses `ctx.storage` to track conversation context between AI processing and user responses.

### 3. `agent.py` - Main Orchestrator

**Purpose**: Makes the agent discoverable and manages system lifecycle

**Agent Setup**:
```python
agent = Agent(
    name="airbnb_assistant",
    port=8004,
    mailbox=True
)

# Include all protocols for different capabilities
agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)
agent.include(proto, publish_manifest=True)  # Rate limiting
```

**Health Monitoring**:
```python
def agent_is_healthy() -> bool:
    return mcp_session is not None  # Healthy if MCP connected

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
```

**Lifecycle Management**:
```python
@agent.on_event("startup")
async def on_startup(ctx: Context):
    success = await connect_to_airbnb_mcp()  # Connect on startup

# Cleanup on shutdown
if __name__ == "__main__":
    try:
        agent.run()
    except KeyboardInterrupt:
        asyncio.run(cleanup_mcp_connection())
```

## 🔄 Request Flow Example

1. **User**: "Find Airbnb in Paris"
2. **Chat Protocol**: Sends to AI agent with structured output prompt
3. **AI Agent**: Returns `{"request_type": "search", "parameters": {"location": "Paris"}}`
4. **Chat Protocol**: Calls `search_airbnb_listings("Paris")`
5. **MCP Client**: Calls Airbnb MCP server tool `"airbnb_search"`
6. **Response**: Formatted listings sent back to user

## 🚀 Running the System

```bash
# Install dependencies
pip install uagents mcp

# Run the agent
python agent.py
```

**Output**:
```
Your agent's address is: [agent_address]
Successfully connected to Airbnb MCP server
```

## 🔧 Key Configuration

**AI Agent Address**: `agent1qtlpfshtlcxekgrfcpmv7m9zpajuwu7d5jfyachvpa4u3dkt6k0uwwp2lct`
**Rate Limiting**: 30 requests per 60 minutes
**Default Results**: 4 listings per search
**Supported Parameters**: location, checkin, checkout, adults, children, infants, pets, minPrice, maxPrice

## 🎯 Adapting for Other MCP Servers

To use this pattern with different MCP servers:

1. **Update MCP Client** (`mcp_client.py`):
   - Change `StdioServerParameters` command/args for your server
   - Replace function names and tool calls
   - Adapt response parsing for your server's format

2. **Update Chat Protocol** (`chat_proto.py`):
   - Modify request/response models for your domain
   - Update AI prompts for your use case
   - Change function routing logic

3. **Update Agent** (`agent.py`):
   - Change agent name and port
   - Adjust health check logic for your dependencies

**Core Pattern**: The stdio communication, async session management, and AI integration patterns remain the same across all MCP servers.