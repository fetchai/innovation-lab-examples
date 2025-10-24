# 📸 Image Input Guide for ASI One

This guide explains how to send images to your Claude Vision Agent through ASI One.

## The Challenge

ASI One uses the Fetch.ai chat protocol, which has specific ways of handling images. We need to properly receive and process images sent through this protocol.

## Solution Overview

Our agent handles **3 methods** of image input:

### ✅ Method 1: ResourceContent (Primary)
**How it works:**
- ASI One attaches images as `ResourceContent` objects
- Contains a URI (URL or storage reference)
- Agent downloads and processes the image

**Implementation:**
```python
for item in msg.content:
    if isinstance(item, ResourceContent):
        # Extract the image URI
        image_uri = item.resource.uri
        
        # Download image
        image_bytes = await download_image_from_uri(image_uri, ctx)
        
        # Convert to base64 for Claude
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')
```

### ✅ Method 2: HTTP/HTTPS URLs in Text
**How it works:**
- User includes image URL in their message
- Agent detects and downloads the URL
- Processes as normal

**Example message:**
```
Analyze this image: https://example.com/photo.jpg
```

### ✅ Method 3: Base64 (Future Enhancement)
**How it works:**
- Image encoded as base64 string in message
- Agent decodes and processes
- Useful for programmatic access

## How to Test

### Testing via ASI One Web Interface

#### Option A: Upload Image Feature
If ASI One supports file uploads:

