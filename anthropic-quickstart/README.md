# 🤖 Anthropic Claude Quickstart for Fetch.ai

Build intelligent AI agents powered by Anthropic's Claude on the Fetch.ai decentralized network!

## 🎯 What You'll Learn

This quickstart series teaches you to build production-ready AI agents using **Claude 3.5 Sonnet** and the **Fetch.ai uAgents framework**. From basic conversational agents to advanced multi-modal applications.

## 📚 Guides

### 01. Basic Claude Agent ✅
**Start here!** Build your first conversational AI agent with Claude 3.5 Sonnet.

**What you'll learn:**
- Setting up Claude API with Fetch.ai
- Handling chat messages
- Conversation context management
- Deploying to Agentverse

**Time:** 15 minutes

👉 [Start Guide 01](./01-basic-claude-agent/README.md)

---

### 02. Claude Vision Agent ✅
Add visual understanding to your agent using Claude's vision capabilities.

**What you'll learn:**
- Processing images with Claude
- Image analysis and description
- Multi-modal conversations
- Handling image uploads from ASI One
- URL-based image input

**Time:** 20 minutes

👉 [Start Guide 02](./02-claude-vision-agent/README.md)

---

### 03. Function Calling Agent ✅
Let Claude use external tools and APIs to perform actions.

**What you'll learn:**
- Defining tools and functions
- Claude's native function calling
- Multi-step tool execution
- Weather, calculator, time, search tools
- Creating custom tools
- Real API integration

**Time:** 25 minutes

 [Start Guide 03](./03-function-calling-agent/README.md)

---

### 04. MCP Agent ✅
Connect Claude to ANY MCP (Model Context Protocol) server for unlimited capabilities.

**What you'll learn:**
- MCP (Model Context Protocol) integration
- Connecting to GitHub, databases, filesystems
- Auto-discovering tools from servers
- Adding any MCP server easily
- Bridging Fetch.ai with MCP ecosystem

**Time:** 30 minutes

 [Start Guide 04](./04-mcp-agent/README.md)

---

### 05. Multi-Agent System ✅
Build a system where multiple agents work together!

**What you'll learn:**
- Agent-to-agent communication
- Request routing and classification
- Multi-agent coordination
- Simple 3-agent architecture
- Message forwarding patterns

**Time:** 20 minutes

 [Start Guide 05](./05-multi-agent-system/README.md)

---

## Quick Start

```bash
# Clone or navigate to the project
cd anthropic-quickstart

# Start with Guide 01
cd 01-basic-claude-agent

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Run the agent
python basic_claude_agent.py
```

## 🔑 Getting Your API Key

