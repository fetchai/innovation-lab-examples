# Quick Start: Veo 3.1 Video Generation Agent

Create AI-generated videos using Google Veo 3.1 on Fetch.ai! 🎬

## What You'll Build

An AI agent that:
- ✅ Generates 8-second HD videos from text prompts
- ✅ Uses Google Veo 3.1 (state-of-the-art video model)
- ✅ Includes native audio generation
- ✅ Works with ASI One chat interface
- ✅ Cinematic realism and stunning quality

## Prerequisites

- Python 3.9+
- Google Gemini API key (same key works for Veo!)
- Agentverse API key (for video storage)
- Completed Guides 01 & 02

## Step 1: Install Dependencies

```bash
cd 03-veo-video-agent

# Use existing virtual environment or create new one
pip install -r requirements.txt
```

## Step 2: Configure API Keys

Use the same `.env` file or create one:

```bash
# Same keys as previous guides!
GEMINI_API_KEY=your_gemini_api_key_here
AGENTVERSE_API_KEY=your_agentverse_api_key_here
```

## Step 3: Run the Agent

```bash
python veo_agent.py
```

You should see:
```
🎬 Starting Veo 3.1 Video Generator Agent...
📍 Agent address: agent1q...
✅ Veo API configured
✅ Agentverse storage configured
⏳ Note: Video generation takes 30-60 seconds per request
✅ Agent is running!
```

## Step 4: Generate Videos

### Via ASI One
1. Go to https://asi.one
2. Search for your agent
3. **Be patient** - videos take 30-60 seconds to generate!
4. Try these prompts:

```
A close up of two people talking by torchlight in a cave
```

```
A calico kitten sleeping in the sunshine, camera slowly pans to reveal a sunny room
```

```
An origami butterfly flies gracefully through a garden
```

```
Cinematic drone shot rising over mountains at sunset
```

## Understanding Veo Prompts

### Basic Structure
**Action + Subject + Setting + Camera + Style**

### Key Elements:

**1. Camera Angles & Movement**
- "Close up", "Wide shot", "Medium shot"
- "Panning", "Tracking", "Drone shot"
- "Camera pulls back", "Slowly zooms in"

**2. Action & Movement**
- Be specific about what's happening
- Describe movements clearly
- Include timing if important

**3. Audio & Dialogue** (Optional)
- Veo generates audio natively!
- Can include spoken dialogue
- Mention sound effects

**4. Lighting & Atmosphere**
- "Golden hour", "Torchlight", "Neon lights"
- "Foggy", "Moonlit", "Dramatic shadows"

**5. Style & Mood**
- "Cinematic", "Dreamlike", "Haunting"
- "High-fashion", "Documentary style"

## Example Prompts by Category

### Dialogue & Sound Effects
```
A close up of two people staring at a cryptic drawing on a wall, 
torchlight flickering. A man murmurs, 'This must be it. That's 
the secret code.' The woman looks at him and whispering excitedly, 
'What did you find?'
```

### Cinematic Realism
```
A wide, cinematic shot of a lone astronaut walking across a barren, 
red Martian landscape. The camera slowly tracks alongside them as 
dust swirls in the thin atmosphere. The sun sets on the horizon, 
casting long shadows. The scene is epic and isolated.
```

### Creative Animation
```
An origami butterfly flaps its wings and flies out of french doors 
into a vibrant garden. It lands on a colorful origami flower as 
paper leaves flutter in the breeze. Whimsical and dreamlike.
```

### Product Showcase
```
A sleek, modern smartphone slowly rotates on a white surface 
against a gradient background. Dramatic studio lighting highlights 
its metallic edges. The camera orbits around it, showcasing the 
design from all angles. Professional and elegant.
```

### Nature & Landscapes
```
Aerial drone footage rising above a misty forest at dawn. The 
camera ascends through wispy fog to reveal mountain peaks bathed 
in golden sunlight. Birds fly past. Serene and majestic.
```

## Veo Configuration

The agent uses these default settings:
- **Model**: veo-3.1-generate-preview
- **Duration**: 8 seconds (fixed)
- **Resolution**: 720p (can be 1080p)
- **Videos per prompt**: 1
- **Audio**: Native generation (automatic)

### Customizing in Code

Edit `veo_agent.py` to change defaults:

```python
DEFAULT_VIDEO_CONFIG = types.GenerateVideosConfig(
    number_of_videos=1,
    resolution="1080p",  # Higher quality (uses more quota)
)
```

**Available options:**
- **resolution**: "720p", "1080p"
- **number_of_videos**: 1-4 (generate multiple variations)

## Advanced Features

### 1. Image-to-Video
Generate a video starting from an image (requires Nano Banana integration)

### 2. Video Extension
Extend existing Veo-generated videos by 7 seconds

### 3. Reference Images
Use up to 3 reference images to guide content (preserve characters/objects)

### 4. Frame-Specific Generation
Specify first and last frames for interpolation

(These features require additional code - see Veo API documentation)

## Tips for Best Results

