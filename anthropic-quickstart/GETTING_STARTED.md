# 🚀 Getting Started with Claude Agents on Fetch.ai

Welcome! This guide will get you building AI agents with Anthropic Claude in minutes.

## 📋 Prerequisites

Before you start, make sure you have:

- ✅ **Python 3.9 or higher** installed
- ✅ **pip** (Python package manager)
- ✅ **Anthropic API key** ([Get one here](https://console.anthropic.com/settings/keys))
- ✅ **Basic Python knowledge**

### Check Your Python Version

```bash
python --version
# Should show Python 3.9 or higher
```

## 🔑 Step 1: Get Your Anthropic API Key

1. Visit [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Sign up or log in with your account
3. Click **"Create Key"**
4. Give it a name (e.g., "Fetch.ai Agent")
5. Copy the key (starts with `sk-ant-api03-`)

**Important:** 
- Keep your API key secret!
- Don't commit it to Git
- Store it in `.env` files only

## 📦 Step 2: Set Up Your Environment

### Option A: Use the Root `.env` File

# Edit the .env file
nano .env  # or use your preferred editor

# Add your Anthropic key:
ANTHROPIC_API_KEY="sk-ant-api03-your-actual-key-here"
```

### Option B: Create a Local `.env` File

For the specific guide you're working on:

```bash
cd anthropic-quickstart/01-basic-claude-agent

# Copy the example
cp .env.example .env

# Edit it
nano .env

# Add your key
ANTHROPIC_API_KEY="sk-ant-api03-your-actual-key-here"
```

## 🏗️ Step 3: Install Dependencies

### Create a Virtual Environment (Recommended)

```bash
cd anthropic-quickstart/01-basic-claude-agent

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### Install Packages

```bash
pip install -r requirements.txt
```

This installs:
- `uagents` - Fetch.ai agent framework
- `anthropic` - Claude API client
- `python-dotenv` - Environment variable management

## ▶️ Step 4: Run Your First Agent

```bash
python basic_claude_agent.py
```

You should see:

```
🤖 Starting Claude Assistant...
📍 Agent address: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
✅ Anthropic Claude API configured
   Using model: claude-3-5-sonnet-20241022

🎯 Agent Features:
   • Conversational AI with Claude 3.5 Sonnet
   • Advanced reasoning and analysis
   • Context-aware responses
   • Conversation history tracking
   • Ready for Agentverse deployment

✅ Agent is running! Connect via ASI One or send messages programmatically.
   Press Ctrl+C to stop.
```

**🎉 Congratulations!** Your Claude agent is running!

## 💬 Step 5: Test Your Agent

### Via ASI One (Web Interface)

1. Keep your agent running
2. Open [https://asi1.ai](https://asi1.ai) in your browser
3. Copy your agent address from the terminal
4. Paste it in ASI One search
5. Start chatting!

**Test prompts:**

```
Hello! What can you do?
```

```
Explain how AI agents work
```

```
Write a short poem about autonomous agents
```

```
What's the difference between you and other AI models?
```

## 🎯 What's Happening?

When you send a message:

1. **User → ASI One**: You type a message in the web interface
2. **ASI One → Agent**: Message is sent via Fetch.ai protocol
3. **Agent → Claude API**: Your agent forwards it to Claude
4. **Claude → Agent**: Claude generates a response
5. **Agent → ASI One**: Response is sent back through the protocol
6. **ASI One → User**: You see Claude's answer!

## 📊 Understanding the Output

### Terminal Logs

```
📨 Message from agent1q...xyz: Hello! What can you do?
🤔 Generating response with Claude...
✅ Response generated: I'm a helpful AI assistant...
💬 Response sent to agent1q...xyz
```

- **📨** = Received message
- **🤔** = Processing with Claude
- **✅** = Response ready
- **💬** = Sent back to user

## 🛠️ Troubleshooting

### "ANTHROPIC_API_KEY not found"

**Problem:** The agent can't find your API key.

**Solution:**
```bash
# Check if .env exists
ls -la .env

# Check if key is set
cat .env | grep ANTHROPIC_API_KEY

# Make sure it's properly formatted
ANTHROPIC_API_KEY="sk-ant-api03-..."
# No spaces around the =
```

### "API key is invalid" or "401 Unauthorized"

**Problem:** The API key isn't working.

**Solutions:**
1. Verify the key is correct (copy it again)
2. Check it's active at [console.anthropic.com](https://console.anthropic.com)
3. Make sure you have available credits
4. Key should start with `sk-ant-api03-`

### "Rate limit exceeded" or "429 Error"

**Problem:** Too many requests.

**Solution:**
- Wait 60 seconds
- Check your usage in Anthropic Console
- Consider upgrading your plan

### Agent starts but doesn't respond

**Check:**
1. Agent is still running (no errors in terminal)
2. You're using the correct agent address
3. Internet connection is stable
4. Anthropic API is operational ([status page](https://status.anthropic.com))

### "Module not found" errors

**Problem:** Dependencies not installed.

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt



## 🎓 Next Steps

### 1. Experiment with Prompts
Try different types of queries:
- Questions: "What is quantum computing?"
- Creative: "Write a story about an AI agent"
- Analysis: "Explain the pros and cons of electric cars"
- Code: "Explain this Python code: [paste code]"

### 2. Customize the System Prompt
Edit `SYSTEM_PROMPT` in `basic_claude_agent.py`:

```python
SYSTEM_PROMPT = """You are a Python coding tutor.

Help users learn Python by:
- Explaining concepts clearly
- Providing code examples
- Suggesting exercises
- Being encouraging and patient"""
```

### 3. Adjust Parameters
In `basic_claude_agent.py`:

```python
# More creative (good for writing)
TEMPERATURE = 0.9

# More focused (good for factual)
TEMPERATURE = 0.3

# Longer responses
MAX_TOKENS = 2048
```

### 4. Try Different Models

```python
# Fastest, cheapest
MODEL_NAME = 'claude-3-haiku-20240307'

# Most capable (slower, pricier)
MODEL_NAME = 'claude-3-opus-20240229'

# Best balance (default)
MODEL_NAME = 'claude-3-5-sonnet-20241022'
```

### 5. Deploy to Agentverse
Make your agent publicly accessible 24/7!

*(Deployment guide coming in advanced tutorials)*

## 📚 Learning Resources

### Anthropic Resources
- [Claude API Docs](https://docs.anthropic.com)
- [Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [Best Practices](https://docs.anthropic.com/claude/docs/best-practices)

### Fetch.ai Resources
- [uAgents Documentation](https://fetch.ai/docs/guides/agents/introduction)
- [ASI One Platform](https://asi.one)
- [Fetch.ai Discord](https://discord.gg/fetchai)

### This Quickstart
- [Guide 01: Basic Agent](./01-basic-claude-agent/README.md) ← You are here!
- Guide 02: Vision Agent (Coming Soon)
- Guide 03: Function Calling (Coming Soon)

## 🤝 Need Help?

- 💬 [Fetch.ai Discord](https://discord.gg/fetchai)
- 📖 [Anthropic Support](https://support.anthropic.com)
- 🐛 Open an issue in this repo
- 📧 Check the Anthropic/Fetch.ai documentation

## ✅ Quick Reference

### Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the agent
python basic_claude_agent.py

# Check logs (if agent crashes)
# Errors will show in the terminal

# Stop the agent
Ctrl+C
```

### File Structure

```
anthropic-quickstart/
├── 01-basic-claude-agent/
│   ├── basic_claude_agent.py  ← Main agent code
│   ├── requirements.txt       ← Dependencies
│   ├── .env                   ← Your API key (create this)
│   ├── .env.example           ← Template
│   ├── .gitignore            ← Git exclusions
│   └── README.md             ← Full guide
├── README.md                  ← Overview
└── GETTING_STARTED.md         ← This file!
```

## 🎉 You're Ready!

You now have:
- ✅ Claude API configured
- ✅ Agent running locally
- ✅ Tested basic conversations
- ✅ Understanding of how it works

**Next:** Explore the [full README](./01-basic-claude-agent/README.md) for advanced features!

---

**Happy building! 🚀** Questions? Join the [Fetch.ai Discord](https://discord.gg/fetchai)!
