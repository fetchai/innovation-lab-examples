# Claude Vision Agent

Analyze and understand images using Claude 3.5 Sonnet's vision capabilities on Fetch.ai! 👁️

## What You'll Build

An AI agent that:
- ✅ Analyzes images with Claude's vision model
- ✅ Provides detailed descriptions of what it sees
- ✅ Answers questions about images
- ✅ Extracts text from images (OCR)
- ✅ Handles multiple image input methods
- ✅ Works with ASI One interface

## 🎯 Key Challenge: Image Input from ASI One

**The Problem:** How do we send images through the Fetch.ai chat protocol to our agent?

**The Solution:** We handle multiple input methods:

### 1. ResourceContent (Primary Method)
ASI One can send images as `ResourceContent` in the chat protocol:

```python
# Agent receives this structure
ResourceContent(
    type="resource",
    resource_id="image_123",
    resource=Resource(
        uri="https://example.com/image.jpg",  # or agent-storage://...
        metadata={"mime_type": "image/jpeg"}
    )
)
```

Our agent:
1. Detects `ResourceContent` in the message
2. Downloads the image from the URI
3. Converts to base64
4. Sends to Claude's API

### 2. Direct HTTP URLs
Users can send image URLs in text:
```
Analyze this image: https://example.com/photo.jpg
```

### 3. Base64 (Future)
Support for inline base64 encoded images.

## Prerequisites

- Python 3.9+
- Anthropic API key (same one from Guide 01)
- Completed Guide 01 (Basic Claude Agent)

## Quick Start

### Step 1: Install Dependencies

```bash
cd anthropic-quickstart/02-claude-vision-agent

# Use the same virtual environment or create a new one
source ../01-basic-claude-agent/venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### Step 2: Use Your Existing API Key

The agent will automatically use your `ANTHROPIC_API_KEY` from the root `.env` file!

### Step 3: Run the Agent

```bash
python claude_vision_agent.py
```
### You will see an inspector link, which you can open on your browser and connect the mailbox.

You should see:

```
👁️ Starting Claude Vision Agent...
📍 Agent address: agent1q...
✅ Claude Vision API configured
   Using model: claude-3-5-sonnet-20241022

🎯 Agent Features:
   • Image analysis with Claude 3.5 Sonnet Vision
   • Detailed scene descriptions
   • Text extraction (OCR)
   • Object identification
   • Visual Q&A
   • Multiple image input methods

📸 Supported Image Formats:
   • JPEG, PNG, WebP, GIF
   • Max size: 5MB per image
   • URLs and base64 encoding

✅ Agent is running! Send images via ASI One to analyze them.
```

## Testing the Agent

### Via ASI One

1. Go to [https://asi1.ai](https://asi1.ai)
2. Find your agent using the address shown in the terminal
3. Send images with questions!

**Method 1: Upload Image (if supported)**
- Use ASI One's file upload feature
- Add optional text: "What's in this image?"

**Method 2: Send Image URL**
```
Analyze this image: https://i.imgur.com/example.jpg
```

**Method 3: Send image + specific question**
```
[Upload image]
What colors do you see? Is there any text?
```

### Example Queries

**General Description:**
```
What do you see in this image?
```

**Specific Questions:**
```
How many people are in this image?
What's the mood or atmosphere?
Describe the setting and environment
```

**Text Extraction:**
```
Extract all text from this image
What does the sign say?
```

**Object Identification:**
```
What objects can you identify?
Is there a cat or dog in this image?
```

**Creative Analysis:**
```
What story does this image tell?
Describe this image as if you're a poet
```

## How It Works

### Image Processing Flow

```
User (ASI One)
    ↓
    ↓ Sends ChatMessage with ResourceContent
    ↓
Agent receives message
    ↓
    ↓ Extracts ResourceContent.uri
    ↓
Download image from URI
    ↓
    ↓ Convert to bytes
    ↓
Encode as base64
    ↓
    ↓ Build Claude API request
    ↓
Claude Vision API
    ↓
    ↓ Analyzes image + text
    ↓
Returns description
    ↓
    ↓ Send back via chat protocol
    ↓
User sees response
```

### Code Breakdown

**1. Detect Image Content:**
```python
for item in msg.content:
    if isinstance(item, ResourceContent):
        # Found an image!
        image_uri = item.resource.uri
```

**2. Download Image:**
```python
async def download_image_from_uri(uri: str):
    if uri.startswith('http'):
        response = requests.get(uri)
        return response.content
    # Handle other URI schemes...
```

**3. Prepare for Claude:**
```python
# Convert to base64
img_base64 = base64.b64encode(image_bytes).decode('utf-8')