### ✅ Do:
- Be very descriptive and specific
- Include camera movements and angles
- Describe the action clearly
- Mention lighting and atmosphere
- Specify style and mood
- Include audio/dialogue if desired
- Be patient (30-60 seconds per video!)

### ❌ Don't:
- Use vague or ambiguous descriptions
- Expect instant results (it's NOT like images!)
- Request harmful or inappropriate content
- Expect perfect lip sync on first try
- Generate videos longer than 8 seconds

## Prompt Writing Guide

### Basic Template:
```
[Camera angle] of [subject] [action] in [setting], [atmosphere/lighting]. 
[Style/mood].
```

### Example:
```
Wide cinematic shot of a dancer leaping through a rain-soaked street 
at night, neon signs reflecting in puddles. Dramatic and moody.
```

### Adding Dialogue:
```
Close-up of an elderly man at a cafe. He looks directly at camera 
and says warmly, "The best stories are yet to be written." He smiles. 
Intimate and hopeful.
```

### Adding Camera Movement:
```
The camera starts on a close-up of a vintage record player, then 
slowly pulls back to reveal a cozy living room filled with plants 
and afternoon sunlight. Peaceful and nostalgic.
```

## Performance & Quotas

### Generation Time
- **Typical**: 30-60 seconds per video
- **Complex prompts**: Up to 2 minutes
- **Max timeout**: 10 minutes (agent will abort)

### Quota Considerations
- Videos use **much more quota** than images
- Free tier: Very limited (5-10 videos/day)
- Paid tier: Higher limits but still monitored
- **Recommendation**: Enable billing for hackathon

### Cost (Paid Tier)
- ~$0.10-0.50 per video (varies)
- More expensive than images
- Worth it for impressive demos!

## Troubleshooting

**"Video generation timed out"**
- Prompt may be too complex
- Try simpler scene or shorter action
- Check API status
- Retry after a moment

**"Quota exceeded"**
- Hit daily/hourly limits
- Wait 1 hour or 24 hours
- Consider enabling billing
- See QUOTA_LIMITS.md in previous guide

**"Poor quality results"**
- Add more descriptive details
- Specify camera angles clearly
- Describe action and movement precisely
- Try multiple variations of your prompt

**"Audio not matching"**
- Dialogue generation is still improving
- Try simpler phrases
- Focus on ambient audio instead
- Regenerate 2-3 times

## Architecture

```
User (ASI One)
    ↓
    ↓ Text prompt via ChatMessage
    ↓
Veo Agent
    ↓
    ↓ generate_videos() → Long-running operation
    ↓
Google Veo 3.1 API (30-60s generation)
    ↓
    ↓ Poll operation status
    ↓
Generated video (MP4)
    ↓
    ↓ Upload to External Storage
    ↓
Agent Storage
    ↓
    ↓ ResourceContent with video
    ↓
User (ASI One) - Video displays!
```

## Key Differences from Image Agent

| Feature | Images | Videos |
|---------|--------|--------|
| Generation time | 1-5 seconds | 30-60 seconds |
| File size | ~100KB | ~5-10MB |
| Operation type | Immediate | Long-running (polling) |
| Quota usage | Lower | Higher |
| Cost | ~$0.001 | ~$0.10-0.50 |
| Updates to user | None | Periodic progress messages |

## Next Steps

1. **Test different styles** - Try cinematic, animated, documentary
2. **Add dialogue** - Experiment with character speech
3. **Combine with images** - Use Nano Banana for first frames
4. **Create sequences** - Generate multiple related videos
5. **Extend videos** - Add video extension feature

## Hackathon Ideas

Enhance this agent for competition:

- 🎬 **Story Generator** - Create video sequences with narrative
- 📱 **Social Media Content** - Auto-generate video posts
- 🎓 **Educational Videos** - Visualize concepts
- 🎮 **Game Trailers** - Generate cinematic game previews
- 🎨 **Music Videos** - Visualize songs and lyrics
- 📺 **Commercial Creator** - Product showcase videos
- 🎭 **Character Performances** - Animated character interactions
- 🌍 **Virtual Tourism** - Generate travel destination videos

## Example Conversation

```
User: Create a video of a robot dancing
Agent: 🎬 Generating your video... This takes 30-60 seconds. Please wait! ⏳
Agent: ⏳ Still generating... 30s elapsed. Almost there!
Agent: 🎬 Generated: A robot dancing... (8 seconds, 720p)
      [Video displays in ASI One]

User: Make it more cinematic
Agent: 🎬 Generating your video...
Agent: 🎬 Generated: Cinematic shot of robot dancing...
      [New video displays]
```

## Resources

- [Google Veo Documentation](https://ai.google.dev/gemini-api/docs/veo)
- [Veo Prompt Guide](https://ai.google.dev/gemini-api/docs/veo?lang=python#prompt_guide)
- [Video Generation Examples](https://ai.google.dev/examples)
- [Fetch.ai Agent Resources](https://fetch.ai/docs)

## Next Guide

👉 **Guide 04: MCP Integration** - Add real-world actions to your agents!

---

**Ready to generate stunning videos? Run the agent and start creating!** 🎬✨
