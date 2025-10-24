# Quick Start: Basic Claude Agent

Build your first AI agent powered by Anthropic Claude on Fetch.ai! 🤖

## What You'll Build

An AI agent that:
- ✅ Responds to conversational queries using Claude 3.5 Sonnet
- ✅ Maintains conversation context and history
- ✅ Provides intelligent, thoughtful responses
- ✅ Works with ASI One chat interface
- ✅ Deploys to Agentverse in minutes

## Why Claude?

**Claude 3.5 Sonnet** is Anthropic's most advanced model, offering:
- 🧠 **Superior Reasoning**: Advanced problem-solving and analysis
- 📚 **Large Context Window**: 200K tokens (handles long conversations)
- 💡 **Thoughtful Responses**: Deep understanding and nuanced answers
- 🔒 **Safety First**: Built-in safety and helpfulness
- ⚡ **Fast & Reliable**: Quick response times with consistent quality

## Prerequisites

- Python 3.9+
- Anthropic API key ([Get one here](https://console.anthropic.com/settings/keys))
- Basic Python knowledge

## Step 1: Install Dependencies

```bash
cd anthropic-quickstart/01-basic-claude-agent

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

## Step 2: Get Your API Key

1. Go to [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Sign up or log in
3. Create a new API key
4. Copy your key

## Step 3: Configure Environment

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your key:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

## Step 4: Run the Agent

```bash
python basic_claude_agent.py
```
### You will see an inspector link, which you can open on your browser and connect the mailbox.

You should see:

```
🤖 Starting Claude Assistant...
📍 Agent address: agent1q...
✅ Anthropic Claude API configured
   Using model: claude-3-5-sonnet-20241022

🎯 Agent Features:
   • Conversational AI with Claude 3.5 Sonnet
   • Advanced reasoning and analysis
   • Context-aware responses
   • Conversation history tracking
   • Ready for Agentverse deployment

✅ Agent is running! Connect via ASI One or send messages programmatically.
```

## Step 5: Test Your Agent

### Option A: Via ASI One (Web Interface)

1. Keep your agent running
2. Go to [https://asi1.ai](https://asi1.ai)
3. Search for your agent address (shown in terminal)
4. Start chatting!

**Try these prompts:**

```
Hello! What can you help me with?
```

```
Explain quantum computing in simple terms
```

```
Write a haiku about AI agents
```

```
Help me brainstorm ideas for a mobile app
```

### Option B: Programmatically (Coming Soon)

We'll add a test client in the next section!

## Understanding the Code

### Key Components

```python
# 1. Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

# 2. Create Fetch.ai agent
agent = Agent(
    name="claude_assistant",
    seed="your-unique-seed",
    port=8000,
    mailbox=True
)

# 3. Handle messages
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # Extract user text
    # Call Claude API
    # Send response back
```

### Model Configuration

```python
MODEL_NAME = 'claude-3-5-sonnet-20241022'  # Latest Claude 3.5 Sonnet
MAX_TOKENS = 1024          # Response length limit
TEMPERATURE = 0.7          # Creativity level (0.0-1.0)
```

**Temperature Settings:**
- `0.0-0.3`: More focused, consistent (good for factual queries)
- `0.4-0.7`: Balanced (default, good for general use)
- `0.8-1.0`: More creative, varied (good for creative writing)

### Conversation History

The agent maintains context by storing recent messages:

```python
# Stores last 10 messages per user
conversations[sender] = history[-10:]
```

This allows Claude to reference previous messages in the conversation!

## Customization

### Change the System Prompt

Edit `SYSTEM_PROMPT` in `basic_claude_agent.py`:

```python
SYSTEM_PROMPT = """You are a helpful coding assistant.

You specialize in:
- Python programming
- Debugging code
- Explaining algorithms
- Best practices

Always provide code examples when relevant."""
```

### Adjust Model Parameters

```python
# More creative responses
TEMPERATURE = 0.9
MAX_TOKENS = 2048

# More focused responses
TEMPERATURE = 0.3
MAX_TOKENS = 512
```

### Use Different Claude Models

```python
# Claude 3.5 Sonnet (Best balance - Recommended)
MODEL_NAME = 'claude-3-5-sonnet-20241022'

# Claude 3 Opus (Most capable, slower, more expensive)
MODEL_NAME = 'claude-3-opus-20240229'

# Claude 3 Haiku (Fastest, most affordable)
MODEL_NAME = 'claude-3-haiku-20240307'
```

## Claude Model Comparison

| Model | Best For | Speed | Cost | Context |
|-------|----------|-------|------|---------|
| **Claude 3.5 Sonnet** | General use, reasoning | Fast | Mid | 200K |
| **Claude 3 Opus** | Complex tasks, analysis | Slower | High | 200K |
| **Claude 3 Haiku** | Quick responses, simple tasks | Fastest | Low | 200K |

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

**Solution:** Make sure your `.env` file exists and contains:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### "API key is invalid"

**Solutions:**
- Check you copied the complete key (starts with `sk-ant-api03-`)
- Verify key is active at [console.anthropic.com](https://console.anthropic.com)
- Make sure your account has available credits

### "Rate limit exceeded"

**Solutions:**
- Wait 60 seconds and try again
- Check your usage limits in the Anthropic Console
- Consider upgrading your plan for higher limits

### Agent not responding

**Check:**
1. Agent is running (terminal shows "Agent is running!")
2. No error messages in terminal
3. Correct agent address in ASI One
4. Internet connection is stable

## Cost & Pricing

Claude API pricing (as of 2024):

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Claude 3 Opus | $15.00 | $75.00 |
| Claude 3 Haiku | $0.25 | $1.25 |

**For this basic agent:**
- Average message: ~100 tokens input, ~200 tokens output
- Cost per message: $0.0003-$0.003 (depending on model)
- Very affordable for development and testing!

**Free Credits:**
- New accounts get free credits to start
- Check your balance at [console.anthropic.com](https://console.anthropic.com)

## Next Steps

1. ✅ **Test different prompts** - See how Claude handles various queries
2. 🎨 **Customize the system prompt** - Make it your own!
3. 📊 **Add features** - Extend functionality (see Advanced section)
4. 🚀 **Deploy to Agentverse** - Make it publicly accessible
5. 🔗 **Connect to other agents** - Build multi-agent systems

## Advanced Features (Coming Soon)

- **Agent-to-Agent Communication**: Let agents talk to each other
- **Claude Vision**: Add image understanding capabilities
- **Function Calling**: Let Claude use tools and APIs
- **Streaming Responses**: Show responses as they're generated
- **Multi-turn Conversations**: Advanced context management

## Resources

- [Anthropic Documentation](https://docs.anthropic.com)
- [Claude API Reference](https://docs.anthropic.com/claude/reference)
- [Fetch.ai Docs](https://fetch.ai/docs)
- [uAgents Documentation](https://fetch.ai/docs/guides/agents/introduction)
- [ASI One Platform](https://asi.one)

## Support

**Issues?** 
- Check the troubleshooting section above
- Read [Anthropic's Help Center](https://support.anthropic.com)
- Ask in [Fetch.ai Discord](https://discord.gg/fetchai)

## What's Next?

👉 **Guide 02: Claude Vision Agent** - Add image understanding to your agent!

---

**Ready to build something amazing with Claude? Start experimenting!** 🚀
