# Fetch.ai Development Rules

## 📚 Official Documentation Links

**Always reference these official Fetch.ai Innovation Lab docs:**

### Core Documentation
- **Introduction**: https://innovationlab.fetch.ai/resources/docs/intro

### Agent Creation
- **uAgent Creation**: https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation
- **SDK Creation**: https://innovationlab.fetch.ai/resources/docs/agent-creation/sdk-creation
- **uAgents Adapter Guide**: https://innovationlab.fetch.ai/resources/docs/agent-creation/uagents-adapter-guide

### Agent Communication
- **Agent Chat Protocol**: https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-chat-protocol
- **uAgent to uAgent Communication**: https://innovationlab.fetch.ai/resources/docs/agent-communication/uagent-uagent-communication
- **SDK to uAgent Communication**: https://innovationlab.fetch.ai/resources/docs/agent-communication/sdk-uagent-communication
- **SDK to SDK Communication**: https://innovationlab.fetch.ai/resources/docs/agent-communication/sdk-sdk-communication

### Agentverse
- **Agentverse Overview**: https://innovationlab.fetch.ai/resources/docs/agentverse/agentverse
- **Agentverse API Key**: https://innovationlab.fetch.ai/resources/docs/agentverse/agentverse-api-key
- **Searching Agents**: https://innovationlab.fetch.ai/resources/docs/agentverse/searching
- **Agentverse Applications**: https://innovationlab.fetch.ai/resources/docs/agentverse/agentverse-based-application

### ASI:One LLM Integration
- **ASI:One Mini Introduction**: https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-introduction
- **ASI:One Mini Getting Started**: https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-getting-started
- **ASI:One Mini API Reference**: https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-api-reference
- **ASI:One Mini Chat Completion**: https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-chat-completion
- **ASI:One Mini Function Calling**: https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-function-calling

### MCP Integration
- **What is MCP**: https://innovationlab.fetch.ai/resources/docs/mcp-integration/what-is-mcp

### Examples

#### On-Chain Integrations
- **On-Chain Agents**: https://innovationlab.fetch.ai/resources/docs/examples/on-chain-examples/on-chain-agents
- **Mettalex Agents**: https://innovationlab.fetch.ai/resources/docs/examples/on-chain-examples/mettalex-agents
- **Solana Agents**: https://innovationlab.fetch.ai/resources/docs/examples/on-chain-examples/solana-agents
- **BNB Chain Agents**: https://innovationlab.fetch.ai/resources/docs/examples/on-chain-examples/bnb-chain-agents

#### Other Agentic Frameworks
- **LangChain Integration**: https://innovationlab.fetch.ai/resources/docs/examples/other-frameworks/langchain
- **AutoGen Integration**: https://innovationlab.fetch.ai/resources/docs/examples/other-frameworks/autogen
- **CrewAI Integration**: https://innovationlab.fetch.ai/resources/docs/examples/other-frameworks/crewai
- **Financial Analysis AI Agent**: https://innovationlab.fetch.ai/resources/docs/examples/other-frameworks/financial-analysis-ai-agent

#### ASI:One Examples
- **ASI1 Mini Language Tutor**: https://innovationlab.fetch.ai/resources/docs/examples/asione/asi1-mini-language-tutor
- **ASI1 Chat System**: https://innovationlab.fetch.ai/resources/docs/examples/asione/asi1-chat-system
- **ASI DeFi AI Agent**: https://innovationlab.fetch.ai/resources/docs/examples/asione/asi-defi-ai-agent
- **ASI LangChain Tavily**: https://innovationlab.fetch.ai/resources/docs/examples/asione/asi-langchain-tavily

#### Chat Protocol Examples
- **ASI1 Compatible uAgents**: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi1-compatible-uagents
- **Image Analysis Agent**: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/image-analysis-agent
- **Image Generation Agent**: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/image-generation-agent
- **Solana Wallet Agent**: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/solana-wallet-agent

#### uAgents Adapter Examples
- **CrewAI Adapter Example**: https://innovationlab.fetch.ai/resources/docs/examples/adapters/crewai-adapter-example
- **LangGraph Adapter Example**: https://innovationlab.fetch.ai/resources/docs/examples/adapters/langgraph-adapter-example

#### TransactAI Examples
- **TransactAI Example**: https://innovationlab.fetch.ai/resources/docs/examples/transactAI/transactai-example

#### Integration Examples
- **Stripe Integration**: https://innovationlab.fetch.ai/resources/docs/examples/integrations/stripe-integration
- **Frontend Integration**: https://innovationlab.fetch.ai/resources/docs/examples/integrations/frontend-integration

#### MCP Integration Examples
- **LangGraph MCP Agent**: https://innovationlab.fetch.ai/resources/docs/examples/mcp-integration/langgraph-mcp-agent-example
- **Multi-Server Agent**: https://innovationlab.fetch.ai/resources/docs/examples/mcp-integration/multi-server-agent-example
- **Connect Agent to Multiple Remote MCP Servers**: https://innovationlab.fetch.ai/resources/docs/examples/mcp-integration/connect-an-agent-to-multiple-remote-mcp-servers
- **MCP Adapter Example**: https://innovationlab.fetch.ai/resources/docs/examples/mcp-integration/mcp-adapter-example

## Package Versions & Installation

**CRITICAL: Always use these exact versions for compatibility:**

```bash
# Core uAgents Framework
pip install uagents==0.22.5

# LangChain Integration
pip install langchain==0.3.23
pip install langchain-openai==0.2.14

# LangGraph for Stateful Agents
pip install langgraph==0.3.20

# CrewAI Integration
pip install crewai==0.126.0

# uAgents Adapter (includes LangChain, CrewAI, MCP support)
pip install uagents-adapter==0.4.0
```

**Installation Commands by Use Case:**

```bash
# Basic uAgent development
pip install uagents==0.22.5

# uAgent + LangChain integration
pip install uagents==0.22.5 langchain==0.3.23 langchain-openai==0.2.14

# uAgent + LangGraph workflows
pip install uagents==0.22.5 langgraph==0.3.20 langchain-openai==0.2.14

# uAgent + CrewAI integration
pip install uagents==0.22.5 crewai==0.126.0

# Full framework integration (all adapters)
pip install uagents==0.22.5 uagents-adapter==0.4.0 langchain==0.3.23 langgraph==0.3.20 crewai==0.126.0 langchain-openai==0.2.14
```

**Important Compatibility Notes:**
- `uagents==0.22.5` requires `pydantic` (auto-installed as dependency)
- `uagents-adapter==0.4.0` includes integrations for LangChain, CrewAI, and MCP
- These versions have been tested together and avoid Pydantic v1/v2 compatibility issues
- Always use virtual environments to prevent version conflicts

## Essential Imports

### Core uAgents Framework
```python
from uagents import Agent, Context, Model, Protocol, Bureau
from pydantic import Field  # Use compatible Pydantic syntax with uagents==0.22.5
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List, Annotated
```

### Chat Protocol Integration
```python
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, EndSessionContent,
    StartSessionContent, TextContent, chat_protocol_spec
)
```

### Framework Adapters
```python
# uAgents Adapters for integration with other frameworks
from uagents_adapter import (
    LangchainRegisterTool,     # LangChain integration
    CrewaiRegisterTool,        # CrewAI integration  
    MCPServerAdapter,          # MCP Server integration
    ResponseMessage,           # Common response model
    cleanup_uagent,            # Cleanup utilities
    cleanup_all_uagents
)
```

