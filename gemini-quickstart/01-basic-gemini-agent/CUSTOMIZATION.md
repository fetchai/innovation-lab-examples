# Customization Guide

Make this agent your own! Here are easy ways to customize it for your use case.

## 🎭 Change the Personality

Edit the `SYSTEM_PROMPT` in `basic_gemini_agent.py`:

### Example: Technical Tutor
```python
SYSTEM_PROMPT = """You are a patient and knowledgeable programming tutor.

Your teaching style:
- Break down complex topics into simple steps
- Use analogies and examples
- Encourage questions
- Provide code examples when relevant
- Celebrate progress and learning

Focus areas: Python, JavaScript, web development, algorithms
"""
```

### Example: Creative Writer
```python
SYSTEM_PROMPT = """You are a creative writing assistant specializing in storytelling.

Your approach:
- Help brainstorm plot ideas and characters
- Suggest vivid descriptions and metaphors
- Provide constructive feedback on writing
- Inspire creativity while respecting the author's vision
- Share writing tips and techniques

Specialties: Fiction, screenwriting, poetry, world-building
"""
```

### Example: Business Coach
```python
SYSTEM_PROMPT = """You are an experienced business advisor and startup mentor.

Your expertise:
- Strategic planning and goal setting
- Market analysis and competitor research
- Fundraising and pitch deck review
- Team building and leadership
- Growth tactics and marketing

Communication style: Direct, actionable, data-driven
"""
```

## 🎛️ Adjust AI Behavior

### Make Responses More Creative
```python
model = genai.GenerativeModel(
    'gemini-1.5-flash',
    generation_config={
        'temperature': 0.9,      # ↑ More creative (was 0.7)
        'top_p': 0.95,
        'top_k': 40,
    }
)
```

### Make Responses More Focused
```python
generation_config={
    'temperature': 0.3,      # ↓ More deterministic
    'top_p': 0.8,            # ↓ More focused
    'top_k': 20,             # ↓ Fewer options
}
```

### Longer Responses
```python
generation_config={
    'max_output_tokens': 2048,  # ↑ Allow longer responses (was 1024)
}
```

### Shorter Responses
```python
generation_config={
    'max_output_tokens': 512,   # ↓ Keep it concise
}
```

## 🧠 Use Better Model (Higher Quality)

```python
# Instead of gemini-1.5-flash, use:
model = genai.GenerativeModel('gemini-1.5-pro')  # Better but slower
```

**Trade-offs:**
- ✅ Higher quality responses
- ✅ Better reasoning
- ❌ Slower (2-4x)
- ❌ More expensive (10x cost)

## 💾 Extend Conversation Memory

```python
# Keep more context (default is 5 messages)
for h in history[-10:]:  # Keep last 10 instead of 5
    chat_history.append(...)

# Or keep all history (be careful with token limits!)
for h in history:
    chat_history.append(...)
```

## 🎨 Format Responses

### Add Markdown Formatting
```python
SYSTEM_PROMPT = """...
Format your responses using markdown:
- Use **bold** for emphasis
- Use `code` for technical terms
- Use bullet points for lists
- Use ## headers for sections
"""
```

### Add Emojis
```python
SYSTEM_PROMPT = """...
Use relevant emojis to make responses engaging:
- 🎯 for goals/targets
- 💡 for ideas
- ✅ for completed items
- 🚀 for exciting developments
"""
```

### Structured Responses
```python
SYSTEM_PROMPT = """...
Always structure responses as:
1. **Summary** - Brief overview
2. **Details** - In-depth explanation
3. **Action Items** - What to do next
4. **Resources** - Links or references (if relevant)
"""
```

## 🔧 Add Custom Features

### Welcome Message
```python
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("Agent started")
    ctx.storage.set("welcome_sent", {})

@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # Check if this is first message from user
    welcome_sent = ctx.storage.get("welcome_sent") or {}
    
    if sender not in welcome_sent:
        welcome = "👋 Welcome! I'm your AI assistant. How can I help you today?"
        await ctx.send(sender, ChatResponse(text=welcome, ...))
        welcome_sent[sender] = True
        ctx.storage.set("welcome_sent", welcome_sent)
    
    # Continue with normal processing...
```