# Build message content
message_content = [{
    "type": "image",
    "source": {
        "type": "base64",
        "media_type": "image/jpeg",
        "data": img_base64
    }
}, {
    "type": "text",
    "text": user_text
}]
```

**4. Call Claude API:**
```python
response = client.messages.create(
    model=MODEL_NAME,
    messages=[{
        "role": "user",
        "content": message_content
    }]
)
```

## Claude Vision Capabilities

### What Claude Can See

- ✅ **Objects**: People, animals, vehicles, furniture, etc.
- ✅ **Scenes**: Indoor/outdoor, time of day, weather
- ✅ **Text**: Read signs, documents, handwriting (OCR)
- ✅ **Colors**: Identify and describe color schemes
- ✅ **Emotions**: Facial expressions, mood
- ✅ **Actions**: What people/objects are doing
- ✅ **Composition**: Layout, framing, artistic elements
- ✅ **Details**: Small elements, patterns, textures

### What It Can Do

- 📝 **Describe**: Comprehensive image descriptions
- 🔍 **Analyze**: Detailed analysis of specific elements
- 📖 **Read**: Extract text (OCR)
- 🏷️ **Identify**: Name objects, brands, landmarks
- 💭 **Interpret**: Explain meaning, context, symbolism
- ❓ **Answer**: Specific questions about the image
- 🎨 **Critique**: Art/photo analysis
- 🔢 **Count**: Number of objects/people

## Image Format Support

### Supported Formats
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **WebP** (.webp)
- **GIF** (non-animated, first frame only)

### Size Limits
- **Max file size**: 5MB per image
- **Recommended**: 1MB or less for faster processing
- **Resolution**: Works with various resolutions

### Quality Tips
- Higher resolution = more details Claude can see
- Good lighting helps with accuracy
- Clear, focused images work best
- Text should be legible

## Use Cases

### 1. Content Moderation
```python
# Check images for inappropriate content
"Does this image contain any inappropriate content?"
```

### 2. E-commerce
```python
# Product descriptions
"Describe this product in detail for an online listing"
"What condition is this item in?"
```

### 3. Accessibility
```python
# Alt text generation
"Provide alt text for this image for screen readers"
```

### 4. Education
```python
# Visual learning
"Explain what's happening in this diagram"
"What historical period does this photo represent?"
```

### 5. Healthcare (General)
```python
# General observations (not medical advice!)
"Describe what you see in this image"
```

### 6. Real Estate
```python
# Property descriptions
"Describe this room and its features"
"What's the style of this interior?"
```

### 7. Social Media
```python
# Content creation
"Suggest a caption for this image"
"What hashtags would work for this photo?"
```

## Advanced Features

### Multi-Image Analysis

Send multiple images in one message:

```python
# Agent handles multiple ResourceContent items
images = []
for item in msg.content:
    if isinstance(item, ResourceContent):
        images.append(download_image(item.resource.uri))

# All images sent to Claude together
```

Ask comparative questions:
```
Compare these two images. What's different?
```

### Conversation Context

The agent maintains context, so you can have multi-turn conversations:

```
User: [Sends image]
Agent: "I see a dog in a park..."

User: "What breed is it?"
Agent: "Based on the features, it appears to be a Golden Retriever..."

User: "What's it doing?"
Agent: "The dog is playing with a ball..."
```

## Troubleshooting

### "No image received"

**Check:**
- Image was properly attached/linked
- URI is accessible
- Format is supported (JPEG, PNG, WebP, GIF)
- File size under 5MB

### "Error downloading image"

**Solutions:**
- Verify URL is publicly accessible
- Check internet connection
- Try a different image host
- Ensure no authentication required

### "Image processing error"

**Try:**
- Converting to JPEG or PNG
- Reducing file size
- Re-uploading the image
- Using a different image

### Claude can't see details

**Improve:**
- Use higher resolution images
- Ensure good lighting
- Make text larger/clearer
- Reduce compression

## Cost Considerations

### Pricing (Claude 3.5 Sonnet with Vision)

- **Input**: $3 per 1M tokens
- **Output**: $15 per 1M tokens
- **Images**: ~1,600 tokens per image (approximate)

### Cost Per Request

**Typical image analysis:**
- Image: ~1,600 tokens
- Text prompt: ~50 tokens
- Response: ~300 tokens
- **Total cost**: ~$0.005 per analysis (half a cent!)

**Very affordable for:**
- Development and testing
- Personal projects
- Small to medium applications

## Customization

### Change System Prompt

Make Claude focus on specific aspects:

```python
SYSTEM_PROMPT = """You are a product photography expert.

When analyzing images:
- Focus on product features and quality
- Describe colors, materials, and condition
- Suggest improvements for better photos
- Provide e-commerce listing descriptions
"""
```

### Adjust Model Parameters

```python
# More detailed responses
MAX_TOKENS = 4096

# More creative descriptions
TEMPERATURE = 0.9

# More focused, factual
TEMPERATURE = 0.3
```

### Add Image Filters

```python
def should_process_image(image_bytes: bytes) -> bool:
    """Filter images before processing"""
    # Check file size
    if len(image_bytes) > 5 * 1024 * 1024:  # 5MB
        return False
    
    # Check format
    media_type = get_image_media_type(image_bytes)
    if media_type not in ALLOWED_TYPES:
        return False
    
    return True
```

## Next Steps

1. ✅ **Test with different images** - Try various content types
2. 🎨 **Customize prompts** - Specialize for your use case
3. 🔧 **Add features** - Image storage, history, comparisons
4. 🚀 **Deploy** - Make it publicly accessible
5. 🔗 **Integrate** - Connect with other agents/services

## Resources

- [Claude Vision Documentation](https://docs.anthropic.com/claude/docs/vision)
- [Image Best Practices](https://docs.anthropic.com/claude/docs/vision#image-best-practices)
- [Fetch.ai Chat Protocol](https://fetch.ai/docs)
- [ASI One Platform](https://asi.one)

## What's Next?

👉 **Guide 03: Function Calling Agent** - Let Claude use tools and APIs! (Coming Soon)

---

**Ready to give your agent eyes? Start sending images!** 👁️✨
