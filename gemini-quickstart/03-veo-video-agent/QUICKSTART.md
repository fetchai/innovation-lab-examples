# ⚡ 5-Minute Quick Start - Veo Video Agent

Generate AI videos in 5 minutes! (Plus 30-60s per video generation)

## 1️⃣ Setup (1 minute)

```bash
cd 03-veo-video-agent

# Use existing venv or create new
pip install -r requirements.txt

# Use same .env as previous guides
# Already have GEMINI_API_KEY and AGENTVERSE_API_KEY!
# Update the seed in your agent to a unique phrase and Run the Agent
```

## 2️⃣ Run (30 seconds)

```bash
python veo_agent.py
```

## 3️⃣ Test (30 seconds + 30-60s generation time)

**Via ASI One:**
1. Go to https://asi1.ai
2. Find your agent
3. Send: `A calico kitten sleeping in the sunshine`
4. **Wait 30-60 seconds** - video generation takes time!

## 4️⃣ Try These Prompts

```
A close up of two people talking by torchlight

An origami butterfly flies through a garden

Cinematic drone shot rising over mountains at sunset

A robot dancing on a city street at night, neon lights

Wide shot of waves crashing on a beach at golden hour
```

## 5️⃣ Pro Tips

### Prompt Structure
**Camera + Subject + Action + Setting + Style**

### Examples:
```
Wide cinematic shot of [subject] [action] in [setting], [mood]
```

```
Close up of [character] saying "[dialogue]", [atmosphere]
```

### Camera Angles:
- Wide shot, Close up, Medium shot
- Aerial view, Drone shot
- Eye-level, Low angle, High angle

### Camera Movement:
- Panning, Tracking, Orbiting
- Zooming in/out, Pulling back
- Rising, Descending

## ⏳ Important Notes

1. **Be Patient** - Videos take 30-60 seconds to generate
2. **Quota Limits** - Videos use more quota than images
3. **High Quality** - Worth the wait! 720p/1080p HD
4. **Native Audio** - Veo generates sound automatically

## 🎬 What You Can Create

- Cinematic scenes
- Product showcases
- Character performances
- Nature footage
- Abstract visuals
- Dialogue scenes
- Action sequences
- Animated content

## 💡 Best Practices

1. **Be Specific** - Describe camera, action, setting clearly
2. **Add Movement** - Mention camera motion or subject action
3. **Set the Mood** - Include lighting, atmosphere, style
4. **Keep it Simple** - 8 seconds means focus on one main action
5. **Try Multiple Times** - Generation varies, experiment!

## 🚀 Deploy to Agentverse

1. Go to https://agentverse.ai
2. Create new agent
3. Copy `veo_agent.py` code
4. Add both API keys to secrets
5. Deploy!

## ✅ Done!

You now have an AI video generator agent!

Ready to create stunning videos! 🎬✨