1. Visit [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Sign up or log in
3. Click "Create Key"
4. Copy your API key (starts with `sk-ant-api03-`)
5. Add it to your `.env` file

**Free Credits:** New accounts receive free credits to get started!

## 💡 Why Claude on Fetch.ai?

### Claude Advantages
- 🧠 **Advanced Reasoning**: Best-in-class problem-solving
- 📚 **Long Context**: 200K tokens (entire books!)
- 🔒 **Safety Built-in**: Constitutional AI for helpful, harmless outputs
- ⚡ **Fast & Reliable**: Quick responses with consistent quality
- 🎨 **Multi-modal**: Text + Vision capabilities

### Fetch.ai Benefits
- 🌐 **Decentralized**: Run agents anywhere
- 💬 **Easy Communication**: Built-in messaging protocols
- 🔗 **Agent Network**: Connect multiple AI agents
- 🚀 **Production Ready**: Deploy to Agentverse instantly
- 🆓 **Open Source**: Full control over your agents

### Combined Power
Build intelligent, autonomous agents that can:
- Reason deeply about complex problems
- Understand images and text
- Use tools and APIs
- Communicate with other agents
- Run 24/7 in the cloud

## 📊 Claude Models

| Model | Best For | Context | Speed | Cost |
|-------|----------|---------|-------|------|
| **Claude 3.5 Sonnet** ⭐ | General use, balanced | 200K | Fast | $$ |
| **Claude 3 Opus** | Complex analysis | 200K | Slower | $$$ |
| **Claude 3 Haiku** | Quick tasks | 200K | Fastest | $ |

**Recommendation:** Start with **Claude 3.5 Sonnet** - best balance of performance, speed, and cost.

## 🛠️ Prerequisites

- **Python 3.9+**
- **Anthropic API Key** ([Get one](https://console.anthropic.com))
- **Basic Python Knowledge**
- *Optional:* Fetch.ai Agentverse account

## 📖 Guide Structure

Each guide includes:
- ✅ **Complete working code** - Copy, paste, run!
- 📝 **Step-by-step instructions** - Never get lost
- 🎯 **Clear learning objectives** - Know what you're building
- 🔧 **Customization tips** - Make it your own
- 🐛 **Troubleshooting** - Fix common issues
- 💡 **Next steps** - Continue learning

## 🎓 Learning Path

**Beginner:**
1. Complete Guide 01 (Basic Agent)
2. Test with different prompts
3. Customize the system prompt
4. Deploy to Agentverse

**Intermediate:**
1. Complete Guide 02 (Vision Agent)
2. Combine text and image inputs
3. Build a specialized agent (e.g., tutor, analyst)

**Advanced:**
1. Complete Guide 03 (Function Calling)
2. Connect multiple agents
3. Build complex workflows
4. Integrate with external services

## 🚀 Deployment Options

### Local Development
- Run on your machine
- Full control and debugging
- No deployment needed
- Good for testing

### Agentverse (Cloud)
- Deploy with one command
- 24/7 availability
- Automatic scaling
- Production ready

### Self-Hosted
- Deploy to your own servers
- Docker containers
- Full infrastructure control
- Custom networking



## 🎯 Hackathon Ideas

Use these guides to build:
- 🤖 **AI Assistants**: Customer support, tutoring, coaching
- 📊 **Research Agents**: Market analysis, competitor research
- 🎨 **Creative Tools**: Writing assistants, brainstorming bots
- 🔧 **Automation**: Data processing, report generation
- 🏥 **Specialized Agents**: Legal, medical, financial advisors
- 🎮 **Game NPCs**: Intelligent characters, quest givers
- 📱 **App Backends**: Add AI to your applications

## 🗺️ Roadmap

- [x] Guide 01: Basic Claude Agent
- [x] Guide 02: Claude Vision Agent
- [x] Guide 03: Function Calling Agent
- [x] Guide 04: MCP Agent
- [x] Guide 05: Multi-Agent System (Simple)
- [ ] Guide 06: Streaming Responses
- [ ] Guide 07: Advanced Multi-Agent (Complex workflows)
- [ ] Guide 08: Production Deployment

## 📦 All Dependencies

```bash
# Core requirements for all guides
uagents>=0.14.0
anthropic>=0.39.0
python-dotenv>=1.0.0

# Additional (guide-specific)
# Will be specified in each guide's requirements.txt
```

## 🔒 Security Best Practices

1. **Never commit API keys** - Use `.env` files (already in `.gitignore`)
2. **Rotate keys regularly** - Generate new keys periodically
3. **Monitor usage** - Check Anthropic Console for unusual activity
4. **Set spending limits** - Configure budget alerts
5. **Use environment variables** - Never hardcode secrets

## 📝 Contributing

Found an issue? Have an improvement?
- Open an issue
- Submit a pull request
- Share your agent creations!

## 📄 License

This quickstart is provided as-is for educational purposes.

## 🙏 Acknowledgments

Built with:
- [Anthropic Claude](https://anthropic.com) - Advanced AI
- [Fetch.ai](https://fetch.ai) - Agent framework
- [uAgents](https://github.com/fetchai/uAgents) - Agent library

---

## 🎯 Ready to Start?

👉 **[Begin with Guide 01: Basic Claude Agent](./01-basic-claude-agent/README.md)**

Build your first AI agent in 15 minutes! 🚀

---

