# Fetch.ai Development Rules for Cursor IDE

## 📚 What is fetchai.mdc?

The `fetchai.mdc` file is a comprehensive set of development rules and best practices specifically designed for building Fetch.ai agents using Cursor IDE. It serves as an intelligent coding assistant that helps developers write correct, efficient, and production-ready uAgent code.

## 🎯 Purpose

This rule file ensures:
- **Consistent Code Quality**: Standardized patterns across all Fetch.ai projects
- **Compatibility**: Exact package versions that work together seamlessly
- **Best Practices**: Official patterns from Fetch.ai Innovation Lab documentation
- **Error Prevention**: Common pitfalls and how to avoid them
- **Production Readiness**: Deployment patterns and monitoring guidelines

## 🚀 Quick Start

### 1. Setup in Cursor IDE

1. **Place the Rule File**: The `fetchai.mdc` file should be in your `.cursor/rules/` directory
2. **Activate Rules**: Cursor automatically detects and applies rules in this directory
3. **Verify**: Check that Cursor recognizes the rules in your project

### 2. Package Installation

The rules specify exact versions for compatibility:

```bash
# Basic uAgent development
pip install uagents==0.22.5

# Full framework integration
pip install uagents==0.22.5 uagents-adapter==0.4.0 langchain==0.3.23 langgraph==0.3.20 crewai==0.126.0 langchain-openai==0.2.14
```

### 3. Start Coding

When you create Python files in your project, Cursor will automatically:
- Suggest proper imports
- Generate compatible code patterns
- Warn about common mistakes
- Reference official documentation

## 🏗️ What's Included

### 📖 Official Documentation Links
- Direct links to Fetch.ai Innovation Lab documentation
- Agent creation, communication, and deployment guides
- Examples for LangGraph, CrewAI, ASI:One integration
- MCP integration patterns

### 🔧 Core Patterns
- **uAgent Creation**: Proper agent initialization with descriptive names and seeds
- **Message Models**: Pydantic-compatible model definitions
- **Protocol Implementation**: Versioned protocols with error handling
- **REST API Integration**: GET/POST endpoint patterns

### 🚀 Framework Integration
- **LangGraph**: Simple function wrapper pattern (official approach)
- **LangChain**: Agent executor integration
- **CrewAI**: Multi-agent collaboration
- **MCP Servers**: Model Context Protocol integration

### 🛡️ Best Practices
- **Pydantic Compatibility**: Avoiding problematic validators and decorators
- **Error Handling**: Comprehensive exception management
- **Security**: Input validation and rate limiting
- **Performance**: Async patterns and memory management

### 🌐 Deployment Patterns
- **Local Agents**: Development and testing
- **Mailbox Agents**: Hybrid local/Agentverse deployment
- **Hosted Agents**: Full Agentverse deployment
- **Production Monitoring**: Analytics and health checks

## 💡 How Cursor Uses These Rules

### Intelligent Code Generation
When you ask Cursor to create agent code, it will:

```python
# ✅ Generate this (correct pattern)
from uagents import Agent, Context, Model, Protocol
from pydantic import Field
from datetime import datetime, UTC

agent = Agent(
    name="descriptive_service_name",
    seed="unique_deterministic_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=True
)

class ServiceRequest(Model):
    request_id: str = Field(..., description="Unique identifier")
    timestamp: str = Field(default="", description="Request timestamp")
    
    def __init__(self, **data):
        if 'timestamp' not in data or not data['timestamp']:
            data['timestamp'] = datetime.now(UTC).isoformat()
        super().__init__(**data)
```

Instead of problematic patterns that cause errors.

### Error Prevention
Cursor will avoid generating code with:
- Deprecated `@field_validator` decorators that cause pickle errors
- Incorrect REST endpoint parameter patterns
- Deprecated `datetime.utcnow()` usage
- Wrong Pydantic base classes

### Documentation Integration
When you ask about Fetch.ai features, Cursor will reference:
- Official Innovation Lab documentation links
- Specific examples and tutorials
- Best practice patterns
- Compatibility requirements

## 🔗 Agent Communication Patterns

### Two-Agent Communication
The rules emphasize the **correct workflow** for agent communication:

```bash
# Step 1: Start Bob first
python bob.py
# Copy Bob's address from output

# Step 2: Update Alice's code with Bob's address
BOB_ADDRESS = "agent1qwj8cuywyt548afedw3mvw4jsklsl4343uhvagwpu0wux3rz2t8a2qtu0ul"

# Step 3: Start Alice
python alice.py
```

