# Architecture Overview

## System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         User                                 │
│                      (ASI One UI)                            │
└────────────────────┬───────────────────────────────────────┘
                     │
                     │ ChatMessage
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Fetch.ai Network                            │
│              (Decentralized Protocol)                        │
└────────────────────┬───────────────────────────────────────┘
                     │
                     │ Message Routing
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Your Gemini Agent                               │
│                (Agentverse)                                  │
│                                                              │
│  ┌────────────────────────────────────────────────┐        │
│  │  1. Receive ChatMessage                         │        │
│  │  2. Send Acknowledgement                        │        │
│  │  3. Load Conversation History                   │        │
│  │  4. Generate Response with Gemini               │◄───┐   │
│  │  5. Store Context                               │    │   │
│  │  6. Send ChatResponse                           │    │   │
│  └────────────────────────────────────────────────┘    │   │
└──────────────────────────────────────────────────────────┼──┘
                                                           │
                                                           │ API Call
                                                           │
                                                           ▼
                                            ┌──────────────────────────┐
                                            │  Google Gemini API       │
                                            │  (gemini-1.5-flash)      │
                                            │                          │
                                            │  • Natural Language      │
                                            │  • Context Understanding │
                                            │  • Response Generation   │
                                            └──────────────────────────┘
```

## Component Details

### 1. User Interface (ASI One)
- Web-based chat interface
- Connects to Fetch.ai network
- Sends ChatMessage protocol messages
- Receives ChatResponse messages

### 2. Fetch.ai Network
- Decentralized message routing
- Agent discovery and addressing
- Protocol enforcement
- Message delivery guarantees

### 3. Your Gemini Agent
**Core Components:**

#### Message Handler (`handle_chat_message`)
```python
Input:  ChatMessage(text, msg_id, timestamp)
Output: ChatResponse(text, agent_address, timestamp)

Steps:
1. Validate message
2. Send acknowledgement
3. Retrieve conversation history
4. Call Gemini API
5. Process response
6. Update history
7. Send response back
```

#### Conversation Storage
```python
{
  "sender_address": [
    {"role": "user", "text": "Hello"},
    {"role": "model", "text": "Hi! How can I help?"},
    ...
  ]
}
```
- Maintains last 10 messages per user
- Provides context for Gemini
- Stored in agent's local storage

#### Gemini Integration
```python
model = genai.GenerativeModel('gemini-1.5-flash')
chat = model.start_chat(history=conversation_history)
response = chat.send_message(user_message)
```

### 4. Google Gemini API
- **Model**: gemini-1.5-flash
- **Purpose**: Fast, cost-effective text generation
- **Capabilities**:
  - Natural language understanding
  - Context-aware responses
  - Multi-turn conversations
  - Instruction following

## Data Flow

### Request Path
```
User Input
  ↓
ASI One encodes to ChatMessage
  ↓
Fetch.ai network routes to agent
  ↓
Agent receives and validates
  ↓
Agent retrieves conversation context
  ↓
Agent calls Gemini API with context
  ↓
Gemini processes and generates response
  ↓
Agent formats as ChatResponse
  ↓
Fetch.ai network routes back
  ↓
ASI One displays to user
```

### Context Management
```
First Message: No history → Fresh conversation
Later Messages: History included → Contextual responses

History Format:
[
  {"role": "user", "parts": ["message 1"]},
  {"role": "model", "parts": ["response 1"]},
  {"role": "user", "parts": ["message 2"]},
  ...
]
```

## Deployment Architecture

### Local Development
```
Your Machine
├── Agent Process (port 8000)
├── Gemini API calls
└── Local storage
```

### Agentverse Production
```
Agentverse Infrastructure
├── Containerized agent
├── Managed networking
├── Persistent storage
├── Auto-scaling
├── Monitoring
└── Marketplace listing
```

## Protocol Specifications

### ChatMessage
```python
class ChatMessage:
    text: str           # User's message
    msg_id: str         # Unique identifier
    timestamp: datetime # When sent
```

### ChatResponse
```python
class ChatResponse:
    text: str           # Agent's response
    agent_address: str  # Agent identifier
    timestamp: datetime # When sent
```

### ChatAcknowledgement
```python
class ChatAcknowledgement:
    acknowledged_msg_id: str  # ID of acknowledged message
    timestamp: datetime       # When acknowledged
```

## Performance Considerations

### Response Time
- Network latency: ~50-200ms
- Gemini API: ~500-2000ms
- Total: ~1-3 seconds typical

### Scalability
- Stateless design (context in storage)
- Horizontal scaling on Agentverse
- API rate limits: Plan accordingly

### Cost Optimization
- Use Flash model (cheaper, faster)
- Limit history to last 10 messages
- Cache common responses
- Set appropriate token limits

## Security

### API Key Management
- Never commit keys to git
- Use environment variables
- Agentverse secrets storage
- Rotate keys periodically

### Message Validation
- Verify sender addresses
- Sanitize user input
- Rate limiting (recommended)
- Error handling

## Monitoring

### Key Metrics
- Total messages processed
- Average response time
- Error rate
- API usage/costs
- Active conversations

### Logging
```python
ctx.logger.info("Message received")
ctx.logger.error("API error occurred")
ctx.storage.set("total_messages", count)
```

## Extension Points

### Easy Customizations
1. **System Prompt** - Change personality/role
2. **Model Selection** - Try gemini-pro for better quality
3. **Temperature** - Adjust creativity (0.0-1.0)
4. **History Length** - Keep more/less context
5. **Response Format** - Add markdown, formatting

### Advanced Extensions
1. **Multimodal** - Add image handling
2. **Function Calling** - Integrate tools/APIs
3. **RAG** - Add knowledge base
4. **Multi-Agent** - Coordinate with other agents
5. **MCPs** - Add real-world actions