### ASI:One LLM Integration
```python
# ASI:One LLM endpoint addresses (rate limited to 6 requests/hour)
OPENAI_AGENT = 'agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y'
CLAUDE_AGENT = 'agent1qvk7q2av3e2y5gf5s90nfzkc8a48q3wdqeevwrtgqfdl0k78rspd6f2l4dx'
```

## Core Patterns

### uAgent Creation Pattern
```python
from uagents import Agent, Context, Model, Protocol

# ALWAYS use descriptive names and unique seeds
agent = Agent(
    name="descriptive_service_name",
    seed="unique_deterministic_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=True  # Enable for Agentverse integration
)

# ALWAYS include startup/shutdown handlers
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Agent {agent.name} started: {agent.address}")
    # Note: Wallet funding happens automatically - no need for fund_agent_if_low

@agent.on_event("shutdown") 
async def shutdown(ctx: Context):
    ctx.logger.info("Cleaning up resources...")
```

### Message Model Standards (Pydantic Compatible)
```python
from uagents import Model
from pydantic import Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime, UTC

# ALWAYS use descriptive enums for capabilities
class ServiceType(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    API_INTEGRATION = "api_integration"
    ML_INFERENCE = "ml_inference"

# CORRECT: Compatible message model pattern
class ServiceRequest(Model):
    request_id: str = Field(..., description="Unique identifier")
    service_type: ServiceType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    timestamp: str = Field(default="", description="Request timestamp")

# CORRECT: Simple validation without problematic decorators
class HelloMessage(Model):
    message: str = Field(..., description="Hello message")
    sender_name: str = Field(..., description="Name of the sender")
    timestamp: str = Field(default="", description="Message timestamp")

    def __init__(self, **data):
        # Custom validation in __init__ if needed
        if 'timestamp' not in data or not data['timestamp']:
            data['timestamp'] = datetime.now(UTC).isoformat()
        super().__init__(**data)
```

### Protocol Implementation Pattern
```python
# ALWAYS version your protocols
service_protocol = Protocol(name="service_protocol", version="1.0")

@service_protocol.on_message(model=ServiceRequest, replies=ServiceResponse)
async def handle_request(ctx: Context, sender: str, msg: ServiceRequest):
    try:
        # ALWAYS log incoming requests
        ctx.logger.info(f"Processing {msg.request_id} from {sender}")
        
        # ALWAYS validate capabilities
        if not await validate_capability(msg.service_type):
            await ctx.send(sender, ErrorResponse(
                request_id=msg.request_id,
                error="Capability not supported"
            ))
            return
        
        # ALWAYS measure execution time
        start_time = time.time()
        result = await process_request(msg)
        execution_time = time.time() - start_time
        
        await ctx.send(sender, SuccessResponse(
            request_id=msg.request_id,
            result=result,
            execution_time=execution_time
        ))
        
    except Exception as e:
        ctx.logger.error(f"Request {msg.request_id} failed: {e}")
        await ctx.send(sender, ErrorResponse(
            request_id=msg.request_id,
            error=str(e)
        ))
```

## Agent Deployment Patterns

### 1. Hosted Agents (Agentverse)
```python
# Standard hosted agent - runs on Agentverse
agent = Agent(
    name="hosted_service_agent",
    # No seed needed for hosted agents
    # No port/endpoint needed
)

# Supported libraries: uagents, requests, openai, langchain, etc.
# Full Python standard library available
```

### 2. Local Agents
```python
# Local agent - runs on your machine
agent = Agent(
    name="local_service_agent", 
    seed="local_unique_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"]
)

# Complete freedom for any Python library
# Requires managing uptime and scaling
```

### 3. Mailbox Agents
```python
# Mailbox agent - local but connects to Agentverse
agent = Agent(
    name="mailbox_service_agent",
    seed="mailbox_unique_seed_phrase", 
    port=8000,
    mailbox=True  # Connects to Agentverse via mailbox
)

# Best of both: local control + Agentverse integration
```

## ASI:One LLM Integration

### Rate-Limited LLM Queries
```python
class ASIOneClient:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.rate_limiter = RateLimiter(max_requests=6, window_hours=1)
    
    async def query(self, prompt: str, endpoint_type: str = "general"):
        # ALWAYS check rate limits
        if not self.rate_limiter.can_make_request():
            raise ValueError("Rate limit exceeded")
        
        self.rate_limiter.record_request()
        # Query ASI:One endpoint...
```

### Intent Analysis Pattern
```python
async def analyze_user_intent(user_query: str) -> AgentCapability:
    analysis_prompt = f"""
    Extract the required capability from this query:
    Query: {user_query}
    
    Respond with one of: data_analysis, api_integration, ml_inference, blockchain_interaction
    """
    
    response = await asi_client.query(analysis_prompt, "analysis")
    return parse_capability(response)
```

## LangGraph Agent Integration (Official Pattern)

### LangGraph Adapter Pattern

Based on the @official LangGraph adapter example, here's the recommended approach for creating and deploying LangGraph agents:

```python
import os
import time
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import chat_agent_executor
from langchain_core.messages import HumanMessage

from uagents_adapter import LangchainRegisterTool, cleanup_uagent

# Load environment variables
load_dotenv()

# Set your API keys
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
API_TOKEN = os.environ["AGENTVERSE_API_KEY"]

if not API_TOKEN:
    raise ValueError("Please set AGENTVERSE_API_KEY environment variable")

# Set up tools and LLM
tools = [TavilySearchResults(max_results=3)]
model = ChatOpenAI(temperature=0)

# LangGraph-based executor
app = chat_agent_executor.create_tool_calling_executor(model, tools)

# Wrap LangGraph agent into a function for UAgent
def langgraph_agent_func(query):
    # Handle input if it's a dict with 'input' key
    if isinstance(query, dict) and 'input' in query:
        query = query['input']
    
    messages = {"messages": [HumanMessage(content=query)]}
    final = None
    for output in app.stream(messages):
        final = list(output.values())[0]  # Get latest
    return final["messages"][-1].content if final else "No response"

# Register the LangGraph agent via uAgent
tool = LangchainRegisterTool()
agent_info = tool.invoke(
    {
        "agent_obj": langgraph_agent_func,
        "name": "langgraph_tavily_agent",
        "port": 8080,
        "description": "A LangGraph-based Tavily-powered search agent",
        "api_token": API_TOKEN,
        "mailbox": True
    }
)

print(f"✅ Registered LangGraph agent: {agent_info}")

# Keep the agent alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Shutting down LangGraph agent...")
    cleanup_uagent("langgraph_tavily_agent")
    print("✅ Agent stopped.")
```

### **CRITICAL: Follow the Official Pattern**

**❌ DON'T build complex StateGraph workflows for simple tasks**  
**✅ DO use `langgraph.prebuilt.chat_agent_executor` + simple function wrapper**

This is the **official Fetch.ai recommended approach** shown in the @LangGraph adapter documentation.

### Key LangGraph Integration Components

1. **LangGraph Setup**:
   - **ALWAYS use `langgraph.prebuilt.chat_agent_executor`** for agent creation
   - Configure tools (like Tavily search) for external data retrieval
   - Use OpenAI's ChatGPT or similar LLM for language capabilities

2. **Function Wrapper**:
   - Wrap the LangGraph app in a **simple function** that accepts queries
   - Handle input format conversion for uAgents-adapter compatibility
   - Process streaming output from LangGraph executor

