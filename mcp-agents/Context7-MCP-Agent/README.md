# 📚 Context7 MCP Agent for Agentverse

**A sophisticated uAgent that wraps a custom MCP client to integrate with the remote Context7 MCP server, providing intelligent documentation retrieval with multi-tool evaluation and result enhancement, discoverable on ASI:One through the chat protocol.**

![Architecture](https://img.shields.io/badge/Architecture-MCP%20Client%20in%20uAgent-blue)
![Protocol](https://img.shields.io/badge/Protocol-Chat%20Protocol-green)
![MCP](https://img.shields.io/badge/MCP-Remote%20Context7-orange)
![AI](https://img.shields.io/badge/AI-Claude%203.5%20Sonnet-purple)

## 🏗️ Detailed Architecture

```
┌─────────────────────┐
│    ASI:One LLM      │
│   (Chat Interface)  │
└─────────┬───────────┘
          │ Chat Protocol
          ▼
┌─────────────────────┐
│      uAgent         │
│  ┌───────────────┐  │
│  │ Chat Protocol │  │  ◄─── Handles ASI:One communication
│  │   Handler     │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │   Custom MCP  │  │  ◄─── Our core innovation
│  │    Client     │  │
│  │ ┌───────────┐ │  │
│  │ │Search     │ │  │  ◄─── 5 intelligent strategies
│  │ │Strategies │ │  │
│  │ └───────────┘ │  │
│  │ ┌───────────┐ │  │
│  │ │Tool Chain │ │  │  ◄─── Multi-tool evaluation
│  │ │Evaluation │ │  │
│  │ └───────────┘ │  │
│  │ ┌───────────┐ │  │
│  │ │Result     │ │  │  ◄─── Claude-powered enhancement
│  │ │Enhancement│ │  │
│  │ └───────────┘ │  │
│  └───────┬───────┘  │
└──────────┬──────────┘
           │ stdio communication
           ▼
┌─────────────────────┐
│   Remote Context7   │
│    MCP Server      │  ◄─── via npx @upstash/context7-mcp
│ ┌─────────────────┐ │
│ │resolve-library- │ │  ◄─── Tool 1: Find libraries
│ │      id         │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │get-library-docs │ │  ◄─── Tool 2: Get documentation
│ └─────────────────┘ │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Documentation      │
│    Database         │  ◄─── Context7's curated docs
└─────────────────────┘
```

## 🎯 What We Built: MCP Client → uAgent Wrapper

### The Innovation: Custom MCP Client Inside uAgent

We created a **custom MCP client** (`Context7MCPClient`) that:
1. **Connects to remote MCP server** via stdio 
2. **Implements intelligent search strategies**
3. **Evaluates and chains tool calls**
4. **Enhances results with AI**

Then we **wrapped this MCP client inside a uAgent** to:
1. **Make it discoverable on ASI:One**
2. **Handle chat protocol communication**
3. **Manage user sessions**
4. **Deploy on Agentverse**

```python
class Context7MCPClient:           # ← Our custom MCP client
    """The brain of our system"""
    
    def __init__(self, ctx: Context):
        self._session: mcp.ClientSession = None  # MCP connection
        self.search_strategies = [...]           # 5 search strategies
        self.anthropic = Anthropic(...)         # Claude for enhancement
    
    async def connect(self):
        """Connect to REMOTE Context7 MCP server"""
        params = mcp.StdioServerParameters(
            command="npx",
            args=["-y", "@upstash/context7-mcp"]  # Remote server!
        )
        # ... stdio connection setup

# Then we wrap it in a uAgent:
agent = Agent(name="context7_agent", mailbox=True)  # ← uAgent wrapper

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    client = await get_context7_client(ctx, session_id)  # ← Get our MCP client
    response = await client.process_query(query)        # ← Use our client
```

## 🔧 The Two-Tool Evaluation & Enhancement Pipeline

### Tool Chain Workflow

Our system uses **two MCP tools in sequence** with **intelligent evaluation** between each step:

```
User Query: "uAgent REST handlers"
     │
     ▼
┌─────────────────────┐
│   STEP 1: SEARCH    │
│  Multiple Strategy  │  ◄─── Try 5 different search approaches
│      Attempts       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│     TOOL 1:         │
│ resolve-library-id  │  ◄─── Find relevant libraries
│                     │
│ Input: "fetch.ai    │
│        uAgent"      │
│ Output: Library     │
│         candidates  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   EVALUATION 1:     │
│  Result Quality     │  ◄─── Claude evaluates relevance
│   Assessment        │
│                     │
│ • Is this relevant? │
│ • Which library ID? │
│ • Should we proceed?│
└─────────┬───────────┘
          │
      ┌───▼───┐
      │ Good? │
      └───┬───┘
    No    │    Yes
     ◄────┼────►
          │
          ▼
┌─────────────────────┐
│     TOOL 2:         │
│ get-library-docs    │  ◄─── Get targeted documentation
│                     │
│ Input: {            │
│   "id": "/fetchai/  │
│          docs",     │
│   "tokens": 12000,  │
│   "topic": "uAgent  │  ◄─── KEY: Topic filtering!
│           REST      │
│           handlers" │
│ }                   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   EVALUATION 2:     │
│  Content Quality    │  ◄─── Assess if results are sufficient
│   Assessment        │
│                     │
│ • Length check      │
│ • Relevance check   │
│ • Claude assessment │
└─────────┬───────────┘
          │
      ┌───▼───┐
      │ Good? │
      └───┬───┘
    No    │    Yes
     │    │    │
     │    ▼    ▼
     │ ┌─────────────────────┐
     │ │   ENHANCEMENT:      │
     │ │ Claude Formatting   │  ◄─── Final result enhancement
     │ │                     │
     └►│ • Clean structure   │
       │ • Remove metadata   │
       │ • Add examples      │
       │ • Focus on query    │
       └─────────┬───────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  FINAL RESPONSE     │  ◄─── High-quality, targeted answer
        └─────────────────────┘
```

### Detailed Tool Chaining Logic

#### 1. **Tool 1 → Evaluation → Tool 2 Chain**

```python
async def process_query(self, query: str) -> str:
    for strategy in self.search_strategies:
        search_terms = await strategy(query)
        
        for term in search_terms:
            # TOOL 1: Find libraries
            library_result = await self._session.call_tool(
                "resolve-library-id", 
                {"libraryName": term}
            )
            
            # EVALUATION 1: Is this relevant?
            evaluation = await self._evaluate_search_results(
                query, term, library_result.content
            )
            
            if evaluation["is_relevant"]:
                library_id = evaluation["selected_library_id"]
                
                # TOOL 2: Get docs with enhancement
                docs_result = await self._get_targeted_documentation(
                    library_id, query, term
                )
                
                # ENHANCEMENT: Format with Claude
                return await self._format_documentation_response(
                    query, docs_result.content, library_id, term
                )
```

#### 2. **Multi-Level Documentation Retrieval**

```python
async def _get_targeted_documentation(self, library_id: str, original_query: str, search_term: str):
    # LEVEL 1: Topic-focused search (most specific)
    docs_result = await self._session.call_tool(
        "get-library-docs",
        {
            "context7CompatibleLibraryID": library_id,
            "tokens": 12000,
            "topic": original_query  # "uAgent REST handlers"
        }
    )
    
    # EVALUATION 2: Quality assessment
    quality = await self._assess_content_quality(docs_result.content, original_query)
    
    if quality["is_sufficient"]:
        return docs_result
    
    # LEVEL 2: Keyword-based search (fallback)
    keywords = await self._extract_search_keywords(original_query)
    for keyword in keywords:
        docs_result = await self._session.call_tool(
            "get-library-docs",
            {
                "context7CompatibleLibraryID": library_id,
                "tokens": 10000,
                "topic": keyword  # "REST" or "handlers"
            }
        )
        
        quality = await self._assess_content_quality(docs_result.content, original_query)
        if quality["is_sufficient"]:
            return docs_result
    
    # LEVEL 3: General search (final fallback)
    return await self._session.call_tool(
        "get-library-docs",
        {"context7CompatibleLibraryID": library_id, "tokens": 8000}
    )
```

## 🧠 Intelligent Evaluation System

### Evaluation 1: Library Relevance Assessment

```python
async def _evaluate_search_results(self, original_query: str, search_term: str, content: Any):
    """Claude evaluates if found libraries are relevant to user's query"""
    
    evaluation_prompt = f"""
Original user query: "{original_query}"
Search term used: "{search_term}"

Library search results:
{text_content}

Evaluate:
1. Are these results relevant to the original user query?
2. Which library ID is the best match?

Format:
RELEVANT: [YES/NO]
LIBRARY_ID: [/fetchai/docs or NONE]
REASON: [Brief explanation]
"""
    
    response = await self._call_claude(evaluation_prompt)
    
    # Parse Claude's evaluation
    is_relevant = "RELEVANT: YES" in response
    library_id = self._extract_library_id(response)
    
    return {
        "is_relevant": is_relevant and library_id is not None,
        "selected_library_id": library_id,
        "reason": self._extract_reason(response)
    }
```

### Evaluation 2: Content Quality Assessment

```python
async def _assess_content_quality(self, content: Any, original_query: str):
    """Assess if retrieved documentation is sufficient for the user's query"""
    
    text_content = self._extract_text_content(content)
    
    # Quick check: minimum content length
    if len(text_content.strip()) < 100:
        return {"is_sufficient": False, "reason": "Insufficient content"}
    
    # Claude assessment for relevance and quality
    assessment_prompt = f"""
User's query: "{original_query}"

Retrieved content preview:
{text_content[:1500]}...

Assessment:
1. Does this contain information relevant to the user's query?
2. Are there code examples or specific details that help?
3. Is there enough substance for a useful response?

Format:
SUFFICIENT: [YES/NO]
REASON: [Brief explanation]
"""
    
    response = await self._call_claude(assessment_prompt)
    
    is_sufficient = "SUFFICIENT: YES" in response
    reason = self._extract_reason_from_assessment(response)
    
    return {
        "is_sufficient": is_sufficient,
        "reason": reason
    }
```

## 🎨 Result Enhancement Pipeline

### Three-Stage Enhancement Process

#### Stage 1: Raw MCP Results
```json
{
  "content": [
    {
      "text": "TITLE: Define Custom GET Endpoint - uAgents Python\nDESCRIPTION: Use the `@on_rest_get()` decorator...\nSOURCE: https://github.com/fetchai/docs/...\nCODE: ```python\n@agent.on_rest_get(\"/custom_get_route\", Response)\n..."
    }
  ]
}
```

#### Stage 2: Content Extraction & Cleaning
```python
def _extract_text_content(self, content: Any) -> str:
    """Extract and clean raw MCP content"""
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if hasattr(item, 'text'):
                text_content += item.text
            elif isinstance(item, dict) and 'text' in item:
                text_content += item['text']
    return text_content
```

#### Stage 3: Claude-Powered Formatting
```python
async def _format_documentation_response(self, original_query: str, raw_content: Any, library_id: str, successful_search_term: str):
    """Transform raw documentation into polished, user-focused response"""
    
    formatting_prompt = f"""
Original User Query: "{original_query}"
Successful Search Term: "{successful_search_term}"

Raw Documentation Snippets:
{text_content}

Transform this into a professional response:

Requirements:
1. Focus on answering the original query specifically
2. Create clear headings and organize logically  
3. Include relevant code examples with proper formatting
4. Remove duplicate information and metadata headers (TITLE:, DESCRIPTION:, SOURCE:)
5. Use markdown formatting for readability
6. Make it clear this answers their original question

Target: Professional documentation that directly addresses "{original_query}"
"""
    
    claude_response = await self._call_claude(formatting_prompt)
    formatted_content = claude_response.content[0].text.strip()
    
    # Add source attribution
    attribution = f"\n\n---\n*Found via search: '{successful_search_term}' | Source: Context7 MCP ({library_id})*"
    
    return formatted_content + attribution
```

### Before vs After Enhancement

**Before (Raw MCP Output):**
```
TITLE: Define Custom GET Endpoint - uAgents Python
DESCRIPTION: Use the `@on_rest_get()` decorator to define a custom GET endpoint
SOURCE: https://github.com/fetchai/docs/blob/main/pages/guides/agents/intermediate/rest-endpoints.mdx#_snippet_0
CODE: ```python
@agent.on_rest_get("/custom_get_route", Response)
async def handle_get(ctx: Context) -> Dict[str, Any]:
    return {"field": <value>}
```
```

**After (Claude Enhancement):**
```markdown
# uAgent REST Handler Documentation

This guide demonstrates how to implement REST handlers in uAgents for handling HTTP GET requests.

## Basic GET Handler Setup

Use the `@agent.on_rest_get()` decorator to define GET endpoints:

```python
@agent.on_rest_get("/custom_get_route", Response)
async def handle_get(ctx: Context) -> Dict[str, Any]:
    return {
        "field": <value>,
    }
```

## Complete Example

[... well-structured, comprehensive guide ...]
```

## 🚀 Remote MCP Server Integration

### Why Remote MCP Server?

We use the **remote Context7 MCP server** via npx rather than a local implementation:

**Advantages:**
- ✅ **Always up-to-date**: Remote server maintains current documentation
- ✅ **No local maintenance**: No need to sync documentation databases
- ✅ **Scalable**: Handles multiple concurrent requests
- ✅ **Reliable**: Professional infrastructure and uptime

**How It Works:**
```python
# npx downloads and runs the remote MCP server locally
params = mcp.StdioServerParameters(
    command="npx",
    args=["-y", "@upstash/context7-mcp"]  # Remote package
)

# This creates a local proxy to the remote Context7 service
read_stream, write_stream = await stdio_client(params)
session = mcp.ClientSession(read_stream, write_stream)
```

### MCP Communication Flow

```
Your Agent (Local)           Context7 MCP Server (Remote)
      │                              │
      │ 1. npx downloads package     │
      │ ──────────────────────────►  │
      │                              │
      │ 2. stdio connection          │
      │ ◄──────────────────────────  │
      │                              │
      │ 3. initialize session        │
      │ ──────────────────────────►  │
      │                              │
      │ 4. call resolve-library-id   │
      │ ──────────────────────────►  │
      │                              │
      │ 5. library search results    │
      │ ◄──────────────────────────  │
      │                              │
      │ 6. call get-library-docs     │
      │ ──────────────────────────►  │
      │                              │
      │ 7. documentation content     │
      │ ◄──────────────────────────  │
```

## 🔧 Five Intelligent Search Strategies

### Strategy Implementation Details

#### 1. **Exact Match Strategy**
```python
async def _strategy_exact_match(self, query: str) -> List[str]:
    """Try user's query exactly as provided"""
    return [query]

# Example: "uAgent REST handlers" → ["uAgent REST handlers"]
```

#### 2. **Framework Context Strategy** 
```python
async def _strategy_add_framework_context(self, query: str) -> List[str]:
    """Use Claude to add relevant framework context"""
    
    context_prompt = f"""
Given: "{query}"
Generate 3 search terms with framework context.

Examples:
- "routing" → "next.js routing", "react router", "express routing"
- "uAgent" → "fetch.ai uAgent", "autonomous agent", "uagents framework"

Terms:
"""
    
    claude_response = await self._call_claude(context_prompt)
    return self._parse_terms(claude_response)

# Example: "authentication" → ["passport.js authentication", "firebase auth", "oauth authentication"]
```

#### 3. **Language Context Strategy**
```python
async def _strategy_add_language_context(self, query: str) -> List[str]:
    """Add programming language context"""
    languages = ["python", "javascript", "typescript", "java", "go", "rust"]
    return [f"{query} {lang}" for lang in languages[:3]]

# Example: "database connection" → ["database connection python", "database connection javascript", "database connection typescript"]
```

#### 4. **Popular Alternatives Strategy**
```python
async def _strategy_try_popular_alternatives(self, query: str) -> List[str]:
    """Try known alternatives for common terms"""
    alternatives_map = {
        "agent": ["uagent", "fetch.ai", "autonomous agent", "uagents framework"],
        "uagent": ["fetch.ai uagent", "uagents python", "autonomous agent"],
        "rest": ["fastapi rest", "express rest", "flask rest", "rest api"],
        "handlers": ["message handlers", "event handlers", "request handlers"],
        "auth": ["authentication", "authorization", "oauth", "passport.js"],
        "database": ["mongodb", "postgresql", "sqlite", "prisma"],
        "api": ["rest api", "graphql api", "api framework"]
    }
    
    query_lower = query.lower()
    for key, alternatives in alternatives_map.items():
        if key in query_lower:
            return alternatives
    return []

# Example: "rest handlers" → ["fastapi rest", "express rest", "flask rest", "rest api"]
```

#### 5. **Keyword Extraction Strategy**
```python
async def _strategy_extract_keywords(self, query: str) -> List[str]:
    """Use Claude to extract key technical terms"""
    
    extraction_prompt = f"""
Extract 2-3 key technical terms from: "{query}"

Focus on:
- Technology names (React, uAgent, MongoDB)
- Technical concepts (authentication, routing, handlers)
- Tool names (Docker, fetch.ai, Kubernetes)

Keywords:
"""
    
    claude_response = await self._call_claude(extraction_prompt)
    return self._parse_keywords(claude_response)

# Example: "uAgent REST handlers documentation" → ["uAgent", "REST", "handlers"]
```

## 🌐 ASI:One Integration & Discoverability

### Complete Chat Protocol Setup

```python
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,      # Protocol specification
    ChatMessage,             # User messages  
    ChatAcknowledgement,     # Message confirmations
    TextContent,             # Text content wrapper
)

# Create chat protocol instance
chat_proto = Protocol(spec=chat_protocol_spec)

# Handle incoming chat messages
@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    session_id = str(ctx.session)
    
    # 1. Send acknowledgment immediately
    ack_msg = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack_msg)
    
    # 2. Process each content item
    for item in msg.content:
        if isinstance(item, TextContent):
            query = item.text.strip()
            
            # 3. Update session activity
            if session_id not in user_sessions:
                user_sessions[session_id] = {}
            user_sessions[session_id]['last_activity'] = time.time()
            
            # 4. Send processing notification
            processing_msg = ChatMessage(
                msg_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                content=[TextContent(
                    type="text", 
                    text="🔍 Searching for documentation... Using multiple strategies."
                )]
            )
            await ctx.send(sender, processing_msg)
            
            # 5. Get MCP client and process
            client = await get_context7_client(ctx, session_id)
            response_text = await client.process_query(query)
            
            # 6. Send final response
            response_msg = ChatMessage(
                msg_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                content=[TextContent(type="text", text=response_text)]
            )
            await ctx.send(sender, response_msg)

