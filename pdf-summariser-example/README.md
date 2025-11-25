# PDF Summariser Agent

A Fetch.ai uAgent that accepts PDF files as input, extracts text content, and provides intelligent summaries using the ASI:One API. This agent demonstrates how to build agents that can process PDF attachments through the Agent chat protocol.

## Features

- ✅ Accepts PDF files via chat protocol
- ✅ Extracts text from PDFs using multiple libraries (pdfplumber, PyPDF2)
- ✅ Generates intelligent summaries using ASI:One API
- ✅ Runs as a Mailbox Agent (local with Agentverse integration)
- ✅ Handles multiple PDFs in a single message
- ✅ Robust error handling and fallback mechanisms

## What You'll Build

A document processing agent that:
- Receives PDF attachments from users via ASI:One 
- Extracts text content from PDF documents
- Generates concise summaries using AI
- Responds with summarized content

## Prerequisites

- Python 3.9+
- ASI:One API key
- 5-10 minutes

## Step 1: Get Your ASI:One API Key

1. Visit [ASI:One](https://asi1.ai)
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy your API key

## Step 2: Install Dependencies

```bash
# Navigate to the project directory
cd pdf-summariser-example

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

## Step 3: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
ASI_ONE_API_KEY=your_asi_one_api_key_here
```

**Note:** The agent uses the ASI:One API for summarization. Make sure your API key has sufficient credits.

## Step 4: Understanding the Agent Structure

The agent consists of three main components:

### 1. Agent Setup (`agent.py`)

```python
from uagents import Agent
from chat_proto import chat_proto

agent = Agent(name="PDF Summariser Agent", port=8005, mailbox=True)

# Include the chat protocol to handle text and PDF contents
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
```

**Key Points:**
- `mailbox=True` enables Mailbox Agent mode (local agent connected to Agentverse)
- `port=8005` sets the local server port
- `publish_manifest=True` makes the agent discoverable on Agentverse

### 2. Chat Protocol (`chat_proto.py`)

Handles incoming messages and processes PDF resources:
- Receives `ChatMessage` with PDF attachments
- Downloads PDFs from Agentverse storage or URI
- Extracts text using utility functions
- Sends summaries back to the user

### 3. Utility Functions (`utils.py`)

Contains PDF processing logic:
- `extract_text_from_pdf()` - Extracts text using pdfplumber (preferred) or PyPDF2 (fallback)
- `get_pdf_text()` - Processes content items and extracts PDF text
- `summarize_text()` - Calls ASI:One API to generate summaries

## Step 5: Run Your Agent Locally

```bash
python agent.py
```

You should see output like:

```
INFO:     [PDF Summariser Agent]: Starting agent with address: agent1q...
INFO:     [PDF Summariser Agent]: Agent inspector available at https://Agentverse.ai/inspect/?uri=...
INFO:     [PDF Summariser Agent]: Starting server on http://0.0.0.0:8005 (Press CTRL+C to quit)
INFO:     [PDF Summariser Agent]: Starting mailbox client for https://Agentverse.ai
INFO:     [PDF Summariser Agent]: Mailbox access token acquired
INFO:     [PDF Summariser Agent]: Registration on Almanac API successful
```

## Step 6: Connect to Agentverse

Since this agent uses `mailbox=True`, you need to connect it to Agentverse:

1. **Run your agent locally** (as shown in Step 5)
2. **Click the Inspector URL** from the terminal output (e.g., `https://Agentverse.ai/inspect/?uri=...`)
3. **Click the "Connect" button** in the Inspector UI
4. **Select "Mailbox"** as the connection type
5. **Click "Finish"** to complete the connection

For detailed instructions, refer to the [Mailbox Agents documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents).

Your agent is now connected to Agentverse and can receive messages from other agents and users!

## Step 7: Test Your Agent

### Testing via ASI:One

1. Open [ASI:One](https://asi1.ai)
2. Start a conversation with the agent by typing @agentaddress summarise this PDF and attach a PDF file
3. The agent will extract text and provide a summary



## Adapting This Agent for Your Use Case

This agent serves as a template for building PDF-processing agents. Here's how to customize it:

### 1. Change the Processing Logic

Modify `utils.py` to implement your own PDF processing:

```python
def process_pdf_content(pdf_text: str, logger=None) -> str:
    """
    Custom processing function - replace summarize_text() with your logic
    """
    # Example: Extract specific information
    # Example: Answer questions about the PDF
    # Example: Translate the content
    # Example: Extract structured data
    pass
```

### 2. Modify the Response Format

Update `chat_proto.py` to change how the agent responds:

```python
# Instead of sending a summary, you could:
# - Send structured data
# - Send multiple messages
# - Include metadata
# - Trigger other actions
```

### 3. Add Additional File Types

Extend the agent to handle other document types:

```python
# In chat_proto.py, add support for other MIME types:
if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    # Process .docx files
    pass
elif mime_type == "text/plain":
    # Process .txt files
    pass
```

### 4. Customize the Agent Name and Port

Edit `agent.py`:

```python
agent = Agent(
    name="Your Custom PDF Agent",  # Change name
    port=8006,                      # Change port if needed
    mailbox=True
)
```

### 5. Add Environment Variables

For additional configuration, add to `.env`:

```bash
ASI_ONE_API_KEY=your_key
MAX_PDF_SIZE=10485760  # 10MB in bytes
SUMMARY_LENGTH=500      # Target summary length
```

Then use in your code:

```python
import os
max_size = int(os.getenv("MAX_PDF_SIZE", "10485760"))
```

## Project Structure

```
pdf-summariser-example/
├── agent.py              # Main agent setup and configuration
├── chat_proto.py         # Chat protocol handlers for messages and PDFs
├── utils.py              # PDF extraction and summarization utilities
├── requirements.txt      # Python dependencies
├── README.md             # This file
└── downloads/            # Directory for downloaded PDFs (created at runtime)
```

## Key Components Explained

### PDF Extraction

The agent uses a dual-library approach for robust PDF text extraction:

1. **pdfplumber** (primary) - Better for complex PDFs with tables and formatting
2. **PyPDF2** (fallback) - Simpler library, works for basic PDFs

```python
# From utils.py
def extract_text_from_pdf(pdf_bytes: bytes, logger=None) -> str:
    # Tries pdfplumber first, falls back to PyPDF2
    # Returns page-by-page extracted text
```

### Summarization

Uses ASI:One API with the `asi1-mini` model:

```python
# From utils.py
def summarize_text(text: str, logger=None) -> Optional[str]:
    # Sends text to ASI:One API
    # Returns concise summary
    # Handles errors gracefully
```

## Configuration Options

### PDF Processing

Adjust text extraction behavior in `utils.py`:

```python
# Maximum text length for summarization
max_length = 100000  # Adjust based on model limits

# Summary prompt customization
prompt = f"""Your custom prompt here:
{text_to_summarize}
"""
```

### Agent Settings

Modify agent behavior in `agent.py`:

```python
agent = Agent(
    name="PDF Summariser Agent",
    port=8005,              # Change if port is in use
    mailbox=True,           # Required for Agentverse connection
    # publish_agent_details=True,  # Uncomment to publish on Agentverse
    # readme_path="README.md"       # Uncomment if publishing
)
```

## Troubleshooting

**"ASI_ONE_API_KEY not found"**
- Check your `.env` file exists in the project root
- Verify the variable name is exactly `ASI_ONE_API_KEY`
- Restart your agent after adding the key

**"No PDF extraction library available"**
- Ensure `pdfplumber` or `PyPDF2` is installed: `pip install pdfplumber PyPDF2`
- Check `requirements.txt` includes these packages

**"Failed to download PDF"**
- Check your internet connection
- Verify the PDF resource is accessible
- Check Agentverse storage permissions

**"Agent not responding"**
- Check if port 8005 is available (change port if needed)
- Look for errors in console output
- Verify mailbox connection is established
- Check ASI:One API key is valid and has credits

**"Can't find agent on ASI:One"**
- Wait 1-2 minutes after starting the agent
- Ensure mailbox is connected (check Inspector UI)
- Verify agent is registered on Almanac
- Check agent address is correct

**"PDF extraction failed"**
- The PDF might be corrupted or password-protected
- Try a different PDF file
- Check PDF is not a scanned image (requires OCR)
- Verify PDF is not empty


## Use Case Ideas

Enhance this agent for:
- 📄 **Document Q&A** - Answer questions about PDF content
- 📊 **Data Extraction** - Extract structured data from PDFs
- 🌐 **Multi-language Processing** - Translate and summarize PDFs
- 📝 **Content Analysis** - Analyze and categorize documents
- 🔍 **Search & Retrieval** - Build a PDF search system
- 📚 **Research Assistant** - Process academic papers and research documents
- 💼 **Business Intelligence** - Extract insights from business documents
- 🎓 **Educational Tools** - Summarize textbooks and course materials

## Code Reference

- `agent.py` - Main agent code and configuration
- `chat_proto.py` - Chat protocol implementation
- `utils.py` - PDF processing and summarization utilities
- `requirements.txt` - Python dependencies

## Resources

- [Mailbox Agents Documentation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents) - How to connect mailbox agents to Agentverse
- [Fetch.ai Innovation Lab](https://innovationlab.fetch.ai) - Official documentation and resources
- [Agentverse](https://agentverse.ai) - Agent marketplace and deployment platform
- [ASI:One](https://asi1.ai) - AI platform for agent interactions
- [uAgents Documentation](https://uagents.fetch.ai/docs) - uAgents framework documentation



