# Quick Start: Basic Gemini Agent

Build your first Google Gemini-powered AI agent on Fetch.ai in 10 minutes! 🚀

## What You'll Build

A conversational AI agent that:
- ✅ Uses Google Gemini for intelligent responses
- ✅ Registers to Fetch.ai Agentverse
- ✅ Works with ASI One messaging
- ✅ Maintains conversation context
- ✅ Is discoverable on the marketplace

## Prerequisites

- Python 3.9+
- Google Gemini API key
- 5-10 minutes

## Step 1: Get Your Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy your API key

## Step 2: Install Dependencies

```bash
# Create project directory
mkdir my-gemini-agent
cd my-gemini-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install uagents google-genai python-dotenv
```

## Step 3: Set Up Environment Variables

Create a `.env` file:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

## Step 4: Create Your Agent

Copy the code from `basic_gemini_agent.py` or create it using the template provided.

### Key Components Explained:

**1. Gemini Integration**
```python
import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')
```

**2. Agent Setup**
```python
from uagents import Agent, Context, Protocol
from uagents.communication.chat import ChatMessage, ChatResponse

agent = Agent(
    name="gemini_assistant",
    seed="your-unique-seed-phrase",
    port=8000,
    mailbox=True  # Enable for local agents running on your machine
)
```

**3. Message Handling**
```python
@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Get response from Gemini
    response = model.generate_content(msg.text)
    
    # Send back to user
    await ctx.send(sender, ChatResponse(
        text=response.text,
        agent_address=ctx.agent.address
    ))
```

## Step 5: Run Locally

```bash
python basic_gemini_agent.py
```

You should see:
```
🤖 Starting Gemini Assistant...
📍 Agent address: agent1q...
✅ Gemini API configured
✅ Agent is running!
```

## Step 6: Register on Agentverse

### Option A: Locally
1. Go to [Agentverse](https://agentverse.ai)
2. Create new agent
3. Copy your `basic_gemini_agent.py` code
4. Add your `GEMINI_API_KEY` to secrets
5. Deploy!


## Step 7: Test on ASI One

1. Open [ASI One](https://asi1.ai)
2. Search for your agent name
3. Start chatting!

Try these prompts:
- "Hello! What can you help me with?"
- "Explain quantum computing in simple terms"
- "Write a haiku about AI agents"

## 🎯 What's Next?

Now that you have a basic agent running, you can:

1. **Add Conversation Memory** - Track chat history
2. **Add Personality** - Customize the system prompt
3. **Add Multimodal Support** - Handle images (see Guide 02)
4. **Add Real Actions** - Integrate MCPs (see Guide 03)

## 📊 Architecture

```
User (ASI One) 
    ↓
    ↓ ChatMessage
    ↓
Fetch.ai Agent
    ↓
    ↓ generate_content()
    ↓
Google Gemini API
    ↓
    ↓ Response
    ↓
User (ASI One)
```

## 🐛 Troubleshooting

**"API key not found"**
- Check your `.env` file exists
- Verify `GEMINI_API_KEY` is set correctly
- Restart your agent after adding the key

**"Agent not responding"**
- Check if port 8000 is available
- Look for errors in console output
- Verify Gemini API quota/limits

**"Can't find agent on ASI One"**
- Wait 1-2 minutes after deployment
- Ensure mailbox is enabled
- Check agent is deployed successfully on Agentverse

## 💡 Pro Tips

1. **Use Flash Model** - `gemini-1.5-flash` is faster and cheaper for chat
2. **Add Rate Limiting** - Prevent API quota exhaustion
3. **Cache Responses** - For repeated questions
4. **Log Conversations** - For debugging and improvement
5. **Set Temperature** - Control response creativity

## 🚀 Hackathon Ideas

Enhance this basic agent:
- 🎓 **Tutor Agent** - Personalized learning assistant
- 🏥 **Health Coach** - Wellness and fitness guidance
- 💼 **Business Advisor** - Startup and strategy help
- 🎨 **Creative Writer** - Stories, poems, content
- 🔧 **Tech Support** - Troubleshooting assistant

## 📝 Code Reference

- `basic_gemini_agent.py` - Main agent code
- `requirements.txt` - Dependencies
- `.env.example` - Environment template

## Next Guide

👉 [02-multimodal-agent](../02-imagen-agent/) - Add image understanding to your agent!