# Handle acknowledgments
@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # Could log successful message delivery
    pass
```

### Agent Configuration for ASI:One

```python
# Critical configuration for ASI:One discoverability
agent = Agent(
    name="context7_agent",        # Discoverable name
    port=8007,                    # Local development port
    mailbox=True                  # REQUIRED for ASI:One!
)

# Include chat protocol (REQUIRED)
agent.include(chat_proto)

# Session management for multi-turn conversations
session_clients: Dict[str, Context7MCPClient] = {}
user_sessions: Dict[str, Dict[str, Any]] = {}
```

### Session Management Implementation

```python
SESSION_TIMEOUT = 30 * 60  # 30 minutes

def is_session_valid(session_id: str) -> bool:
    """Check if user session is valid and not expired"""
    if session_id not in user_sessions:
        return False
    
    last_activity = user_sessions[session_id].get('last_activity', 0)
    if time.time() - last_activity > SESSION_TIMEOUT:
        # Clean up expired session
        if session_id in user_sessions:
            del user_sessions[session_id]
        if session_id in session_clients:
            await session_clients[session_id].cleanup()
            del session_clients[session_id]
        return False
    
    return True

async def get_context7_client(ctx: Context, session_id: str) -> Context7MCPClient:
    """Get or create MCP client for user session"""
    if session_id not in session_clients or not is_session_valid(session_id):
        # Create new MCP client for this session
        client = Context7MCPClient(ctx)
        await client.connect()
        session_clients[session_id] = client
    
    return session_clients[session_id]