### Rate Limiting
```python
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # Track message count per user
    user_counts = ctx.storage.get("user_message_counts") or {}
    count = user_counts.get(sender, 0)
    
    if count > 20:  # Max 20 messages per session
        await ctx.send(sender, ChatResponse(
            text="You've reached the message limit. Please start a new session.",
            ...
        ))
        return
    
    user_counts[sender] = count + 1
    ctx.storage.set("user_message_counts", user_counts)
    
    # Continue with normal processing...
```

### Typing Indicator (Simulated)
```python
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # Send acknowledgement immediately
    await ctx.send(sender, ChatAcknowledgement(...))
    
    # Optional: Send "thinking" message
    await ctx.send(sender, ChatResponse(
        text="🤔 Thinking...",
        ...
    ))
    
    # Generate actual response
    response = chat_session.send_message(msg.text)
    
    # Send real response
    await ctx.send(sender, ChatResponse(text=response.text, ...))
```

## 📊 Add Analytics

```python
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # Track various metrics
    stats = ctx.storage.get("stats") or {
        "total_messages": 0,
        "unique_users": set(),
        "avg_message_length": 0,
        "topics": {}
    }
    
    stats["total_messages"] += 1
    stats["unique_users"].add(sender)
    stats["avg_message_length"] = (
        (stats["avg_message_length"] * (stats["total_messages"] - 1) + len(msg.text)) 
        / stats["total_messages"]
    )
    
    ctx.storage.set("stats", stats)
    ctx.logger.info(f"Stats: {stats['total_messages']} messages from {len(stats['unique_users'])} users")
```

## 🌐 Multi-Language Support

```python
SYSTEM_PROMPT = """You are a multilingual AI assistant.

Language support:
- Detect the user's language automatically
- Respond in the same language
- Support: English, Spanish, French, German, Chinese, Japanese, etc.

Always maintain the same language as the user unless they explicitly request a change.
"""
```

## 🎯 Domain-Specific Knowledge

### Add Context in Prompt
```python
SYSTEM_PROMPT = """You are a medical information assistant.

Knowledge base:
- Common symptoms and conditions
- General health advice
- Medication information (general)
- When to see a doctor

IMPORTANT: 
- Never diagnose conditions
- Always recommend consulting healthcare professionals
- Provide information, not prescriptions
"""
```

### Load External Knowledge
```python
# Load FAQ or knowledge base on startup
@agent.on_event("startup")
async def startup(ctx: Context):
    with open('knowledge_base.txt', 'r') as f:
        kb = f.read()
    ctx.storage.set("knowledge_base", kb)

@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    kb = ctx.storage.get("knowledge_base")
    
    # Include in prompt
    enhanced_prompt = f"{SYSTEM_PROMPT}\n\nKnowledge Base:\n{kb}"
    # Use enhanced_prompt with Gemini...
```

## 🔐 Add Safety Filters

```python
# Configure Gemini safety settings
from google.generativeai.types import HarmCategory, HarmBlockThreshold

model = genai.GenerativeModel(
    'gemini-1.5-flash',
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
)
```

## 🎪 Quick Customization Checklist

- [ ] Change `SYSTEM_PROMPT` for your use case
- [ ] Adjust `temperature` for creativity level
- [ ] Set `max_output_tokens` for response length
- [ ] Choose model (`flash` vs `pro`)
- [ ] Configure conversation history length
- [ ] Add welcome message
- [ ] Set up rate limiting
- [ ] Add custom analytics
- [ ] Configure safety settings
- [ ] Test with real users!

## 💡 Pro Tips

1. **Start Simple** - Make one change at a time and test
2. **Test Thoroughly** - Try edge cases and different user types
3. **Monitor Costs** - Track API usage as you customize
4. **Get Feedback** - Let real users guide your customizations
5. **Iterate** - Continuously improve based on usage data

## 🚀 Ready to Deploy?

After customizing:
1. Test locally thoroughly
2. Update agent name and seed
3. Deploy to Agentverse
4. Share with users
5. Collect feedback
6. Iterate!