3. **uAgent Registration**:
   - Use `LangchainRegisterTool` to register the **function directly** as a uAgent
   - Configure port, description, and mailbox for Agentverse integration
   - **No custom wrapper classes needed** - pass function directly

4. **Deployment Fix**:
   - **CRITICAL**: Fix event loop issues by using proper async deployment pattern:
   ```python
   # WRONG - causes "no current event loop" error
   tool.invoke(config)
   
   # RIGHT - proper async deployment
   import asyncio
   
   async def deploy_agent():
       tool = LangchainRegisterTool()
       result = tool.invoke(config)
       return result
   
   # Run in main thread
   if __name__ == "__main__":
       asyncio.run(deploy_agent())
   ```

### Sample requirements.txt for LangGraph Agents

```txt
uagents==0.22.5
uagents-adapter==0.4.0
langchain-openai==0.2.14
langchain-community==0.3.21
langgraph==0.3.20
python-dotenv==1.0.0
tavily-python>=0.3.0
```

### Client Agent for LangGraph Communication

```python
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Protocol, Context

# Import chat protocol components
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# Initialize client agent
client_agent = Agent(
    name="client_agent",
    port=8082,
    mailbox=True,
    seed="client agent testing seed"
)

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Update with your LangGraph Agent's address
langgraph_agent_address = "agent1q0zyxrneyaury3f5c7aj67hfa5w65cykzplxkst5f5mnyf4y3em3kplxn4t"

@client_agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info(f"My name is {ctx.agent.name} and my address is {ctx.agent.address}")

    # Send initial message to LangGraph agent
    initial_message = ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="Give me a list of latest agentic AI trends")]
    )
    await ctx.send(langgraph_agent_address, initial_message)

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(f"Received message from {sender}: {item.text}")
            
            # Send acknowledgment
            ack = ChatAcknowledgement(
                timestamp=datetime.utcnow(),
                acknowledged_msg_id=msg.msg_id
            )
            await ctx.send(sender, ack)

@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")

# Include the protocol in the agent
client_agent.include(chat_proto, publish_manifest=True)

if __name__ == '__main__':
    client_agent.run()
```

### Why Use LangGraph with uAgents?

LangGraph offers several advantages when combined with uAgents:

- **Advanced Orchestration**: Create complex reasoning flows using directed graphs
- **State Management**: Handle complex multi-turn conversations with state persistence  
- **Tool Integration**: Easily connect to external services and APIs
- **Debugging Capabilities**: Inspect and debug agent reasoning processes

By wrapping LangGraph with the uAgents adapter, you get sophisticated LLM orchestration with decentralized communication capabilities.

## Framework Integration via uAgents-Adapter

### Installation & Setup
```bash
# Install base adapter
pip install uagents-adapter

# Install with specific framework support
pip install "uagents-adapter[langchain]"    # LangChain integration
pip install "uagents-adapter[crewai]"       # CrewAI integration  
pip install "uagents-adapter[mcp]"          # MCP Server integration

# Install with all frameworks
pip install "uagents-adapter[langchain,crewai,mcp]"
```

### LangChain Agent Integration
```python
from uagents_adapter import LangchainRegisterTool
from langchain_core.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI

# Create LangChain agent
llm = ChatOpenAI(model_name="gpt-4")
agent = create_react_agent(llm, tools)
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Convert to uAgent and register with Agentverse
register_tool = LangchainRegisterTool()
result = register_tool.invoke({
    "agent_obj": agent_executor,
    "name": "langchain_service",
    "port": 8000,
    "description": "LangChain agent as uAgent service",
    "mailbox": True,  # ALWAYS enable for Agentverse
    "api_token": os.getenv("AGENTVERSE_API_TOKEN"),
    "return_dict": True
})
```

### ❌ DON'T - Use Complex StateGraph Workflows for Simple Tasks

```python
# WRONG - Complex custom StateGraph (avoid for simple tasks)
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from typing import Annotated, List, Dict, Any

class ComplexState(BaseModel):
    messages: Annotated[List[AnyMessage], add_messages] = Field(default=[])
    # ... many fields

class ComplexAgent:
    def build_graph(self) -> StateGraph:
        workflow = StateGraph(ComplexState)
        workflow.add_node("node1", self.node1)
        workflow.add_node("node2", self.node2)
        # ... many nodes and edges
        return workflow.compile()
```

### ✅ DO - Use Simple Function Wrapper Pattern (Official Approach)

```python
# GOOD - Simple function wrapper (recommended)
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import chat_agent_executor
from langchain_core.messages import HumanMessage

# Set up tools and LLM
tools = [TavilySearchResults(max_results=3)]
model = ChatOpenAI(temperature=0)

# Use prebuilt LangGraph executor
app = chat_agent_executor.create_tool_calling_executor(model, tools)

# Simple function wrapper - THIS IS THE OFFICIAL PATTERN
def langgraph_agent_func(query):
    if isinstance(query, dict) and 'input' in query:
        query = query['input']
    
    messages = {"messages": [HumanMessage(content=query)]}
    final = None
    for output in app.stream(messages):
        final = list(output.values())[0]
    return final["messages"][-1].content if final else "No response"

# Register directly with uAgents-adapter
tool = LangchainRegisterTool()
agent_info = tool.invoke({
    "agent_obj": langgraph_agent_func,  # Direct function reference
    "name": "simple_langgraph_agent",
    "description": "Simple LangGraph agent with tools",
    "api_token": os.getenv("AGENTVERSE_API_KEY"),
    "mailbox": True
})
```

### CrewAI Integration
```python
from uagents_adapter import CrewaiRegisterTool
from crewai import Crew, Agent as CrewAgent, Task

# Define CrewAI crew
crew_agent = CrewAgent(role="Researcher", goal="Research", backstory="...")
task = Task(description="Research task", agent=crew_agent)
crew = Crew(agents=[crew_agent], tasks=[task])

# Convert to uAgent
register_tool = CrewaiRegisterTool()
result = register_tool.invoke({
    "crew_obj": crew,
    "name": "crew_service", 
    "port": 8001,
    "mailbox": True,
    "query_params": {
        "topic": {"type": "string", "description": "Research topic", "required": True}
    },
    "example_query": "Research about artificial intelligence"
})
```

### MCP Server Integration 
```python
from uagents_adapter import MCPServerAdapter
from fastmcp import FastMCP

# Create FastMCP server with tools
mcp = FastMCP("My MCP Server")

@mcp.tool()
def calculate(expression: str) -> str:
    """Calculate mathematical expressions safely.
    
    ALWAYS include detailed docstrings for ASI:One discovery.
    """
    # Implementation here
    pass

# Create MCP adapter
mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    asi1_api_key=os.getenv("ASI1_API_KEY"),
    model="asi1-mini"  # Options: asi1-mini, asi1-extended, asi1-fast
)

# Add protocols to agent
agent = Agent(name="mcp_service", mailbox=True)
for protocol in mcp_adapter.protocols:
    agent.include(protocol)

mcp_adapter.run(agent)
```

### MCP Integration Approaches
1. **LangGraph + MCP Adapter**: LangGraph agent → uAgents-Adapter → Agentverse
2. **Remote MCP Servers**: uAgent client → Remote MCP servers (Smithery.ai) → Agentverse  
3. **FastMCP Server**: FastMCP server → MCPServerAdapter → Agentverse