```

## 📋 Complete Requirements & Setup

### Requirements.txt
```txt
# Core uAgent framework
uagents>=0.12.0
uagents-core>=0.1.0

# MCP client dependencies  
mcp>=1.0.0

# AI integration
anthropic>=0.25.0

# Utilities
python-dotenv>=1.0.0
asyncio
typing-extensions
```

### Environment Setup

```bash
# 1. Create project directory
mkdir context7-mcp-agent
cd context7-mcp-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify Node.js (required for npx)
node --version  # Should be 16+
npm --version

# 5. Test MCP server access
npx -y @upstash/context7-mcp
```

### Environment Variables (.env)

```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# Optional customization
AGENT_NAME=context7_agent
AGENT_PORT=8007
SESSION_TIMEOUT=1800
MCP_SERVER_PACKAGE=@upstash/context7-mcp
```

## 🎛️ Customization & Extension

### Adapting for Other MCP Servers

#### Step 1: Change MCP Server Package
```python
# In connect() method, change:
params = mcp.StdioServerParameters(
    command="npx",
    args=["-y", "@your-org/your-mcp-server"]  # Your MCP server
)
```

#### Step 2: Discover Available Tools
```python
async def connect(self):
    # ... connection setup ...
    
    # Discover tools
    list_tools_result = await self._session.list_tools()
    self.tools = list_tools_result.tools
    
    # Log available tools
    for tool in self.tools:
        self._ctx.logger.info(f"Tool: {tool.name}")
        self._ctx.logger.info(f"Description: {tool.description}")
        self._ctx.logger.info(f"Input Schema: {tool.inputSchema}")
