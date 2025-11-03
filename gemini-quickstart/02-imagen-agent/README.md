# Quick Start: Imagen Image Generation Agent

Create AI-generated images using Google Imagen on Fetch.ai! 🎨

## What You'll Build

An AI agent that:
- ✅ Generates high-quality images from text prompts
- ✅ Uses Google Imagen 4.0 (state-of-the-art)
- ✅ Stores generated images
- ✅ Works with ASI One chat interface
- ✅ Includes SynthID watermarking automatically

## Prerequisites

- Python 3.9+
- Google Gemini API key (same key works for Imagen!)
- Completed Guide 01 (Basic Gemini Agent)

## Step 1: Install Dependencies

```bash
cd 02-imagen-agent

# Activate your virtual environment
source ../01-basic-gemini-agent/venv/bin/activate  # Or create a new one

# Install packages
pip install -r requirements.txt
```

## Step 2: Configure API Key

Use the same `.env` file or create one:

```bash
# Same key as Gemini!
GEMINI_API_KEY=your_gemini_api_key_here
AGENTVERSE_API_KEY=your_agentverse_api_key_here
```

## Step 3: Update the seed in your agent to a unique phrase and Run the Agent

```bash
python imagen_agent.py
```

You should see:
```
🎨 Starting Imagen Generator Agent...
📍 Agent address: agent1q...
✅ Imagen API configured
✅ Agent is running!
```

## Step 4: Test Image Generation

### Via ASI One
1. Go to https://asi1.ai
2. Search for your agent
3. Try these prompts:

```
A photo of a sunset over mountains
```

```
A minimalist logo for a tech startup on white background
```

```
An oil painting of a cat sitting in a garden, impressionist style
```

```
A futuristic city with flying cars, cyberpunk style, neon lights
```

## Understanding Imagen Prompts

### Basic Structure
**Subject + Context + Style**

**Examples:**

**Photography:**
```
A photo of coffee beans on a wooden table, natural lighting
```

**Art:**
```
A watercolor painting of a lighthouse by the ocean at sunset
```

**Logo/Graphics:**
```
A modern minimalist logo for a coffee shop, geometric shapes
```

## Imagen Capabilities

### 1. Photography Styles
- **Realistic photos**: "A photo of..."
- **Studio photography**: "Studio photo with dramatic lighting"
- **Street photography**: "Street photography, urban, candid"
- **Portrait photography**: "Portrait photo, soft focus, bokeh"

### 2. Camera Settings
- **Lens types**: macro, wide angle, fisheye, 35mm, 50mm
- **Lighting**: natural, dramatic, warm, cold, golden hour
- **Effects**: motion blur, bokeh, soft focus
- **Film types**: polaroid, black and white

### 3. Art Styles
- **Paintings**: oil painting, watercolor, acrylic, pastel
- **Drawing**: sketch, charcoal, pencil drawing, ink
- **Digital**: digital art, 3D render, isometric
- **Historical**: impressionist, baroque, art nouveau, cubist

### 4. Text in Images
```
A poster with the text "Summer Vibes" in bold font, beach background
```
- Keep text under 25 characters
- Specify font style (bold, handwritten, modern, etc.)
- Works best with 1-3 phrases

## Advanced Prompt Techniques

### Example 1: Detailed Photography
```
A close-up photo of a steaming coffee cup on a wooden table, 
natural morning light coming from the left, soft focus background, 
warm tones, cozy atmosphere
```

### Example 2: Stylized Art
```
A digital illustration of a robot reading a book in a library, 
isometric view, vibrant colors, soft shadows, modern flat design
```

### Example 3: Logo Design
```
A minimalist logo for an eco-friendly company, featuring a leaf 
and circle, green and earth tones, clean lines, on white background
```

### Example 4: Scene with Text
```
A vintage travel poster style image with the text "Adventure Awaits",
mountains in the background, sunset colors, retro aesthetic
```

## Imagen Configuration

The agent uses these default settings:
- **Model**: imagen-4.0-generate-001
- **Number of images**: 1 (can be 1-4)
- **Aspect ratio**: 1:1 (square)
- **Person generation**: Allow adults only
- **Size**: 1K (standard quality)

### Customizing in Code

Edit `imagen_agent.py` to change defaults:

```python
DEFAULT_IMAGE_CONFIG = types.GenerateImagesConfig(
    number_of_images=4,          # Generate 4 variations
    aspect_ratio="16:9",         # Widescreen
    image_size="2K",             # Higher resolution
    person_generation="dont_allow"  # No people
)
```

