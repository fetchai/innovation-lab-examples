# ⚡ 5-Minute Quick Start - Imagen Agent

Generate AI images in 5 minutes!

## 1️⃣ Setup (1 minute)

```bash
cd 02-imagen-agent

# Use existing venv or create new
pip install -r requirements.txt

# Use same .env as Guide 01 or create
cp .env.example .env
# Add your GEMINI_API_KEY
```

## 2️⃣ Run (30 seconds)

```bash
python imagen_agent.py
```

## 3️⃣ Test (30 seconds)

**Via ASI One:**
1. Go to https://asi.one
2. Find your agent
3. Send: `A photo of a sunset over mountains`

**Locally:** Test with test messages (via agent inspector)

## 4️⃣ Try These Prompts

```
A minimalist logo for a tech startup

An oil painting of a cat in a garden, impressionist style

A futuristic cityscape with flying cars, cyberpunk, neon lights

A professional product photo of a coffee mug, studio lighting

A watercolor painting of a lighthouse by the ocean at sunset
```

## 5️⃣ Deploy to Agentverse (1 minute)

1. Go to https://agentverse.ai
2. Create new agent
3. Copy `imagen_agent.py` code
4. Add `GEMINI_API_KEY` to secrets
5. Deploy!

## ✅ Done!

You now have an AI image generator agent!

## 🎨 Prompt Tips

**Structure:** Subject + Context + Style

**Examples:**
- **Photo**: "A photo of [subject], [lighting/setting]"
- **Art**: "A [style] of [subject], [mood/colors]"
- **Logo**: "A [style] logo for [business], [elements]"

## 🚀 Next Steps

- Experiment with different styles
- Try adding text to images
- Generate multiple variations
- Build custom UI
- Combine with other agents!

## 💡 Pro Tips

1. **Be specific** - More details = better results
2. **Iterate** - Refine prompts based on results
3. **Reference styles** - Mention art movements or photographers
4. **Use modifiers** - Add lighting, composition, mood
5. **Keep text short** - Under 25 characters in images

Ready to create amazing images! 🎨✨