1. Open ASI One at [asi.one](https://asi.one)
2. Find your agent using its address
3. Look for image upload button 📎 or 🖼️
4. Upload an image
5. Optionally add text: "What do you see?"
6. Send!

#### Option B: Send Image URL
1. Find an image online (e.g., from Imgur, your website)
2. Copy the direct image URL
3. Send to your agent:
   ```
   Describe this image: https://i.imgur.com/example.jpg
   ```

### Test Images You Can Use

Here are some publicly accessible test images:

**1. Sample Photos:**
```
https://picsum.photos/800/600
(Random sample image)
```

**2. Text/OCR Test:**
```
https://via.placeholder.com/400x200/0066cc/ffffff?text=Hello+World
(Image with text)
```

**3. Common Test Image:**
```
https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg
(Wikipedia cat photo)
```

## ASI One Protocol Details

### ChatMessage Structure

When ASI One sends an image, the message looks like:

```python
ChatMessage(
    timestamp=datetime.now(timezone.utc),
    msg_id=uuid4(),
    content=[
        TextContent(
            type="text",
            text="What's in this image?"
        ),
        ResourceContent(
            type="resource",
            resource_id="img_12345",
            resource=Resource(
                uri="https://example.com/image.jpg",
                metadata={
                    "mime_type": "image/jpeg",
                    "size": 245678
                }
            )
        )
    ]
)
```

### Our Agent's Response

```python
# 1. Extract both text and image
user_text = "What's in this image?"
image_uri = "https://example.com/image.jpg"

# 2. Download image
image_bytes = requests.get(image_uri).content

# 3. Send to Claude
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode()
                }
            },
            {
                "type": "text",
                "text": user_text
            }
        ]
    }]
)

# 4. Send response back
await ctx.send(sender, create_text_chat(response.content[0].text))
```

## Testing Without ASI One

### Option 1: Command Line Test (Simple)

Create a test file with an image URL:

```python
# test_image.py
import requests
import base64
from anthropic import Anthropic

client = Anthropic(api_key="your-key")

# Download image
image_url = "https://picsum.photos/800/600"
image_data = requests.get(image_url).content
image_base64 = base64.b64encode(image_data).decode()

# Analyze with Claude
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_base64
                }
            },
            {
                "type": "text",
                "text": "What do you see in this image?"
            }
        ]
    }]
)

print(response.content[0].text)
```

Run:
```bash
python test_image.py
```

### Option 2: Direct Agent Message

Send a message directly to your agent:

```python
# send_test_message.py
from uagents import Agent
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent, ResourceContent, Resource
from datetime import datetime, timezone
from uuid import uuid4

# Your test client
client = Agent(name="test_client", seed="test-seed")

@client.on_event("startup")
async def send_test(ctx):
    vision_agent = "agent1q..."  # Your vision agent address
    
    msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(
                type="text",
                text="What's in this image?"
            ),
            ResourceContent(
                type="resource",
                resource_id="test_img",
                resource=Resource(
                    uri="https://picsum.photos/800/600",
                    metadata={"mime_type": "image/jpeg"}
                )
            )
        ]
    )
    
    await ctx.send(vision_agent, msg)

client.run()
```

## Troubleshooting Image Input

### Issue: "No image received"

**Possible causes:**
1. ASI One not sending ResourceContent
2. URI is malformed
3. Image not properly attached

**Debug steps:**
```python
# Add logging to see what's received
for item in msg.content:
    ctx.logger.info(f"Received content type: {type(item)}")
    if isinstance(item, ResourceContent):
        ctx.logger.info(f"Image URI: {item.resource.uri}")
```

### Issue: "Can't download image"

**Possible causes:**
1. URL is not public
2. Requires authentication
3. Network issue
4. Invalid URL

**Solutions:**
- Test URL in browser first
- Use publicly accessible images
- Check agent logs for download errors
- Try a different image host

### Issue: "Claude can't see the image"

**Possible causes:**
1. Image not properly encoded
2. Wrong media type
3. Image corrupted
4. Format not supported

**Debug:**
```python
# Verify image before sending to Claude
ctx.logger.info(f"Image size: {len(image_bytes)} bytes")
ctx.logger.info(f"Media type: {get_image_media_type(image_bytes)}")
ctx.logger.info(f"Base64 length: {len(img_base64)} chars")
```

## Advanced: Custom Image Sources

### Handle Agentverse Storage

```python
async def download_from_agentverse(asset_id: str, api_token: str):
    """Download from Agentverse external storage"""
    url = f"https://agentverse.ai/v1/storage/{asset_id}"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    response = requests.get(url, headers=headers)
    return response.content
```

### Handle Data URLs

```python
def parse_data_url(data_url: str):
    """Parse data:image/jpeg;base64,... format"""
    if data_url.startswith('data:'):
        # Extract media type and data
        header, data = data_url.split(',', 1)
        media_type = header.split(':')[1].split(';')[0]
        
        if 'base64' in header:
            image_bytes = base64.b64decode(data)
            return image_bytes, media_type
    
    return None, None
```

## Best Practices

### 1. Always Validate Images
```python
def validate_image(image_bytes: bytes) -> tuple[bool, str]:
    """Validate image before processing"""
    # Check size
    if len(image_bytes) > 5 * 1024 * 1024:
        return False, "Image too large (max 5MB)"
    
    # Check format
    media_type = get_image_media_type(image_bytes)
    if media_type not in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
        return False, f"Unsupported format: {media_type}"
    
    return True, "OK"
```

### 2. Provide Helpful Error Messages
```python
if not image_bytes:
    error_msg = """❌ Couldn't download the image.

Please try:
- Sending a public image URL
- Using a different image host
- Checking the image is accessible
- Uploading the image directly (if supported)
"""
    await ctx.send(sender, create_text_chat(error_msg))
```

### 3. Handle Timeouts
```python
try:
    response = requests.get(uri, timeout=10)  # 10 second timeout
except requests.Timeout:
    ctx.logger.error("Image download timed out")
```

### 4. Cache Images (Optional)
```python
# Store in agent storage to avoid re-downloading
image_cache = ctx.storage.get("image_cache") or {}
if uri in image_cache:
    image_bytes = base64.b64decode(image_cache[uri])
else:
    image_bytes = await download_image_from_uri(uri)
    image_cache[uri] = base64.b64encode(image_bytes).decode()
    ctx.storage.set("image_cache", image_cache)
```

## Example Conversations

### Example 1: Simple Analysis
```
User: [Uploads cat photo]
      What animal is this?

Agent: This is a domestic cat. It appears to be an orange/ginger tabby cat...
```

### Example 2: Detailed Description
```
User: [Uploads landscape]
      Describe this scene in detail

Agent: This is a scenic landscape photograph featuring...
       - Mountains in the background with snow-capped peaks
       - A lake in the foreground with crystal clear water
       - Pine trees framing the sides
       - Golden hour lighting creating warm tones
       - Reflections of the mountains in the water
```

### Example 3: Text Extraction
```
User: [Uploads sign photo]
      What does the sign say?

Agent: The sign reads: "Welcome to Central Park
       Open Daily: 6 AM - 1 AM
       Please Keep Our Park Clean"
```

## Summary

**Key Takeaways:**

1. ✅ Agent handles multiple image input methods
2. ✅ ResourceContent is the primary ASI One method
3. ✅ HTTP URLs work as fallback
4. ✅ Images are downloaded and converted to base64
5. ✅ Claude API receives properly formatted image data

**Testing Strategy:**

1. Start with public image URLs (easiest)
2. Test ASI One upload feature
3. Try different image types and sizes
4. Monitor logs for debugging

**Next Steps:**

- Run the agent
- Test with various images
- Experiment with different prompts
- Build specialized vision applications!

---

**Questions?** Check the main README or agent logs for debugging! 📸✨