**Available options:**
- **aspect_ratio**: "1:1", "3:4", "4:3", "9:16", "16:9"
- **image_size**: "1K", "2K" (only Standard/Ultra models)
- **person_generation**: "dont_allow", "allow_adult", "allow_all"

## Tips for Best Results

### ✅ Do:
- Be descriptive and specific
- Include subject, context, and style
- Mention lighting and composition
- Reference artistic styles or movements
- Iterate and refine your prompts
- Keep text in images short (under 25 chars)

### ❌ Don't:
- Use vague or ambiguous descriptions
- Exceed prompt length limits (480 tokens)
- Request harmful or inappropriate content
- Expect perfect text rendering on first try

## Prompt Examples by Category

### Business/Professional
```
A professional headshot of a businessperson in modern office, natural light
A sleek product photo of a smartphone on a white background, studio lighting
A corporate banner with the text "Innovation" in modern font, blue gradient
```

### Creative/Artistic
```
A surreal landscape with floating islands and waterfalls, dreamlike, vibrant colors
An abstract geometric pattern with triangles and circles, bold colors, modern art
A fantasy forest with glowing mushrooms, magical atmosphere, soft ethereal light
```

### Food/Lifestyle
```
A overhead photo of a gourmet burger on a wooden board, food photography
A cozy reading nook with books and a window, warm afternoon light, hygge style
A yoga studio with mats and plants, calm atmosphere, natural light, serene
```

### Technical/Conceptual
```
An isometric illustration of a data center, clean lines, tech aesthetic, blues
A diagram showing solar panels on a house, educational style, clear labels
A futuristic interface design, holographic elements, sci-fi, glowing cyan
```

## Troubleshooting

**"No image generated"**
- Try a simpler prompt
- Check API quota and limits
- Avoid restricted content (violence, explicit, etc.)
- Retry - generation can occasionally fail

**"Poor quality results"**
- Add more descriptive details
- Specify style, lighting, composition
- Reference specific art styles or photographers
- Try multiple variations of your prompt

**"Text not rendering correctly"**
- Keep text very short (under 25 characters)
- Specify font style clearly
- Try regenerating 2-3 times
- Consider making text larger in the prompt

**"Wrong aspect ratio"**
- Specify aspect ratio in the config
- Or add it to your prompt: "in 16:9 format"

## Architecture

```
User (ASI One)
    ↓
    ↓ Text prompt via ChatMessage
    ↓
Imagen Agent
    ↓
    ↓ generate_images()
    ↓
Google Imagen API
    ↓
    ↓ Generated image (PNG)
    ↓
Agent Storage (base64)
    ↓
    ↓ Response + Image reference
    ↓
User (ASI One)
```

## Next Steps

1. **Customize prompts** - Try different styles and subjects
2. **Add variations** - Generate multiple images per prompt
3. **Build UI** - Create a custom interface
4. **Integrate with other agents** - Combine text and image generation
5. **Add image editing** - Use generated images as starting points

## Hackathon Ideas

Enhance this agent for competition:

- 🎨 **Creative Studio** - Generate and iterate on designs
- 📱 **Social Media Content** - Auto-generate posts with images
- 🎓 **Educational Visuals** - Create learning materials
- 🏢 **Brand Asset Generator** - Logos, banners, graphics
- 🎮 **Game Asset Creator** - Characters, environments, items
- 📊 **Data Visualization** - Turn data into infographics
- 🛍️ **Product Mockups** - Generate product photos
- 🎬 **Storyboard Creator** - Visual storytelling

## Example Conversation

```
User: Create a logo for my coffee shop
Agent: 🎨 Generating your image...
Agent: ✨ Image Generated Successfully!
      Your Prompt: Create a logo for my coffee shop
      [Image displayed/stored]

User: Make it more minimalist
Agent: 🎨 Generating your image...
Agent: ✨ Image Generated Successfully!
      [Updated image]
```

## Resources

- [Google Imagen Documentation](https://ai.google.dev/gemini-api/docs/imagen)
- [Prompt Writing Guide](https://ai.google.dev/gemini-api/docs/imagen?lang=python#prompt_guide)
- [Fetch.ai Agent Resources](https://fetch.ai/docs)

## Next Guide

👉 **Guide 03: MCP Integration** - Add real-world actions to your agents!

---

**Ready to generate amazing images? Run the agent and start creating!** 🎨✨
