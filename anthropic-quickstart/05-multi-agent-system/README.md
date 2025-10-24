# Simple Multi-Agent System

Your first multi-agent system! 3 agents working together to handle different tasks. 🤖🤖🤖

## What You'll Build

A system with **3 cooperating agents:**

1. **Router Agent** (port 8005) - Receives user requests, routes to specialists
2. **Vision Agent** (port 8002) - Handles images and visual tasks
3. **MCP Agent** (port 8004) - Handles GitHub, Airbnb, and tool usage

## Architecture

```
User (ASI One)
    ↓
    ↓ "Analyze this image" or "Search GitHub"
    ↓
Router Agent 🔀
    ├─ Uses Claude to classify request
    ├─ Decides: Vision or MCP?
    │
    ├─→ Vision Agent 👁️
    │   (if request involves images)
    │   → Analyzes image
    │   → Sends result back to Router
    │
    └─→ MCP Agent 🔧
        (if request involves GitHub/Airbnb/tools)
        → Uses MCP tools
        → Sends result back to Router

Router Agent
    ↓
    ↓ Forwards response
    ↓
User (ASI One)
```

## Quick Start

### Step 1: Ensure Specialized Agents Are Ready

You should have already built these in previous guides:
- ✅ Guide 02: Vision Agent
- ✅ Guide 04: MCP Agent

### Step 2: Start All Agents

You need to run **3 terminal windows**:

**Terminal 1 - Vision Agent:**
```bash
cd ../02-claude-vision-agent
python claude_vision_agent.py
```

**Terminal 2 - MCP Agent:**
```bash
cd ../04-mcp-agent  
python claude_mcp_agent.py
```

**Terminal 3 - Router Agent:**
```bash
cd 05-multi-agent-simple
python router_agent.py
```
### You will see an inspector link, which you can open on your browser and connect the mailbox.

### Step 3: Update Agent Addresses

When you start the Vision and MCP agents, they'll show their addresses:

```
Vision Agent: agent1qv7cf6...
MCP Agent: agent1q0ed0f5...
```

**Copy these addresses** and update them in `router_agent.py`:

```python
# Update these lines (around line 53-54)
VISION_AGENT_ADDRESS = "agent1qv7cf6..."  # ← Paste Vision agent address
MCP_AGENT_ADDRESS = "agent1q0ed0f5..."     # ← Paste MCP agent address
```

Then restart the router agent.

### Step 4: Test via ASI One

