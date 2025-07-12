# YouTube Summarizer Agent

An AI-powered agent that summarizes YouTube videos by extracting and processing closed captions/transcripts. Built with the A2A (Agent-to-Agent) framework and uAgents.

## 🚀 Features

- **Video Summarization**: Automatically extracts transcripts from YouTube videos and generates concise summaries
- **Multi-language Support**: Tries multiple languages (en, en-US, en-GB, auto) to find available transcripts
- **Intelligent Fallbacks**: Provides helpful error messages when transcripts aren't available
- **Real-time Processing**: Streams responses for better user experience
- **A2A Integration**: Built on the Agent-to-Agent protocol for seamless communication

## 📋 Prerequisites

- Python 3.10+
- OpenAI API key
- Internet connection for YouTube transcript access

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd youtube_summarizer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your OpenAI API key:**
   ```bash
   # Option 1: Set environment variable
   export OPENAI_API_KEY="your_openai_api_key_here"
   
   # Option 2: Create .env file
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   ```

## 🏃‍♂️ Quick Start

1. **Start the YouTube Summarizer system:**
   ```bash
   python main.py
   ```

2. **The system will start multiple services:**
   - YouTube Summarizer Agent on port 10030
   - A2A Coordinator on port 8300
   - A2A Server on port 9999

3. **Send a request to summarize a YouTube video:**
   ```
   Summarize this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

## 🏗️ Architecture

### Core Components

#### `main.py` - System Orchestrator
- **YoutubeSummarizerSystem**: Main system class that coordinates all components
- **Agent Configuration**: Sets up the A2A agent with specialties and examples
- **Server Management**: Starts individual A2A servers and coordinator

#### `agent.py` - YouTube Processing Agent
- **YoutubeSummarizerAgent**: Core agent that handles video processing
- **Transcript Extraction**: Multi-language transcript fetching from YouTube
- **AI Summarization**: Uses OpenAI GPT-4o to generate concise summaries
- **Error Handling**: Graceful fallbacks when transcripts aren't available

#### `agent_executor.py` - A2A Integration
- **SummarizerAgentExecutor**: Bridges the agent with A2A framework
- **Event Management**: Handles task status updates and streaming responses
- **Response Formatting**: Structures responses for A2A protocol

#### uAgent Adapter - Cross-Agent Communication
- **SingleA2AAdapter**: Enables communication with other uAgents
- **Mailbox Integration**: Connects to AgentVerse.ai for message routing
- **Agent Registration**: Registers with Almanac API for discoverability
- **Protocol Support**: Implements AgentChatProtocol for standardized messaging

## 🔧 Configuration

### Agent Settings
```python
# In main.py - Agent Configuration
A2AAgentConfig(
    name="youtube_summarizer",
    description="AI Agent for summarizing YouTube videos using closed captions",
    url="http://localhost:10030",
    port=10030,
    specialties=["youtube", "video summarization", "transcription", "content analysis"],
    priority=3,
    examples=[
        "Summarize this YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "Provide a summary of the key points in this tutorial video",
    ],
)
```

### Supported Video Formats
- YouTube watch URLs: `https://www.youtube.com/watch?v=VIDEO_ID`
- YouTube short URLs: `https://youtu.be/VIDEO_ID`

## 📊 How It Works

### Video Processing Flow
1. **URL Parsing**: Extracts video ID from YouTube URLs
2. **Transcript Fetching**: Attempts to get transcripts in multiple languages
3. **AI Processing**: Sends transcript to OpenAI GPT-4o for summarization
4. **Response Streaming**: Returns formatted summary with captions preview

### uAgent Communication Flow
1. **Message Reception**: uAgent receives messages via AgentVerse.ai mailbox
2. **Task Routing**: A2A coordinator routes requests to the YouTube summarizer agent
3. **Processing**: Agent processes the video and generates summary
4. **Response Delivery**: Results are sent back through the uAgent network
5. **Acknowledgment**: Message acknowledgment is sent to confirm completion

### Transcript Detection Process
```python
# Multi-language fallback strategy
languages = ['en', 'en-US', 'en-GB', 'auto']
for lang in languages:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        return transcript
    except NoTranscriptFound:
        continue
```

## 🚨 Error Handling

### Common Scenarios
- **No Transcript Available**: Provides detailed explanation and suggestions
- **Invalid URL**: Returns helpful error message
- **Private/Restricted Videos**: Explains why access is limited
- **Network Issues**: Graceful timeout handling

### Error Response Example
```
No transcript available for "Video Title" (ID: VIDEO_ID). This could be because:
• The video has no captions/subtitles
• The video is private or restricted
• The video has been removed

Please try a different YouTube video with available captions.
```

## 🔌 API Endpoints

### A2A Protocol Endpoints
- **Agent Card Server**: `http://localhost:10030`
- **A2A Server**: `http://localhost:9999`

### uAgent Adapter Endpoints
- **uAgent Coordinator**: `http://localhost:8300`
- **uAgent Address**: `agent1qd26k3l7cddgfny53z4dh9tk32cjq3ksn0ry5pf85slanwd5xqft7wvnymc`
- **Mailbox**: `https://agentverse.ai` (for cross-agent communication)

### Agent Inspector
Access the agent inspector at:
```
https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8300&address=agent1qd26k3l7cddgfny53z4dh9tk32cjq3ksn0ry5pf85slanwd5xqft7wvnymc
```

## 📝 Usage Examples

### Basic Video Summarization
```
Input: Summarize this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Output: [Concise summary of video content with key points]
```

### Educational Content
```
Input: Provide a summary of the key points in this tutorial video
Output: [Structured summary with main concepts and takeaways]
```

## 🛡️ Security Considerations

- **API Key Management**: Store OpenAI API keys securely (use environment variables)
- **Rate Limiting**: Be mindful of YouTube API and OpenAI rate limits
- **Content Privacy**: Only processes publicly available video transcripts

## 🔄 Development

### Adding New Features
1. **Extend Transcript Sources**: Add support for other video platforms
2. **Enhance Summarization**: Implement different summary styles (bullet points, timeline, etc.)
3. **Add Language Support**: Support for non-English video summarization

### Testing
```bash
# Test agent initialization
python -c "from agent import YoutubeSummarizerAgent; print('✅ Agent ready')"

# Test system startup
python -c "from main import YoutubeSummarizerSystem; print('✅ System ready')"
```

## 📦 Dependencies

### Core Dependencies
- `uagents-adapter`: A2A framework integration and uAgent communication
- `a2a-sdk`: Agent-to-Agent SDK
- `autogen`: OpenAI agent framework
- `youtube-transcript-api`: YouTube transcript extraction
- `python-dotenv`: Environment variable management
- `uagents`: Core uAgent framework for decentralized agent communication

### Development Dependencies
- `uvicorn`: ASGI server
- `requests`: HTTP client for video info fetching

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For issues and questions:
1. Check the error logs for detailed information
2. Ensure your OpenAI API key is valid
3. Verify the YouTube video has available captions
4. Check network connectivity

## 🔮 Roadmap

- [ ] Support for YouTube playlists
- [ ] Multiple summary formats (bullet points, timeline, etc.)
- [ ] Integration with YouTube Data API for enhanced metadata
- [ ] Support for other video platforms (Vimeo, etc.)
- [ ] Batch processing capabilities
- [ ] Custom summary length preferences
