# Multi-Agent Setup Guide

Step-by-step guide to get your 3-agent system running! 🚀

## Overview

You'll run **3 agents in 3 separate terminals**:

```
Terminal 1: Vision Agent (port 8002)
Terminal 2: MCP Agent (port 8004)
Terminal 3: Router Agent (port 8005) ← This is what users connect to
```

## Step-by-Step Setup

### 1. Open 3 Terminal Windows

Open 3 terminal windows/tabs side-by-side so you can monitor all agents.

### 2. Terminal 1 - Start Vision Agent

```bash
cd /Users/radhikadanda/caltrain/anthropic-quickstart/02-claude-vision-agent
python claude_vision_agent.py
```

**Wait for:**
```
✅ Claude Vision API configured
📍 Agent address: agent1qv7cf6qk25dej5vztevnd3mw5m06xhdxq58ql68lc22drt5wggq9wqxawpp
✅ Agent is running!
```

**Copy the agent address!** You'll need it in step 4.

### 3. Terminal 2 - Start MCP Agent

```bash
cd /Users/radhikadanda/caltrain/anthropic-quickstart/04-mcp-agent
python claude_mcp_agent.py
```

**Wait for:**
```
✅ Connected to MCP server: github
✅ Connected to MCP server: airbnb
📍 Agent address: agent1q0ed0f5czkrn7rdkndcjpkh2rf045nt4mmpc5mfnjlq2gtagq4tyv4cplwd
✅ Loaded 28 MCP tools
```

**Copy the agent address!** You'll need it in step 4.

### 4. Update Router Configuration

Open `router_agent.py` in your editor and update lines 53-54:

```python
# BEFORE (default placeholders)
VISION_AGENT_ADDRESS = "agent1qv7cf6qk25dej5vztevnd3mw5m06xhdxq58ql68lc22drt5wggq9wqxawpp"
MCP_AGENT_ADDRESS = "agent1q0ed0f5czkrn7rdkndcjpkh2rf045nt4mmpc5mfnjlq2gtagq4tyv4cplwd"

# AFTER (your actual addresses from step 2 & 3)
VISION_AGENT_ADDRESS = "agent1q..."  # ← Paste from Terminal 1
MCP_AGENT_ADDRESS = "agent1q..."     # ← Paste from Terminal 2
```

**Save the file!**

### 5. Terminal 3 - Start Router Agent

```bash
cd /Users/radhikadanda/caltrain/anthropic-quickstart/05-multi-agent-simple
python router_agent.py
```

**You should see:**
```
🔀 Starting Router Agent...
📍 Router address: agent1q...
👁️  Vision Agent: agent1qv7cf6...
🔧 MCP Agent: agent1q0ed0f5...
✅ Router is running on port 8005
```

### 6. Test It!

Go to [asi.one](https://asi.one) and connect to the **Router Agent** using its address (from Terminal 3).

## Test Queries

### Test 1: Route to MCP Agent

```
Search for Python machine learning repositories on GitHub
```

**Watch the logs:**
- **Router Terminal**: "🔀 Routing to: mcp agent"
- **MCP Terminal**: "📨 Message from router..."
- **Router Terminal**: "✅ Request completed!"

### Test 2: Route to Vision Agent

```
Describe this image in detail
[Upload an image]
```

**Watch the logs:**
- **Router Terminal**: "🔀 Routing to: vision agent"
- **Vision Terminal**: "📨 Message from router..."
- **Router Terminal**: "✅ Request completed!"

### Test 3: More Examples

```
Find Airbnb near Sunnyvale for 2 nights
→ Routes to MCP

What's in this screenshot?
[Upload image]
→ Routes to Vision

Get trending AI repositories from GitHub
→ Routes to MCP
```

## Terminal Layout

Arrange your terminals like this for easy monitoring:

```
┌─────────────────────┬─────────────────────┐
│   Terminal 1        │   Terminal 2        │
│   Vision Agent      │   MCP Agent         │
│   (port 8002)       │   (port 8004)       │
│                     │                     │
│ Vision logs...      │ MCP logs...         │
└─────────────────────┴─────────────────────┘
┌───────────────────────────────────────────┐
│   Terminal 3                              │
│   Router Agent (port 8005)                │
│                                           │
│   Router logs...                          │
└───────────────────────────────────────────┘
```

## Troubleshooting

### Issue: "Failed to connect to agent"

**Solution:**
- Check all 3 agents are running
- Verify agent addresses in `router_agent.py` are correct
- Make sure ports 8002, 8004, 8005 are not in use

### Issue: "Request goes to wrong agent"

**Solution:**
- Check the classification logic
- Try more explicit queries
- Look at router logs to see classification decision

### Issue: "Agent address changed"

**Solution:**
- Copy new address from Vision/MCP terminal
- Update `router_agent.py`
- Restart Router agent (Ctrl+C, then run again)

### Issue: "No response from specialist"

**Check:**
- Is the specialist agent still running?
- Check its terminal for errors
- Verify message was sent (check router logs)

## Quick Restart

If you need to restart everything:

```bash
# Terminal 1
cd ../02-claude-vision-agent && python claude_vision_agent.py

# Terminal 2
cd ../04-mcp-agent && python claude_mcp_agent.py

# Terminal 3
cd ../05-multi-agent-simple && python router_agent.py
```

## Monitoring Tips

### Watch the Message Flow

When you send a request, watch all 3 terminals in order:

1. **Router** receives from user
2. **Router** classifies and routes
3. **Specialist** (Vision or MCP) processes
4. **Specialist** sends response
5. **Router** forwards to user

### Enable Debug Logging

For more detailed logs, you can add:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

Once you have it working:

1. ✅ Try different types of queries
2. ✅ Watch the routing decisions
3. ✅ Monitor response times
4. ✅ Test edge cases
5. ✅ Consider adding more agents!

---

**Happy multi-agent testing!** 🤖✨
