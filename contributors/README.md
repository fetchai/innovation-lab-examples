# Gemin# Gemini-Powered Research Agent

This example demonstrates how to integrate Google's Gemini API (`google-genai`) within the Fetch.ai `uagents` framework to create an autonomous research and summarization agent.

## Architecture
This example utilizes two agents:

1. **Gemini Agent (`gemini_agent.py`)**: Acts as the backend processor. It listens for `ResearchRequest` messages, queries the Gemini 2.5 Flash model, and returns a structured `ResearchResponse`.
2. **User Agent (`user_agent.py`)**: Acts as the client. It triggers the request on startup and logs the AI-generated summary upon receipt.

## Prerequisites
Ensure you have Python 3.10+ installed.

Install the required dependencies:
```bash
python -m pip install uagents google-genai python-dotenv
```

## Setup Instructions

### 1. API Key Setup
Create a `.env` file in this directory and add your Google Gemini API key:
```text
GEMINI_API_KEY=your_api_key_here
```

### 2. Start the Gemini Agent
Open a terminal and run the Gemini agent:
```bash
python gemini_agent.py
```
*Note: Look at the startup logs and copy the Agent address (it starts with `agent1...`).*

### 3. Configure the User Agent
Open `user_agent.py` and replace the `TARGET_AGENT_ADDRESS` variable with the address you just copied.

### 4. Trigger the Research
Open a second terminal and run the user agent:
```bash
python user_agent.py
```

You will see the asynchronous message transfer and the final AI-generated summary printed in your terminal!