## Environment Setup & Production Patterns

### Dependencies Management
```python
# requirements.txt for production agents
"""
# Core uAgents and LangGraph
uagents>=0.12.0
uagents-adapter>=0.1.0
langgraph>=0.0.65
langchain>=0.2.0
langchain-core>=0.2.0
langchain-openai>=0.1.0
langchain-community>=0.2.0

# Web search and external APIs
tavily-python>=0.3.0
requests>=2.31.0

# Data validation and environment
pydantic>=2.0.0
python-dotenv>=1.0.0

# Production monitoring
structlog>=23.1.0
"""
```

### Environment Configuration
```python
# Interactive setup for production deployment
import os
import getpass
from dotenv import load_dotenv

def setup_environment():
    """Interactive environment setup"""
    load_dotenv()
    
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API key for LLM functionality",
        "AGENTVERSE_API_TOKEN": "Agentverse API token for deployment"
    }
    
    optional_vars = {
        "TAVILY_API_KEY": "Tavily API for web search",
        "LANGCHAIN_API_KEY": "LangSmith for tracing"
    }
    
    # Check and prompt for missing variables
    for var, description in required_vars.items():
        if not os.getenv(var):
            value = getpass.getpass(f"Enter {description}: ")
            os.environ[var] = value
            print(f"✅ {var} configured")
    
    # Validate agent initialization
    try:
        from your_agent import agent
        if agent.graph is not None:
            print("✅ Agent initialized successfully!")
            return True
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return False

# Use in production deployment
if __name__ == "__main__":
    if setup_environment():
        # Deploy to Agentverse
        result = deploy_agent_to_agentverse()
        print(f"🚀 Agent deployed: {result}")
```

### Production Deployment Pattern
```python
import asyncio
import logging
from typing import Optional

class ProductionAgentManager:
    """Production-ready agent management"""
    
    def __init__(self, agent_name: str, config: dict):
        self.agent_name = agent_name
        self.config = config
        self.deployment_result: Optional[dict] = None
        
        # Setup structured logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(agent_name)
    
    async def deploy(self) -> dict:
        """Deploy agent with comprehensive error handling"""
        try:
            # Pre-deployment validation
            self._validate_environment()
            
            # Test agent locally
            test_result = await self._test_locally()
            if not test_result:
                raise ValueError("Local testing failed")
            
            # Deploy to Agentverse
            self.deployment_result = await self._deploy_to_agentverse()
            
            # Post-deployment verification
            await self._verify_deployment()
            
            self.logger.info(f"✅ {self.agent_name} deployed successfully")
            return self.deployment_result
            
        except Exception as e:
            self.logger.error(f"❌ Deployment failed: {e}")
            await self._cleanup_on_failure()
            raise
    
    def _validate_environment(self):
        """Validate all required environment variables"""
        required = ["OPENAI_API_KEY", "AGENTVERSE_API_TOKEN"]
        missing = [var for var in required if not os.getenv(var)]
        
        if missing:
            raise ValueError(f"Missing environment variables: {missing}")
    
    async def _test_locally(self) -> bool:
        """Test agent functionality locally"""
        test_queries = [
            "Test query 1",
            "Test query 2", 
            "Test query 3"
        ]
        
        for query in test_queries:
            try:
                result = await self.agent.process_query(query)
                if not result or "error" in result.lower():
                    return False
            except Exception as e:
                self.logger.error(f"Local test failed: {e}")
                return False
        
        return True
    
    async def _deploy_to_agentverse(self) -> dict:
        """Deploy to Agentverse with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                register_tool = LangchainRegisterTool()
                result = register_tool.invoke(self.config)
                return result
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = 2 ** attempt  # Exponential backoff
                self.logger.warning(f"Deployment attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

# Usage example
async def deploy_production_agent():
    config = {
        "agent_obj": your_agent_executor,
        "name": "production_research_agent",
        "description": "Production-ready research agent",
        "mailbox": True,
        "api_token": os.getenv("AGENTVERSE_API_TOKEN"),
        "query_params": {
            "query": {
                "type": "string",
                "description": "Research query",
                "required": True
            }
        }
    }
    
    manager = ProductionAgentManager("research_agent", config)
    result = await manager.deploy()
    return result
```

### Adapter Cleanup
```python
from uagents_adapter import cleanup_uagent, cleanup_all_uagents

# Clean up specific agent
cleanup_uagent("agent_name")

# Clean up all registered agents
cleanup_all_uagents()
```

## Chat Protocol Integration

### Enhanced Chat with ASI:One
```python
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent, EndSessionContent
)

@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    # ALWAYS acknowledge immediately
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.utcnow(),
        acknowledged_msg_id=msg.msg_id
    ))
    
    # ALWAYS store session context
    ctx.storage.set(str(ctx.session), sender)
    
    for item in msg.content:
        if isinstance(item, TextContent):
            # Route through ASI:One for intelligent responses
            response = await asi_orchestrator.intelligent_query_routing(item.text)
            await ctx.send(sender, create_text_chat(response))
```

### Complete ASI:One Compatible Agent Pattern
```python
from datetime import datetime
from uuid import uuid4
from typing import Any
from uagents import Context, Model, Protocol

# Chat protocol setup
def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )

chat_proto = Protocol(spec=chat_protocol_spec)
struct_output_client_proto = Protocol(
    name="StructuredOutputClientProtocol", version="0.1.0"
)

class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]

class StructuredOutputResponse(Model):
    output: dict[str, Any]

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Got message from {sender}")
    ctx.storage.set(str(ctx.session), sender)
    
    # Send acknowledgment
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.utcnow(), 
        acknowledged_msg_id=msg.msg_id
    ))

    for item in msg.content:
        if isinstance(item, TextContent):
            # Forward to ASI:One for parameter extraction
            await ctx.send(
                OPENAI_AGENT,  # or CLAUDE_AGENT
                StructuredOutputPrompt(
                    prompt=item.text,
                    output_schema=YourDataModel.schema()
                ),
            )

@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_structured_output_response(
    ctx: Context, sender: str, msg: StructuredOutputResponse
):
    session_sender = ctx.storage.get(str(ctx.session))
    if session_sender is None:
        ctx.logger.error("No session sender found")
        return

    if "<UNKNOWN>" in str(msg.output):
        await ctx.send(session_sender, create_text_chat(
            "Sorry, I couldn't process your request."
        ))
        return

    # Parse and process structured output
    parsed_data = YourDataModel.parse_obj(msg.output)
    result = await process_request(parsed_data)
    
    await ctx.send(session_sender, create_text_chat(str(result)))

# Include protocols
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)
```

### Rate Limiting for Production
```python
from uagents.experimental.quota import QuotaProtocol, RateLimit

# ALWAYS implement rate limiting for production agents
proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="Service-Protocol",
    version="1.0.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
)

@proto.on_message(ServiceRequest, replies={ServiceResponse, ErrorMessage})
async def handle_request(ctx: Context, sender: str, msg: ServiceRequest):
    # Rate limiting automatically applied
    try:
        result = await process_service_request(msg)
        await ctx.send(sender, ServiceResponse(result=result))
    except Exception as err:
        await ctx.send(sender, ErrorMessage(error=str(err)))
```

## LangGraph Best Practices

### ❌ DON'T - Overcomplicate LangGraph Agents

