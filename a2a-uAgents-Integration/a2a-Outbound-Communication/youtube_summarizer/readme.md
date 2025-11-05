# YouTube Summarizer Agent

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![autogen](https://img.shields.io/badge/autogen-00ADD8) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4)

## 🎯 YouTube Summarizer Agent: Your AI-Powered Video Summary Assistant

Need to quickly understand YouTube video content without watching the entire video? The YouTube Summarizer Agent is your AI-powered video analysis assistant, designed to extract and summarize YouTube video transcripts. Using advanced AI, this agent delivers concise, structured summaries that capture the key points and insights from any YouTube video.

### What it Does

This agent automatically extracts closed captions from YouTube videos and generates comprehensive summaries, saving you time while ensuring you don't miss important information.

## ✨ Key Features

* **Automatic Transcript Extraction** - Fetches closed captions from YouTube videos
* **Multi-Language Support** - Tries multiple language variants (en, en-US, en-GB, auto)
* **AI-Powered Summarization** - Uses OpenAI GPT-4o for intelligent summaries
* **Structured Output** - Clear, organized summaries with key points
* **Real-time Streaming** - Streams responses for better user experience
* **Error Handling** - Helpful messages when transcripts aren't available
* **A2A Integration** - Seamless communication with other agents

## 🔧 Setup

### Prerequisites

- Python 3.10 or higher (3.10.14 recommended)
- pip (Python package manager)
- OpenAI API key

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd youtube_summarizer
```

2. **Set Python version (if using pyenv):**
```bash
pyenv local 3.10.14
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# OpenAI API Key (required for GPT-4o model)
OPENAI_API_KEY=your_openai_api_key_here
```

**How to get API keys:**
- **OpenAI API Key**: Get it from [OpenAI Platform](https://platform.openai.com/api-keys)

### How to Start

Run the application with:

```bash
python main.py
```

Or if you have Python version issues:

```bash
pyenv shell 3.10.14
python main.py
```

The agent will start on the following ports:
- **YouTube Summarizer Specialist**: `http://localhost:10030`
- **A2A Server**: `http://localhost:9999`
- **uAgent Coordinator**: `http://localhost:8300`

**To stop the application:** Press `CTRL+C` in the terminal

### Example Queries

```plaintext
Summarize this YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

```plaintext
Provide a summary of the key points in this tutorial video: https://youtu.be/VIDEO_ID
```

### Expected Output Structure

```markdown
## Video Summary: {Video Title}

**Video ID**: {VIDEO_ID}

### Key Points:
- {Main point 1}
- {Main point 2}
- {Main point 3}

### Summary:
{Comprehensive summary of the video content, highlighting the main topics, arguments, and conclusions presented in the video}

### Topics Covered:
- {Topic 1}
- {Topic 2}
- {Topic 3}

---
*Summary generated from closed captions*
```

## 🔧 Technical Architecture

- **Framework**: uAgents + A2A Protocol + AutoGen
- **AI Models**: OpenAI GPT-4o
- **Transcript Source**: YouTube Transcript API
- **Communication**: Asynchronous agent processing with streaming
- **Output Format**: Markdown with structured summaries

## 📊 How It Works

### Video Processing Flow
1. **URL Parsing**: Extracts video ID from YouTube URLs
2. **Transcript Fetching**: Attempts to get transcripts in multiple languages (en, en-US, en-GB, auto)
3. **AI Processing**: Sends transcript to OpenAI GPT-4o for intelligent summarization
4. **Response Streaming**: Returns formatted summary with key points
5. **Error Handling**: Provides helpful messages when transcripts aren't available

### Supported URL Formats
- Standard YouTube URLs: `https://www.youtube.com/watch?v=VIDEO_ID`
- YouTube short URLs: `https://youtu.be/VIDEO_ID`
- URLs with additional parameters: `https://www.youtube.com/watch?v=VIDEO_ID&t=123`

## 🆘 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure your OpenAI API key is correctly set in the `.env` file
   - Warning: "The API key specified is not a valid OpenAI format" - Check your key format

2. **Port Conflicts**: Check if ports 10030, 8300, or 9999 are already in use. Kill them with:
   ```bash
   lsof -ti:10030,8300,9999 | xargs kill -9
   ```

3. **Python Version Error**: If you see import errors:
   ```bash
   pyenv shell 3.10.14
   python main.py
   ```

4. **No Transcript Available**: The video may not have captions enabled
   - Try a different video with closed captions
   - Check if the video is public and available

5. **Import Error for autogen**: Install the correct version:
   ```bash
   pip install "pyautogen<0.3"
   ```

6. **YouTubeTranscriptApi Errors**: Ensure correct import:
   - Use: `from youtube_transcript_api import YouTubeTranscriptApi`
   - Not: `from youtube_transcript_api._api import YouTubeTranscriptApi`

### Performance Tips

- Videos with longer transcripts may take more time to summarize
- Ensure stable internet connection for transcript fetching
- OpenAI API rate limits may apply for high-volume usage
- The agent works best with videos that have clear, structured content

## 📈 Use Cases

- **Educational Content**: Quickly understand tutorial and lecture videos
- **Meeting Recordings**: Extract key points from recorded meetings
- **Conference Talks**: Summarize conference presentations and talks
- **Product Reviews**: Get quick summaries of product review videos
- **News Content**: Stay updated with news video summaries
- **Research**: Extract information from research presentation videos

## 🔒 Limitations

- Only works with videos that have closed captions/transcripts enabled
- Requires public videos (private/restricted videos not supported)
- Summary quality depends on transcript accuracy
- Language support limited to languages supported by YouTube transcripts
- OpenAI API costs apply for summarization

## 📚 Response Format

Each summary includes:
- **Video Title** and ID
- **Key Points** extracted from the content
- **Comprehensive Summary** of main topics
- **Topics Covered** list
- **Closed Captions Preview** (optional)

## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [Microsoft AutoGen](https://github.com/microsoft/autogen)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)