**Key Rules:**
- Always run agents in separate terminals (unless using Bureau)
- Start listener first, then initiator
- Copy real addresses, don't use hardcoded ones

### REST API Development
For REST endpoints, the rules specify:

```python
# GET endpoints: only response model
@agent.on_rest_get("/data", ResponseModel)
async def get_handler(ctx: Context) -> ResponseModel:
    return ResponseModel(...)

# POST endpoints: both request and response models
@agent.on_rest_post("/process", RequestModel, ResponseModel)
async def post_handler(ctx: Context, request: RequestModel) -> ResponseModel:
    return ResponseModel(...)
```

## 🎨 LangGraph Integration

### Official Simple Pattern (Recommended)
```python
# ✅ DO: Simple function wrapper
from langgraph.prebuilt import chat_agent_executor
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults

tools = [TavilySearchResults(max_results=3)]
model = ChatOpenAI(temperature=0)
app = chat_agent_executor.create_tool_calling_executor(model, tools)

def langgraph_agent_func(query):
    if isinstance(query, dict) and 'input' in query:
        query = query['input']
    
    messages = {"messages": [HumanMessage(content=query)]}
    final = None
    for output in app.stream(messages):
        final = list(output.values())[0]
    return final["messages"][-1].content if final else "No response"
```

### What NOT to Do
```python
# ❌ DON'T: Complex StateGraph for simple tasks
class ComplexMathAgent:
    def build_graph(self):
        graph = StateGraph(ComplexState)
        graph.add_node("ROUTER", router)
        graph.add_node("PARSE_MATH", parse_math)
        # ... 10+ nodes for simple math operations
```

The rules guide you toward the **official Fetch.ai pattern** that's simpler and more maintainable.

## 🛠️ Common Use Cases

### 1. Creating a Basic Agent
Ask Cursor: *"Create a basic uAgent with startup and shutdown handlers"*

### 2. Agent Communication
Ask Cursor: *"Create two agents that communicate with each other"*
- Cursor will generate proper Alice/Bob pattern with correct terminal workflow

### 3. REST API Agent
Ask Cursor: *"Create an agent with REST endpoints for health check and data processing"*
- Cursor will use proper GET/POST patterns and uagents.Model inheritance

### 4. LangGraph Integration
Ask Cursor: *"Create a LangGraph agent with web search capabilities"*
- Cursor will use the official simple function wrapper pattern

### 5. Production Deployment
Ask Cursor: *"Help me deploy this agent to Agentverse with monitoring"*
- Cursor will include proper error handling, logging, and deployment patterns

## 🔧 Troubleshooting

### Rule Not Working?
1. **Check File Location**: Ensure `fetchai.mdc` is in `.cursor/rules/`
2. **Restart Cursor**: Sometimes rules need to be reloaded
3. **Check Syntax**: Ensure the rule file is properly formatted
4. **Verify Project Type**: Rules apply to Python files (*.py)

### Package Version Conflicts?
The rules specify exact versions that are tested together:
- Use virtual environments to avoid conflicts
- Follow the exact version specifications
- Check the compatibility notes in the rules

### Generated Code Has Errors?
- The rules are designed to prevent common errors
- If you see Pydantic errors, ensure you're using the patterns from the rules
- Check that you're using `uagents.Model` instead of `pydantic.BaseModel`

## 📚 Learning Resources

The rules include direct links to official documentation:

- **[Introduction](https://innovationlab.fetch.ai/resources/docs/intro)**: Start here for Fetch.ai basics
- **[Agent Creation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)**: Core agent development
- **[LangGraph Example](https://innovationlab.fetch.ai/resources/docs/examples/adapters/langgraph-adapter-example)**: Official integration pattern
- **[Agent Communication](https://innovationlab.fetch.ai/resources/docs/agent-communication/uagent-uagent-communication)**: Multi-agent patterns

## 🤝 Contributing

To improve these rules:
1. Test patterns with real Fetch.ai projects
2. Identify common developer issues
3. Reference official documentation updates
4. Submit improvements based on community feedback

## 📄 License

These rules follow Fetch.ai's open-source guidelines and are designed to help developers build better agent applications using official patterns and best practices.

---

**Happy Coding with Fetch.ai and Cursor! 🚀** 