```

#### Step 3: Adapt Tool Calls
```python
# Example for different MCP server
async def process_query(self, query: str) -> str:
    # Tool 1: Search (adapt parameters)
    search_result = await self._session.call_tool(
        "your-search-tool",          # Different tool name
        {"query": query, "limit": 10}  # Different parameters
    )
    
    # Tool 2: Retrieve (adapt parameters)  
    content_result = await self._session.call_tool(
        "your-content-tool",
        {
            "id": selected_id,
            "format": "markdown",       # Different parameters
            "include_examples": True
        }
    )
```

#### Step 4: Update Search Strategies
```python
# Add domain-specific alternatives
alternatives_map = {
    "your-domain-term": ["alt1", "alt2", "alt3"],
    "api": ["your-api-framework", "your-api-tool"],
    # Add terms specific to your domain
}
```





## 📚 Additional Resources & Learning

### Key Documentation Links

- **uAgents Framework**: [uAgents](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)
- **MCP Specification**: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Context7 MCP Server**: [https://github.com/upstash/context7-mcp](https://github.com/upstash/context7-mcp)
- **ASI:One Platform**: [ASI:One](https://asi1.ai)
- **Agentverse Console**: [https://agentverse.ai](https://agentverse.ai)
- **Anthropic Claude API**: [https://docs.anthropic.com](https://docs.anthropic.com)

### Related Projects & Examples

- **Other MCP Servers**: [https://github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- **uAgent Examples**: [https://github.com/fetchai/uAgents/tree/main/examples](https://github.com/fetchai/innovation-lab-examples)
- **Chat Protocol Examples**: [https://docs.fetch.ai/uAgents/intermediate/chat-protocol](https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-chat-protocol)



---

## 🎊 Conclusion

This Context7 MCP Agent represents a sophisticated integration of multiple technologies:

- **🤖 uAgent Framework**: For ASI:One discoverability and chat protocol handling
- **🔌 Custom MCP Client**: For intelligent communication with remote documentation services  
- **🧠 Claude AI Integration**: For evaluation, enhancement, and formatting
- **🔍 Multi-Strategy Search**: For maximum query success rates
- **⚡ Quality Assessment**: For ensuring relevant, high-quality responses

The architecture demonstrates how to **wrap MCP clients inside uAgents** to create **intelligent, discoverable agents** that can be easily deployed to Agentverse and accessed through ASI:One.

**Use this as a template** for integrating any MCP server with the uAgent ecosystem, adapting the search strategies, evaluation logic, and enhancement processes for your specific domain and use case.

**Built using uAgents, MCP, and Claude AI**

*Ready to bring more MCP servers to the Agentverse? Follow this guide and contribute to the growing ecosystem of intelligent, interconnected agents!*
