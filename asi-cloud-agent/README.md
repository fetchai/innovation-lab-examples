# Quick Start: ASI:Cloud Agent

Build your first ASI:Cloud-powered AI agent on Fetch.ai in 10 minutes! 🚀

## What You'll Build

A conversational AI agent that:
- ✅ Uses ASI:Cloud (asi1-mini) for intelligent responses
- ✅ Registers to Fetch.ai Agentverse
- ✅ Works with ASI:One messaging
- ✅ Maintains conversation context and history
- ✅ Is discoverable on the marketplace

## Prerequisites

- Python 3.9+
- ASI:Cloud API key
- 5-10 minutes

## What is ASI:Cloud?

ASI:Cloud provides access to various LLM models through a unified API interface. This agent uses the `asi1-mini` model, which offers fast and efficient AI responses powered by the ASI (Artificial Superintelligence) infrastructure.

## Step 1: Get Your ASI:Cloud API Key

1. Visit [ASI:Cloud](https://asicloud.cudos.org/)
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy your API key

## Step 2: Install Dependencies

```bash
# Create project directory
mkdir my-asi-cloud-agent
cd my-asi-cloud-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install uagents openai python-dotenv
```

## Step 3: Set Up Environment Variables

Create a `.env` file:

```bash
ASICLOUD_API_KEY=your_asi_cloud_api_key_here
ASICLOUD_BASE_URL=https://inference.asicloud.cudos.org/v1
```

**Note:** The `ASICLOUD_BASE_URL` is optional and defaults to the standard ASI:Cloud endpoint if not provided.

## Step 4: Create Your Agent

Copy the code from `agent.py` or use it as a template.

### Key Components Explained:

**1. ASI:Cloud Integration**
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("ASICLOUD_API_KEY"),
    base_url=os.getenv("ASICLOUD_BASE_URL", "https://inference.asicloud.cudos.org/v1")
)
```

**2. Agent Setup**
```python
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import ChatMessage, ChatAcknowledgement

agent = Agent(
    name="asi_agent",
    seed="your-unique-seed-phrase",
    port=8000,
    mailbox=True  # Enable for local agents running on your machine
)
```

**3. Message Handling with History**
```python
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Get conversation history
    conversations = ctx.storage.get("conversations") or {}
    history = conversations.get(sender, [])
    
    # Generate response with context
    response_text = generate_response(history, user_text)
    
    # Update history
    history.append({"role": "user", "text": user_text})
    history.append({"role": "assistant", "text": response_text})
    conversations[sender] = history[-10:]  # Keep last 10 messages
```

## Step 5: Run Locally

```bash
python agent.py
```

You should see:
```
🤖 Starting ASI:Cloud Agent...
📍 Agent address: agent1q...
✅ ASI:Cloud API configured
✅ Agent is running!
```

## Step 6: Register on Agentverse

### Option A: Direct Hosting
1. Go to [Agentverse](https://agentverse.ai)
2. Create new agent
3. Copy your `agent.py` code
4. Add your `ASICLOUD_API_KEY` to secrets
5. Deploy!

### Option B: Local with Mailbox
1. Run your agent locally: `python agent.py`
2. Click the inspector link in the terminal
3. Connect to mailbox
4. Register your agent with your Agentverse account
5. Your agent will be accessible even when running locally

Refer to the [Fetch.ai Innovation Lab Documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation) for detailed instructions.

## Step 7: Test on ASI One

1. Open [ASI:One](https://asi1.ai)
2. Search for your agent name or use the agent address
3. Start chatting!

Try these prompts:
- "Hello! What can you help me with?"
- "Explain quantum computing in simple terms"
- "Write a haiku about AI agents"
- "What is ASI:Cloud?"

## 🎯 What's Next?

Now that you have a basic agent running, you can:

1. **Customize the System Prompt** - Make it specialized for your use case
2. **Adjust Model Parameters** - Tune temperature, max_tokens, etc.
3. **Add More Models** - Switch between different ASI:Cloud models
4. **Add Real Actions** - Integrate MCPs for tool usage
5. **Enhance Memory** - Extend conversation history tracking

## 📊 Architecture

```
User (ASI:One) 
    ↓
    ↓ ChatMessage
    ↓
Fetch.ai Agent
    ↓
    ↓ chat.completions.create()
    ↓
ASI:Cloud API (asi1-mini)
    ↓
    ↓ Response
    ↓
User (ASI:One)
```

## 🔧 Configuration Options

### Available Models

The ASI:Cloud API supports multiple ASI:One native models. You can change the model in `agent.py`:

```python
MODEL_NAME = "asi1-mini"  # Fast and efficient
# MODEL_NAME = "asi1-pro"  # Higher quality (if available)
```

### Generation Parameters

Adjust the response behavior:

```python
GENERATION_CONFIG = {
    "temperature": 0.7,    # 0.0-1.0: Lower = more focused, Higher = more creative
    "top_p": 0.95,         # Nucleus sampling parameter
    "max_tokens": 512,     # Maximum response length
}
```

### Conversation History

The agent maintains conversation history per user:
- Keeps last 10 messages by default
- Uses last 5 messages for context when generating responses
- Stored in agent's persistent storage

## 🐛 Troubleshooting

**"API key not found"**
- Check your `.env` file exists
- Verify `ASICLOUD_API_KEY` is set correctly
- Restart your agent after adding the key

**"Agent not responding"**
- Check if port 8000 is available
- Look for errors in console output
- Verify ASI:Cloud API is accessible
- Check your API key is valid

**"Can't find agent on ASI:One"**
- Wait 1-2 minutes after deployment
- Ensure mailbox is enabled for local agents
- Check agent is deployed successfully on Agentverse
- Verify agent address is correct

**"Connection timeout"**
- Check your internet connection
- Verify ASI:Cloud API endpoint is accessible
- Check firewall settings

## 💡 Pro Tips

1. **Use Appropriate Model** - `asi1-mini` is fast and cost-effective for most use cases
2. **Monitor API Usage** - Track your ASI:Cloud API usage
3. **Adjust History Length** - Balance context vs. token usage
4. **Set Temperature** - Lower for factual responses, higher for creative ones
5. **Log Conversations** - For debugging and improvement

## 🚀 Use Case Ideas

Enhance this basic agent for:
- 🎓 **Educational Assistant** - Learning and tutoring
- 💼 **Business Advisor** - Strategy and planning
- 🎨 **Creative Assistant** - Writing and ideation
- 🔧 **Technical Support** - Troubleshooting help
- 📊 **Data Analyst** - Insights and analysis
- 🌐 **Multi-language Assistant** - Translation and communication

## 📝 Code Reference

- `agent.py` - Main agent code
- `requirements.txt` - Dependencies
- `.env.example` - Environment template

## 🔗 Resources

- [ASI:Cloud Documentation](https://docs.cudos.org/docs/asi-cloud/inference/tutorials/chat-completions)
- [Fetch.ai Innovation Lab](https://innovationlab.fetch.ai)
- [Agentverse](https://agentverse.ai)
- [ASI:One](https://asi1.ai)
- [uAgents Documentation](https://docs.fetch.ai)

## Next Steps

👉 Customize the `SYSTEM_PROMPT` for your specific use case
👉 Experiment with different model parameters
👉 Add more advanced features like tool integration
👉 Deploy and share with users!