Go to [asi1.ai](https://asi1.ai) and find the **Router Agent** using its address.

## Example Queries

### Routes to Vision Agent 👁️

```
Describe this image
[Upload image]
```

```
What objects do you see in this picture?
[Upload image]
```

```
Extract text from this screenshot
[Upload image]
```

### Routes to MCP Agent 🔧

```
Search for Python machine learning repositories on GitHub
```

```
Find Airbnb listings in San Francisco under $150/night
```

```
Get trending LLM repositories from GitHub
```

## How It Works

### 1. User Sends Request to Router

```
User → Router: "Search GitHub for AI projects"
```

### 2. Router Classifies Request

```python
# Router uses Claude to analyze
decision = await analyze_request(user_query)
# decision = "mcp" (not an image request)
```

### 3. Router Forwards to Specialist

```python
# Router sends message to MCP agent
await ctx.send(MCP_AGENT_ADDRESS, original_message)
```

### 4. Specialist Processes and Responds

```python
# MCP agent receives message
# Executes GitHub search
# Sends response back to Router
await ctx.send(router_address, result_message)
```

### 5. Router Forwards to User

```python
# Router receives response from MCP agent
# Forwards back to original user
await ctx.send(original_user, response)
```

## Code Walkthrough

### Router Agent - Request Handler

```python
@chat_proto.on_message(ChatMessage)
async def handle_user_request(ctx: Context, sender: str, msg: ChatMessage):
    # 1. Extract user query
    user_text = extract_text(msg)
    has_image = check_for_images(msg)
    
    # 2. Classify request
    target_agent = await analyze_request(user_text, has_image)
    # Returns: "vision" or "mcp"
    
    # 3. Route to appropriate agent
    if target_agent == "vision":
        await ctx.send(VISION_AGENT_ADDRESS, msg)
    else:
        await ctx.send(MCP_AGENT_ADDRESS, msg)
    
    # 4. Wait for response (handled by response handler)
```

### Router Agent - Response Handler

```python
@chat_proto.on_message(ChatMessage)  
async def handle_agent_response(ctx: Context, sender: str, msg: ChatMessage):
    # Check if this is from a specialized agent
    if sender in [VISION_AGENT_ADDRESS, MCP_AGENT_ADDRESS]:
        # Extract response
        response_text = extract_text(msg)
        
        # Send back to original user
        await ctx.send(original_user, response_text)
```

### Classification Logic

```python
async def analyze_request(query: str, has_image: bool) -> str:
    # If there's an image, definitely use vision
    if has_image:
        return "vision"
    
    # Use Claude to classify text requests
    prompt = """Analyze this request and decide:
    - vision: for image-related questions
    - mcp: for GitHub, Airbnb, tools, databases
    
    User: "{query}"
    """
    
    response = client.messages.create(...)
    return response.text  # "vision" or "mcp"
```

## Message Flow Example

**Request:** "Find Python repos on GitHub"

```
1. User sends to Router
   Router address: agent1q...router...
   
2. Router classifies
   Claude decides: "mcp" (GitHub-related)
   
3. Router → MCP Agent
   MCP address: agent1q...mcp...
   Message: "Find Python repos on GitHub"
   
4. MCP Agent processes
   - Calls search_repositories tool
   - Gets results from GitHub
   
5. MCP Agent → Router
   Message: "Found 100 repos: [list]"
   
6. Router → User
   Final response delivered
```

## Troubleshooting

### "No response from agent"

**Check:**
- All 3 agents are running
- Agent addresses are correct in `router_agent.py`
- Check logs in each terminal

### "Request goes to wrong agent"

**Check:**
- Classification logic in `analyze_request()`
- Try more explicit queries
- Check Claude's classification decision in logs

### Agent addresses changed

**Solution:**
- Restart Vision and MCP agents
- Copy new addresses
- Update `router_agent.py`
- Restart Router agent

## Monitoring

Watch all 3 terminal windows to see the message flow:

**Router Terminal:**
```
📨 Request from user: Search GitHub...
🔀 Routing to: mcp agent
→ Forwarding to mcp agent...
📨 Response received from specialized agent
← Sending response back to user
✅ Request completed!
```

**MCP Terminal:**
```
📨 Message from router: Search GitHub...
🔧 Claude wants to use 1 MCP tool(s)
⚙️  Executing MCP tool: search_repositories
✅ Tool result: Found 100 repositories
💬 Response sent to router
```

## Extending the System

### Add More Specialized Agents

Want to add a 4th agent? Easy!

1. **Create the new agent**
2. **Add its address to router**:
   ```python
   FUNCTION_AGENT_ADDRESS = "agent1q..."
   ```
3. **Update classification**:
   ```python
   # Returns: "vision", "mcp", or "function"
   ```
4. **Add routing logic**:
   ```python
   elif target_agent == "function":
       await ctx.send(FUNCTION_AGENT_ADDRESS, msg)
   ```

### Improve Classification

Make the router smarter:

```python
# Use more sophisticated classification
classification_prompt = """
Available agents and their capabilities:

1. vision: Images, photos, screenshots, OCR, visual analysis
2. mcp: GitHub repos, Airbnb search, databases, file operations  
3. function: Weather, calculations, time, general tools

User request: "{query}"

Respond with the best agent name.
"""
```

### Add Request Tracking

Track requests properly:

```python
pending_requests[request_id] = {
    "original_sender": sender,
    "target_agent": target_agent,
    "timestamp": datetime.now(),
    "status": "pending"
}
```

## Advanced: Multi-Step Workflows

You could extend the router to chain multiple agents:

```python
# Future enhancement
async def handle_complex_request(query):
    # Step 1: Use vision to analyze image
    vision_result = await call_agent(VISION_AGENT, image_query)
    
    # Step 2: Use MCP to search based on vision result
    mcp_query = f"Find repos related to {vision_result}"
    mcp_result = await call_agent(MCP_AGENT, mcp_query)
    
    # Step 3: Combine results
    return combine(vision_result, mcp_result)
```

## Key Takeaways

✅ **Agent Communication** - Agents send messages to each other's addresses

✅ **Simple Routing** - Router classifies and forwards requests

✅ **Specialization** - Each agent handles what it does best

✅ **Scalable** - Easy to add more specialized agents

✅ **Decentralized** - All agents run independently

## What's Next?

- ✅ Test with various queries
- ✅ Monitor message flow
- ✅ Add more specialized agents
- ✅ Implement multi-step workflows
- ✅ Add error handling and retries

---

**You've built a multi-agent system!** 🎉 This is the foundation for complex agentic workflows! 🤖✨