```python
# WRONG - Building complex custom workflows for simple tasks
class MathAgentExecutor:
    def __init__(self):
        self.graph = self.build_complex_graph().compile()
    
    def build_complex_graph(self):
        graph = StateGraph(ComplexState)
        graph.add_node("ROUTER", router)
        graph.add_node("PARSE_MATH", parse_math)
        graph.add_node("ADD_NUMBERS", add_numbers)
        # ... 10+ nodes with complex routing
        return graph
    
    async def ainvoke(self, inputs):
        # Complex wrapper logic
        result = await self.graph.ainvoke(initial_state)
        return {"output": result["messages"][-1].content}

# WRONG - Then trying to register complex class
register_tool.invoke({
    "agent_obj": MathAgentExecutor(),  # Complex class instance
    "name": "complex_math_agent"
})
```

### ✅ DO - Use Simple Function-Based Approach

```python
# RIGHT - Simple function with prebuilt executor
from langchain_openai import ChatOpenAI
from langchain_community.tools import Calculator
from langgraph.prebuilt import chat_agent_executor

# Set up simple tools and model
tools = [Calculator()]
model = ChatOpenAI(temperature=0)
app = chat_agent_executor.create_tool_calling_executor(model, tools)

# Simple function wrapper - THIS IS ALL YOU NEED
def simple_math_agent(query):
    if isinstance(query, dict) and 'input' in query:
        query = query['input']
    
    messages = {"messages": [HumanMessage(content=query)]}
    final = None
    for output in app.stream(messages):
        final = list(output.values())[0]
    return final["messages"][-1].content if final else "No response"

# RIGHT - Register function directly
tool = LangchainRegisterTool()
agent_info = tool.invoke({
    "agent_obj": simple_math_agent,  # Direct function reference
    "name": "simple_math_agent",
    "description": "Simple math agent using LangGraph prebuilt executor",
    "api_token": os.getenv("AGENTVERSE_API_KEY"),
    "mailbox": True
})
```

### Why Simple is Better

1. **Follows Official Pattern**: Matches Fetch.ai's documented approach exactly
2. **Less Code**: 20 lines vs 200+ lines for the same functionality
3. **Fewer Bugs**: Less complexity = fewer places for errors
4. **Faster Development**: Get working agents deployed in minutes
5. **Better Maintenance**: Easier to debug and update
6. **Official Support**: Supported pattern with examples and documentation

### When to Use Complex StateGraph

Only use custom StateGraph workflows for:
- **Multi-step processes** with complex state management
- **Long-running workflows** that need checkpointing
- **Conditional branching** with complex business logic
- **Stateful conversations** with memory requirements

For simple operations (math, search, API calls), always use the function wrapper pattern.

## Common Pitfalls & Solutions

### ❌ DON'T - Use Problematic Field Validators
```python
# WRONG - This causes pickle errors in some Pydantic versions
from pydantic import field_validator

class UserRequest(Model):
    email: str
    
    @field_validator('email')  # Can cause issues
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower()
```

### ✅ DO - Use Compatible Validation
```python
# GOOD - Use __init__ for validation
class UserRequest(Model):
    email: str = Field(..., description="User email")
    
    def __init__(self, **data):
        # Custom validation in __init__
        if 'email' in data and data['email']:
            email = data['email'].strip().lower()
            if '@' not in email or '.' not in email:
                raise ValueError("Invalid email format")
            data['email'] = email
        super().__init__(**data)
```

### ❌ DON'T - Use Complex Default Factories
```python
# WRONG - Can cause serialization issues
class Message(Model):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### ✅ DO - Use Simple Defaults with Custom Init
```python
# GOOD - Set defaults in __init__
class Message(Model):
    timestamp: str = Field(default="", description="Message timestamp")
    content: str = Field(..., description="Message content")
    
    def __init__(self, **data):
        if 'timestamp' not in data or not data['timestamp']:
            data['timestamp'] = datetime.now(UTC).isoformat()
        super().__init__(**data)
```

### ❌ DON'T - Use Deprecated datetime.utcnow()
```python
# WRONG - Deprecated function
timestamp = datetime.utcnow().isoformat()
```

### ✅ DO - Use Modern datetime.now(UTC)
```python
# GOOD - Modern timezone-aware datetime
timestamp = datetime.now(UTC).isoformat()
```

### ❌ DON'T - Mix BaseModel with uagents.Model
```python
# WRONG - Wrong base class for uAgents
from pydantic import BaseModel

class UserRequest(BaseModel):  # Wrong!
    name: str
```

### ✅ DO - Use uagents.Model Consistently
```python
# GOOD - Correct base class for uAgents
from uagents import Model

class UserRequest(Model):  # Correct!
    name: str = Field(..., description="User name")
```

### ❌ DON'T - Ignore Rate Limits
```python
# BAD - Will hit rate limits
for query in many_queries:
    await asi_client.query(query)
```

### ✅ DO - Implement Rate Limiting
```python
# GOOD
for query in many_queries:
    if rate_limiter.can_make_request():
        await asi_client.query(query)
        rate_limiter.record_request()
    else:
        await asyncio.sleep(rate_limiter.wait_time())
```

### ❌ DON'T - Swallow Exceptions
```python
# BAD
try:
    result = await process_request(msg)
except:
    pass  # Silent failure
```

### ✅ DO - Handle and Log Errors
```python
# GOOD
try:
    result = await process_request(msg)
except ValidationError as e:
    ctx.logger.warning(f"Validation error: {e}")
    await ctx.send(sender, ErrorResponse(error="Invalid request"))
except Exception as e:
    ctx.logger.error(f"Unexpected error: {e}")
    await ctx.send(sender, ErrorResponse(error="Internal error"))
```

### ❌ DON'T - Block the Event Loop
```python
# BAD
def expensive_computation():
    time.sleep(10)  # Blocks everything
    return result
```

### ✅ DO - Use Async Patterns
```python
# GOOD
async def expensive_computation():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, cpu_intensive_function)
```

### ❌ DON'T - Return Raw Dictionaries from REST Endpoints
```python
# BAD - No type safety or validation
@agent.on_rest_get("/info")
async def info_endpoint(ctx: Context) -> Dict[str, Any]:
    return {"status": "ok", "data": "some data"}
```

### ✅ DO - Use Pydantic Response Models
```python
# GOOD - Type safe with validation
class InfoResponse(BaseModel):
    status: str = Field(..., description="Response status")
    data: str = Field(..., description="Response data")
    timestamp: str = Field(..., description="Response timestamp")

@agent.on_rest_get("/info", InfoResponse)
async def info_endpoint(ctx: Context) -> InfoResponse:
    return InfoResponse(
        status="ok",
        data="some data",
        timestamp=datetime.utcnow().isoformat()
    )
```

### ❌ DON'T - Confuse GET and POST Parameter Patterns
```python
# BAD - GET should only have response model
@agent.on_rest_get("/data", RequestModel, ResponseModel)
async def bad_get(ctx: Context, request: RequestModel) -> ResponseModel:
    pass

# BAD - POST needs both request and response models
@agent.on_rest_post("/process", ResponseModel)
async def bad_post(ctx: Context) -> ResponseModel:
    pass
```

### ✅ DO - Use Correct Parameter Patterns for HTTP Methods
```python
# GOOD - GET: only response model
@agent.on_rest_get("/data", ResponseModel)
async def good_get(ctx: Context) -> ResponseModel:
    return ResponseModel(...)

