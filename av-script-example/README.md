# Agentverse Script Example 🤖

A complete example demonstrating how to create an agent with Agentverse registration, chat protocol implementation, and ASI One API integration.

## Features

- **Agentverse Registration**: Automatically registers with Agentverse for discoverability
- **Chat Protocol**: Full chat protocol implementation with session management
- **ASI One Integration**: Uses ASI One API for AI-powered responses
- **Multi-turn conversations**: Supports session-based chat interactions
- **Error Handling**: Robust error handling for API calls and registration

## Prerequisites

- Python 3.10+
- ASI One API key
- Agentverse API key (optional, for registration)
- Agent seed phrase

## Installation

### Local Setup

```bash
pip install uagents uagents-core requests python-dotenv
```

### Environment Variables

Copy the example environment file and update with your values:

```bash
cp .env.example .env
# Then edit .env with your API keys and seed phrase
```

Or set the environment variables directly:

```bash
export AGENT_SEED_PHRASE=your-agent-seed-phrase-here
export AGENTVERSE_KEY=your-agentverse-api-key-here
export ASI_ONE_API_KEY=your-asi-one-api-key-here
export AGENT_PORT=8006  # Optional, defaults to 8006
# HOSTING_ENDPOINT=http://your-domain.com:8006  # Optional, for production
```

Get your credentials from:
- **Agentverse API Key**: https://agentverse.ai/
- **ASI One API Key**: https://asi1.ai/


## Usage

### Run Locally

```bash
python agent.py
```

The agent will start on `http://0.0.0.0:8006`

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"What is agentic AI?"
"Explain machine learning"
"Hello, how are you?"
"What are the benefits of using agents?"
```

## Architecture




## Project Structure

```
av-script-example/
├── agent.py           # Main agent file with all functionality
├── .env.example       # Example environment variables
└── README.md          # This file
```

## Code Components

### 1. Agent Registration

```python
register_chat_agent(
    "Example Agent",
    agent._endpoints[0].url,
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=AGENTVERSE_KEY,
        agent_seed_phrase=SEED_PHRASE,
    ),
    readme=README,
    description="Agent description"
)
```

### 2. Chat Protocol Handlers

- **StartSessionContent**: Handles session start
- **TextContent**: Processes text messages and generates responses
- **EndSessionContent**: Handles session end
- **ChatAcknowledgement**: Acknowledges received messages

### 3. ASI One API Integration

```python
def call_asi_one_api(user_message: str) -> str:
    url = "https://api.asi1.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ASI_ONE_API_KEY}"
    }
    data = {
        "model": "asi1-mini",
        "messages": [{"role": "user", "content": user_message}]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]
```

## Technology Stack

- **uAgents**: Chat protocol communication and agent-to-agent messaging
- **ASI One API**: AI-powered responses using asi1-mini model
- **Agentverse**: Agent discovery and registration platform
- **Python Requests**: HTTP client for API calls

## Error Handling

The example includes error handling for:
- Missing API keys
- API request failures
- Agentverse registration failures
- Unexpected content types

## Customization

You can customize the agent by:

1. **Changing the agent name**: Update `UAGENT_NAME` and registration name
2. **Modifying responses**: Edit the `handle_message` function
3. **Adding custom logic**: Integrate your own business logic in the message handler
4. **Using different AI models**: Change the model in `call_asi_one_api` function

## Troubleshooting

### Agent not registering with Agentverse
- Check that `AGENTVERSE_KEY` and `AGENT_SEED_PHRASE` are set correctly
- Verify your Agentverse API key is valid
- Check agent logs for registration errors

### ASI One API not working
- Verify `ASI_ONE_API_KEY` is set correctly
- Check your API key is valid and has credits
- Review error messages in logs

### Agent not responding
- Ensure the agent is running and accessible
- Check that the chat protocol is properly included
- Verify network connectivity

## License

This is an example script for educational purposes.

