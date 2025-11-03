# ⚡ 5-Minute Quick Start

Get your Gemini agent running in 5 minutes!

## Step 1: Setup (2 minutes)

```bash
# Clone or download this folder
cd 01-basic-gemini-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

## Step 2: Get Gemini API Key (1 minute)

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Paste it in `.env`:
   ```
   GEMINI_API_KEY=your_actual_key_here
   ```

## Step 3: Update the seed in your agent to a unique seed phrase

## step 4: Two options to register your agent with Agentverse: 

1. Direct hosting on agentverse
2. Running your agent locally and registering it with Agentverse using Mailbox

1.  Direct Hosting: Go to agentverse.ai and create a new agent and paste the code from basic_gemini_agent.py and add the GEMINI_API_KEY in secrets. Refer here : [Fetch.ai Innovation Lab Documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#hosted-agents)

2. Running your agent locally and click the inspector link on the terminal and connect to mailbox and register your agent with Agentverse account. Refer here : [Fetch.ai Innovation Lab Documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents)

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

## 4️⃣ Test It (30 seconds)

Test it on Agentverse "Chat with Agent" or on asi1.ai

### Option A: Use ASI One (Recommended)
1. Go to https://asi1.ai
2. Using agent handle or agent address prompt your agent (after registering your agent with Agentverse)
3. Start chatting!


## 5️⃣ Deploy to Agentverse (1 minute)

1. Go to https://agentverse.ai
2. Sign in
3. Create new agent
4. Copy code from `basic_gemini_agent.py`
5. Add `GEMINI_API_KEY` in Secrets
6. Click Deploy!

## ✅ Done!

Your agent is now:
- ✨ Powered by Gemini
- 🌐 Live on Agentverse
- 🔍 Discoverable on ASI One
- 💬 Ready to chat!

## 🎯 Next Steps

- Customize the `SYSTEM_PROMPT` for your use case
- Add more conversation features
- Try the multimodal guide (coming soon)
- Integrate MCPs for real actions

## 💡 Example Prompts to Try

- "Explain quantum computing in simple terms"
- "Write a Python function to sort a list"
- "What are the benefits of decentralized AI?"
- "Help me brainstorm ideas for a mobile app"
- "Summarize the key concepts of blockchain"

## 🐛 Having Issues?

Check the main [README.md](./README.md) for detailed troubleshooting!