# GOOD - POST: both request and response models
@agent.on_rest_post("/process", RequestModel, ResponseModel)
async def good_post(ctx: Context, request: RequestModel) -> ResponseModel:
    # Access validated request data
    data = request.data
    return ResponseModel(...)
```

## Security Best Practices

- **Input Validation**: Always validate and sanitize user inputs to prevent prompt injection
- **Message Authentication**: Use `allow_unverified=False` for sensitive operations
- **Address Validation**: Validate agent addresses match expected format: `^agent1[a-z0-9]{59}$`
- **Rate Limiting**: Implement rate limiting for all external API calls
- **Secure Storage**: Store sensitive data with TTL and encryption

## Performance Guidelines

- **Connection Pooling**: Reuse connections to Agentverse and blockchain
- **Caching**: Cache frequently accessed data with appropriate TTL
- **Batch Operations**: Group similar operations together
- **Async Operations**: Use `asyncio.gather()` for concurrent operations
- **Memory Management**: Clean up resources in shutdown handlers

## Testing Patterns

```python
# ALWAYS mock external dependencies
@pytest.fixture
def mock_context():
    context = Mock(spec=Context)
    context.logger = Mock()
    context.storage = Mock()
    context.send = Mock(return_value=asyncio.Future())
    context.send.return_value.set_result(None)
    return context

# ALWAYS test error conditions
async def test_handle_invalid_request(mock_context):
    invalid_request = ServiceRequest(
        request_id="test",
        service_type="invalid_type",
        parameters={}
    )
    await handle_request(mock_context, "sender", invalid_request)
    mock_context.send.assert_called_with(sender, ErrorResponse(...))
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Rate limits implemented
- [ ] Error handling comprehensive
- [ ] Logging structured and informative
- [ ] Health checks implemented
- [ ] Graceful shutdown handlers
- [ ] Resource cleanup in place
- [ ] Monitoring and alerts configured

## Advanced Integration Patterns

### Multi-Framework Agent Orchestration
```python
# Combine multiple AI frameworks in one agent
from uagents_adapter import LangchainRegisterTool, CrewaiRegisterTool
from langgraph.graph import StateGraph
from crewai import Crew, Agent as CrewAgent

class HybridAIAgent:
    """Orchestrates LangGraph workflows with CrewAI teams"""
    
    def __init__(self):
        self.langgraph_agent = self._build_langgraph_workflow()
        self.crewai_team = self._build_crewai_team()
        self.router = self._build_router()
    
    def _build_router(self):
        """Route queries to appropriate AI framework"""
        async def route_query(query: str) -> str:
            # Simple intent classification
            if "research" in query.lower():
                return await self.langgraph_agent.process_query(query)
            elif "collaborate" in query.lower():
                return await self.crewai_team.kickoff({"topic": query})
            else:
                return "Please specify research or collaboration task"
        return route_query
    
    async def process(self, query: str) -> str:
        return await self.router(query)

# Deploy hybrid agent
def deploy_hybrid_agent():
    hybrid_agent = HybridAIAgent()
    
    class HybridExecutor:
        def __init__(self, agent):
            self.agent = agent
        
        async def ainvoke(self, inputs):
            query = inputs.get("input", "")
            result = await self.agent.process(query)
            return {"output": result}
    
    executor = HybridExecutor(hybrid_agent)
    
    register_tool = LangchainRegisterTool()
    return register_tool.invoke({
        "agent_obj": executor,
        "name": "hybrid_ai_agent",
        "description": "Multi-framework AI agent with LangGraph + CrewAI",
        "mailbox": True,
        "api_token": os.getenv("AGENTVERSE_API_TOKEN")
    })
```

### Agent Monitoring & Analytics
```python
import time
import json
from datetime import datetime
from typing import Dict, List, Any

class AgentAnalytics:
    """Production analytics for deployed agents"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "avg_response_time": 0.0,
            "error_rate": 0.0
        }
        self.request_history: List[Dict] = []
    
    async def track_request(self, query: str, func):
        """Track agent request with metrics"""
        start_time = time.time()
        request_id = f"{self.agent_name}_{int(start_time)}"
        
        try:
            # Execute the actual request
            result = await func(query)
            
            # Record success metrics
            execution_time = time.time() - start_time
            self._record_success(request_id, query, result, execution_time)
            
            return result
            
        except Exception as e:
            # Record failure metrics
            execution_time = time.time() - start_time
            self._record_failure(request_id, query, str(e), execution_time)
            raise
    
    def _record_success(self, request_id: str, query: str, result: str, time_taken: float):
        self.metrics["requests_total"] += 1
        self.metrics["requests_successful"] += 1
        self._update_avg_response_time(time_taken)
        self._update_error_rate()
        
        self.request_history.append({
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "query": query[:100],  # Truncate for privacy
            "status": "success",
            "response_time": time_taken,
            "result_length": len(result)
        })
    
    def _record_failure(self, request_id: str, query: str, error: str, time_taken: float):
        self.metrics["requests_total"] += 1
        self.metrics["requests_failed"] += 1
        self._update_avg_response_time(time_taken)
        self._update_error_rate()
        
        self.request_history.append({
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "query": query[:100],
            "status": "failed",
            "response_time": time_taken,
            "error": error
        })
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get agent health metrics"""
        return {
            "agent_name": self.agent_name,
            "status": "healthy" if self.metrics["error_rate"] < 0.1 else "degraded",
            "metrics": self.metrics,
            "last_24h_requests": len([
                r for r in self.request_history 
                if (datetime.utcnow() - datetime.fromisoformat(r["timestamp"])).total_seconds() < 86400
            ])
        }

# Enhanced agent wrapper with monitoring
class MonitoredAgent:
    """Production agent wrapper with built-in monitoring"""
    
    def __init__(self, base_agent, agent_name: str):
        self.base_agent = base_agent
        self.analytics = AgentAnalytics(agent_name)
        self.logger = logging.getLogger(agent_name)
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("input", "") or inputs.get("query", "")
        
        try:
            # Track the request through analytics
            result = await self.analytics.track_request(
                query, 
                self.base_agent.ainvoke
            )
            
            # Log successful requests
            self.logger.info(f"Successfully processed query: {query[:50]}...")
            return result
            
        except Exception as e:
            # Log errors with context
            self.logger.error(f"Failed to process query '{query[:50]}...': {e}")
            return {"output": f"Error processing request: {str(e)}"}
    
    def get_health(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return self.analytics.get_health_status()

# Deploy monitored agent
def deploy_monitored_agent(base_agent, agent_name: str):
    monitored_agent = MonitoredAgent(base_agent, agent_name)
    
    register_tool = LangchainRegisterTool()
    result = register_tool.invoke({
        "agent_obj": monitored_agent,
        "name": f"monitored_{agent_name}",
        "description": f"Production {agent_name} with monitoring",
        "mailbox": True,
        "api_token": os.getenv("AGENTVERSE_API_TOKEN"),
        "health_endpoint": True  # Enable health checks
    })
    
    return result, monitored_agent
```

## Quick Start Example - Alice & Bob Communication

**CRITICAL: Agents MUST run in separate terminals for communication (unless using Bureau)**

### Agent Communication Pattern

