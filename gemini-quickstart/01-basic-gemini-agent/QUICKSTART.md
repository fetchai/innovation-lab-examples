# ⚡ 5-Minute Quick Start

Get your Gemini agent running in 5 minutes!

## 1️⃣ Setup (2 minutes)

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

## 2️⃣ Get Gemini API Key (1 minute)

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Paste it in `.env`:
   ```
   GEMINI_API_KEY=your_actual_key_here
   ```

## 3️⃣ ## Step 3: Update the seed in your agent to a unique phrase and Run the Agent

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

Open another terminal and test locally or use ASI One!

### Option A: Use ASI One (Recommended)
1. Go to https://asi1.ai
2. Search for your agent (after deploying to Agentverse)
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