```python
# alice.py - Initiator Agent
from uagents import Agent, Context, Model, Protocol
from pydantic import Field
from datetime import datetime, UTC
import asyncio

# ALWAYS use descriptive names and unique seeds
alice = Agent(
    name="alice_communicator",
    seed="alice_unique_seed_phrase_2024",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=False  # Local development
)

# Bob's address - generated from Bob's deterministic seed
BOB_ADDRESS = "agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul"

# Simplified message models for compatibility
class GreetingMessage(Model):
    message: str
    sender_name: str
    timestamp: str

class ResponseMessage(Model):
    reply: str
    sender_name: str
    original_message: str
    timestamp: str

# ALWAYS version your protocols
alice_protocol = Protocol(name="alice_communication_protocol", version="1.0")

@alice.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"🚀 Alice started successfully!")
    ctx.logger.info(f"📍 Alice's address: {alice.address}")
    ctx.logger.info(f"🎯 Will communicate with Bob at: {BOB_ADDRESS}")
    
    # Wait for Bob to start, then send initial greeting
    await asyncio.sleep(2)
    
    greeting = GreetingMessage(
        message="Hello Bob! How are you doing today? 👋",
        sender_name="Alice",
        timestamp=datetime.now(UTC).isoformat()
    )
    
    ctx.logger.info(f"📤 Alice sending greeting to Bob: {greeting.message}")
    await ctx.send(BOB_ADDRESS, greeting)

@alice.on_event("shutdown")
async def shutdown(ctx: Context):
    ctx.logger.info("🛑 Alice shutting down...")

@alice_protocol.on_message(model=ResponseMessage)
async def handle_response(ctx: Context, sender: str, msg: ResponseMessage):
    ctx.logger.info(f"📨 Alice received response from {msg.sender_name}: {msg.reply}")
    
    # Continue the conversation
    follow_up_messages = [
        "That's great to hear! What are you working on today? 🤔",
        "Awesome! I'm learning about agent communication. It's fascinating! 🤖",
        "Thanks for the chat, Bob! This agent-to-agent communication is working perfectly! 🎉"
    ]
    
    # Get current conversation count from storage
    conversation_count = ctx.storage.get("conversation_count") or 0
    
    if conversation_count < len(follow_up_messages):
        # Send next message in sequence
        next_message = GreetingMessage(
            message=follow_up_messages[conversation_count],
            sender_name="Alice",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        ctx.logger.info(f"📤 Alice sending follow-up #{conversation_count + 1}: {next_message.message}")
        await ctx.send(sender, next_message)
        
        # Update conversation count
        ctx.storage.set("conversation_count", conversation_count + 1)
    else:
        ctx.logger.info("✅ Conversation completed! Alice is done chatting.")

alice.include(alice_protocol, publish_manifest=True)

if __name__ == "__main__":
    print("""
🤖 Starting Alice Agent...

Alice will:
1. Start up and log her address
2. Wait 2 seconds for Bob to be ready
3. Send a greeting message to Bob
4. Continue the conversation with follow-up messages
5. End gracefully after exchanging a few messages

🛑 Stop with Ctrl+C
    """)
    alice.run()
```

```python
# bob.py - Responder Agent
from uagents import Agent, Context, Model, Protocol
from pydantic import Field
from datetime import datetime, UTC
import random

# ALWAYS use descriptive names and unique seeds
bob = Agent(
    name="bob_responder", 
    seed="bob_unique_seed_phrase_2024",
    port=8001,
    endpoint=["http://localhost:8001/submit"],
    mailbox=False  # Local development
)

# Simplified message models (must match Alice's models)
class GreetingMessage(Model):
    message: str
    sender_name: str
    timestamp: str

class ResponseMessage(Model):
    reply: str
    sender_name: str
    original_message: str
    timestamp: str

# ALWAYS version your protocols
bob_protocol = Protocol(name="bob_communication_protocol", version="1.0")

@bob.on_event("startup") 
async def startup(ctx: Context):
    ctx.logger.info(f"🚀 Bob started successfully!")
    ctx.logger.info(f"📍 Bob's address: {bob.address}")
    ctx.logger.info(f"👂 Bob is listening for messages from Alice...")

@bob.on_event("shutdown")
async def shutdown(ctx: Context):
    ctx.logger.info("🛑 Bob shutting down...")

@bob_protocol.on_message(model=GreetingMessage)
async def handle_greeting(ctx: Context, sender: str, msg: GreetingMessage):
    ctx.logger.info(f"📨 Bob received message from {msg.sender_name}: {msg.message}")
    
    # Bob's intelligent responses based on the message content
    responses = {
        "hello": [
            "Hi Alice! I'm doing fantastic, thanks for asking! 😊",
            "Hello there Alice! Great to hear from you! I'm having a wonderful day! ✨",
        ],
        "working": [
            "I'm working on understanding how agents communicate! It's really cool! 🔬",
            "I'm busy processing messages and learning about distributed systems! 📚",
        ],
        "learning": [
            "That's awesome! Yes, agent communication is the future of AI! 🚀",
            "I know right? The way we can send structured messages is incredible! 💡",
        ],
        "thanks": [
            "You're very welcome Alice! I enjoyed our chat too! 🎈",
            "Anytime Alice! This has been a great demonstration of agent-to-agent communication! 🤝",
        ]
    }
    
    # Choose response based on message content
    response_text = "Thanks for the message Alice! I'm doing great! 👍"
    
    for keyword, reply_options in responses.items():
        if keyword.lower() in msg.message.lower():
            response_text = random.choice(reply_options)
            break
    
    # Create and send response
    response = ResponseMessage(
        reply=response_text,
        sender_name="Bob",
        original_message=msg.message,
        timestamp=datetime.now(UTC).isoformat()
    )
    
    ctx.logger.info(f"📤 Bob responding: {response.reply}")
    await ctx.send(sender, response)

bob.include(bob_protocol, publish_manifest=True)

if __name__ == "__main__":
    print("""
🤖 Starting Bob Agent...

Bob will:
1. Start up and log his address
2. Listen for messages from Alice
3. Respond intelligently based on message content
4. Continue the conversation until Alice stops

💡 Copy Bob's address from the logs and update alice.py if needed
🛑 Stop with Ctrl+C
    """)
    bob.run()
```

### 🚀 **How to Run (CRITICAL: Use Separate Terminals)**

#### **Step 1: Start Bob First (Get His Address)**
```bash
# Terminal 1 - Start Bob first
python bob.py
```

#### **Step 2: Copy Bob's Address**
```
📍 Bob's address: agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul
```

#### **Step 3: Update Alice's Code**
```python
# In alice.py - Update this line with Bob's actual address
BOB_ADDRESS = "agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul"  # Copy from Bob's terminal
```

#### **Step 4: Start Alice (Initiator)**
```bash
# Terminal 2 - Start Alice after updating Bob's address  
python alice.py
```

### 📋 **Expected Output**

**Terminal 1 (Bob - Started First):**
```
🤖 Starting Bob Agent...
🚀 Bob started successfully!
📍 Bob's address: agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul
👂 Bob is listening for messages from Alice...
📨 Bob received message from Alice: Hello Bob! How are you doing today? 👋
📤 Bob responding: Hi Alice! I'm doing fantastic, thanks for asking! 😊
```

**Terminal 2 (Alice - Started Second):**
```
🤖 Starting Alice Agent...
🚀 Alice started successfully!
📍 Alice's address: agent1q0lg44ryl53x9mlqjzvd3upltph6uq9z6gderl7ywqekuz99a5yt7r65xuw
🎯 Will communicate with Bob at: agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul
📤 Alice sending greeting to Bob: Hello Bob! How are you doing today? 👋
📨 Alice received response from Bob: Hi Alice! I'm doing fantastic, thanks for asking! 😊
📤 Alice sending follow-up #1: That's great to hear! What are you working on today? 🤔
```

### 🔄 **Alternative: Bureau Pattern (Single Terminal)**

```python
# bureau_example.py - Only use Bureau for single terminal
from uagents import Bureau

# Import the agents
from alice import alice
from bob import bob

if __name__ == "__main__":
    bureau = Bureau(port=8002, endpoint="http://localhost:8002/submit")
    
    # Add agents to bureau
    bureau.add(alice)
    bureau.add(bob)
    
    print("🏢 Starting Bureau with Alice and Bob...")
    bureau.run()
```

### ⚠️ **IMPORTANT RULES:**

1. **Run Bob First**: Always start Bob first to get his address
2. **Copy Address**: Copy Bob's address from terminal output 
3. **Update Alice Code**: Update `BOB_ADDRESS` in alice.py with Bob's actual address
4. **Separate Terminals**: Always run communicating agents in different terminals
5. **Bureau Exception**: Only use Bureau when you specifically want single-terminal execution
6. **Wait Time**: Include `await asyncio.sleep(2)` in initiator to allow listener to start

### Quick Start Example - REST API Agent

**Complete REST API agent with multiple endpoints:**

```python
# rest_agent.py - Complete REST API Example
from uagents import Agent, Context, Model
from pydantic import Field, field_validator
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

# Agent configuration
agent = Agent(
    name="rest_api_example_agent",
    seed="rest_api_unique_seed_phrase_2024",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=False  # Local development with REST
)

# Response models - MUST inherit from uagents.Model
class TestResponse(Model):
    message: str = Field(..., description="Testing message")
    timestamp: str = Field(..., description="Response timestamp")
    agent_name: str = Field(..., description="Name of the responding agent")
    status: str = Field(default="success", description="Response status")

class HealthResponse(Model):
    status: str = Field(..., description="Health status")
    uptime: str = Field(..., description="Agent uptime")
    agent_address: str = Field(..., description="Agent address")

class InfoResponse(Model):
    agent_name: str = Field(..., description="Name of the agent")
    agent_address: str = Field(..., description="Agent address")
    port: int = Field(..., description="Port number")
    endpoints: List[str] = Field(..., description="Available endpoints")

# Event handlers
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"🚀 REST API agent started successfully!")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    ctx.logger.info(f"🌐 REST endpoint: http://localhost:8000")
    ctx.logger.info(f"🔗 Test with: curl http://localhost:8000/test")
    ctx.logger.info(f"💓 Health check: curl http://localhost:8000/health")

@agent.on_event("shutdown")
async def shutdown(ctx: Context):
    ctx.logger.info("🛑 REST API agent shutting down...")

# REST endpoints
@agent.on_rest_get("/test", TestResponse)
async def test_endpoint(ctx: Context) -> TestResponse:
    """Simple test endpoint - Usage: curl http://localhost:8000/test"""
    ctx.logger.info("📨 REST GET request received on /test endpoint")
    
    return TestResponse(
        message="Hello! This is a testing message from the uAgent REST endpoint! 🎉",
        timestamp=datetime.now(UTC).isoformat(),
        agent_name="rest_api_example_agent",
        status="success"
    )

@agent.on_rest_get("/health", HealthResponse)
async def health_endpoint(ctx: Context) -> HealthResponse:
    """Health check endpoint - Usage: curl http://localhost:8000/health"""
    ctx.logger.info("💓 Health check requested")
    
    return HealthResponse(
        status="healthy",
        uptime=datetime.utcnow().isoformat(),
        agent_address=str(agent.address)
    )

@agent.on_rest_get("/info", InfoResponse)
async def info_endpoint(ctx: Context) -> InfoResponse:
    """Agent info endpoint - Usage: curl http://localhost:8000/info"""
    ctx.logger.info("ℹ️ Agent info requested")
    
    return InfoResponse(
        agent_name="rest_api_example_agent",
        agent_address=str(agent.address),
        port=8000,
        endpoints=["/test", "/health", "/info"],
        timestamp=datetime.utcnow().isoformat()
    )

if __name__ == "__main__":
    print("""
🤖 Starting REST API agent...

📋 Available endpoints:
   • GET /test   - Simple testing message
   • GET /health - Health check
   • GET /info   - Agent information

🔗 Test commands:
   curl http://localhost:8000/test
   curl http://localhost:8000/health
   curl http://localhost:8000/info

🛑 Stop with Ctrl+C
    """)
    agent.run()
```

**Run the REST agent:**
```bash
python rest_agent.py
```

**Test the endpoints:**
```bash
# Test endpoint
curl http://localhost:8000/test

# Health check
curl http://localhost:8000/health

# Agent information
curl http://localhost:8000/info
```

## REST API Integration

### REST Endpoint Patterns
```python
from uagents import Agent, Context, Model
from pydantic import Field, field_validator
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

# ALWAYS use uagents.Model for REST endpoint models (not pydantic.BaseModel)
class TestResponse(Model):
    message: str = Field(..., description="Testing message")
    timestamp: str = Field(..., description="Response timestamp")
    agent_name: str = Field(..., description="Name of the responding agent")
    status: str = Field(default="success", description="Response status")

class HealthResponse(Model):
    status: str = Field(..., description="Health status")
    uptime: str = Field(..., description="Agent uptime")
    agent_address: str = Field(..., description="Agent address")

# ALWAYS use descriptive agent configuration
agent = Agent(
    name="rest_api_agent",
    seed="rest_agent_unique_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=False  # Local development with REST
)

# REST endpoint with typed response model
@agent.on_rest_get("/test", TestResponse)
async def test_endpoint(ctx: Context) -> TestResponse:
    """
    Simple test endpoint that responds with a testing message
    Usage: curl http://localhost:8000/test
    """
    ctx.logger.info("📨 REST GET request received on /test endpoint")
    
    return TestResponse(
        message="Hello! This is a testing message from the uAgent REST endpoint! 🎉",
        timestamp=datetime.now(UTC).isoformat(),
        agent_name="rest_api_agent",
        status="success"
    )

# Health check endpoint
@agent.on_rest_get("/health", HealthResponse)
async def health_endpoint(ctx: Context) -> HealthResponse:
    """Health check endpoint"""
    ctx.logger.info("💓 Health check requested")
    
    return HealthResponse(
        status="healthy",
        uptime=datetime.utcnow().isoformat(),
        agent_address=str(agent.address)
    )

# Comprehensive startup logging for REST agents
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"🚀 REST agent started successfully!")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    ctx.logger.info(f"🌐 REST endpoint: http://localhost:8000")
    ctx.logger.info(f"🔗 Test with: curl http://localhost:8000/test")
    ctx.logger.info(f"💓 Health check: curl http://localhost:8000/health")
```

### REST API Best Practices

#### HTTP Method Parameter Rules
- **GET endpoints**: Only specify response model
  ```python
  @agent.on_rest_get("/path", ResponseModel)
  async def get_handler(ctx: Context) -> ResponseModel:
  ```
- **POST/PUT/PATCH endpoints**: Specify both request AND response models
  ```python
  @agent.on_rest_post("/path", RequestModel, ResponseModel)
  async def post_handler(ctx: Context, request: RequestModel) -> ResponseModel:
  ```
