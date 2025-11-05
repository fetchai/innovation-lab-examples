# Currency Conversion Agent

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![langgraph](https://img.shields.io/badge/langgraph-FF6B6B) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4)

## 🎯 Currency Conversion Agent: Your Real-Time Forex Assistant

Need accurate, up-to-date currency exchange rates? The Currency Conversion Agent is a specialized AI assistant built with LangGraph, designed to provide real-time currency conversion and exchange rate information. Using the Frankfurter API, this agent delivers accurate forex data with a conversational interface.

### What it Does

This agent helps you quickly get current exchange rates between any supported currencies. Simply ask for conversion rates, and it will fetch live data and provide clear, formatted responses.

## ✨ Key Features

* **Real-Time Exchange Rates** - Live forex data from Frankfurter API
* **Multi-Currency Support** - Supports all major currencies (USD, EUR, GBP, JPY, etc.)
* **Historical Rates** - Access exchange rates for specific dates
* **Task Management** - Stateful conversations with task tracking
* **LangGraph Integration** - Built with LangGraph for robust agent orchestration
* **Structured Responses** - Clear status indicators (completed, input_required, error)
* **Memory Management** - Maintains conversation context across queries

## 🔧 Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Google API key for Gemini (or OpenAI API key)

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd langgraph
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# Google API Key (required for Gemini model)
GOOGLE_API_KEY=your_google_api_key_here

# Model source (google or openai)
model_source=google

# Optional: For OpenAI instead of Google
# model_source=openai
# API_KEY=your_openai_api_key_here
# TOOL_LLM_NAME=gpt-4
# TOOL_LLM_URL=https://api.openai.com/v1
```

**How to get API keys:**
- **Google API Key**: Get it from [Google AI Studio](https://aistudio.google.com/app/apikey)
- **OpenAI API Key**: Get it from [OpenAI Platform](https://platform.openai.com/api-keys)

### How to Start

Run the application with:

```bash
python currency.py
```

The agent will start on the following ports:
- **Currency Specialist**: `http://localhost:10000`
- **A2A Server**: `http://localhost:9999`
- **uAgent Coordinator**: `http://localhost:8100`

**To stop the application:** Press `CTRL+C` in the terminal

### Example Queries

```plaintext
What is the current exchange rate from USD to EUR?
```

```plaintext
Convert 100 USD to GBP
```

```plaintext
What was the exchange rate between JPY and EUR on 2024-01-15?
```

### Expected Response Format

```
Looking up the exchange rates...
Processing the exchange rates...

The current exchange rate from USD to EUR is 0.92.
For 100 USD, you would get approximately 92 EUR.

Status: completed
```

## 🔧 Technical Architecture

- **Framework**: uAgents + A2A Protocol + LangGraph
- **AI Models**: Google Gemini 2.0 Flash (or OpenAI GPT-4)
- **Agent Framework**: LangGraph with ReAct pattern
- **Memory**: Built-in MemorySaver for conversation context
- **API**: Frankfurter API for exchange rate data
- **Task Management**: A2A task states (working, input_required, completed)

## 📊 Component Overview

### 1. **Currency Agent (`agent.py`)**
- LangGraph-based agent with ReAct pattern
- Single tool: `get_exchange_rate`
- Structured response format with status indicators
- System instructions for currency-only queries

### 2. **Agent Executor (`agent_executor.py`)**
- Implements A2A AgentExecutor interface
- Manages task lifecycle and state updates
- Streams agent responses to event queue
- Handles errors and user input requirements

### 3. **Main System (`currency.py`)**
- Sets up A2A agent configuration
- Manages coordinator and server lifecycle
- Configures ports and endpoints

## 🔄 Agent Flow

1. **User Query** → Received by coordinator
2. **Task Creation** → New task created with unique context ID
3. **Agent Processing**:
   - Status: "working" - Looking up exchange rates
   - Tool Call: Fetches data from Frankfurter API
   - Status: "working" - Processing the exchange rates
4. **Response Generation**:
   - Structured response with status
   - Artifact creation with conversion result
5. **Task Completion** → Task marked as complete

## 🆘 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure your Google API key is correctly set in the `.env` file
2. **Port Conflicts**: Check if ports 10000, 8100, or 9999 are already in use. Kill them with:
   ```bash
   lsof -ti:10000,8100,9999 | xargs kill -9
   ```
3. **Dependency Issues**: Run `pip install -r requirements.txt` to ensure all packages are installed
4. **Frankfurter API Errors**: The Frankfurter API is free and doesn't require authentication. If errors occur, check your internet connection.

### Performance Tips

- The agent is optimized for currency-only queries
- For off-topic queries, the agent will politely decline
- Historical rates are available for dates since 1999
- Supported currencies: Check [Frankfurter API docs](https://www.frankfurter.app/docs/)

## 📈 Use Cases

- **Travel Planning**: Get exchange rates before international trips
- **Financial Analysis**: Track currency trends over time
- **E-commerce**: Calculate product prices in different currencies
- **Investment Research**: Monitor forex rates for trading decisions
- **Expense Management**: Convert receipts and invoices

## 🧪 Testing the Agent

### Test via A2A Protocol

```python
# Send a message to the agent
curl -X POST http://localhost:9999/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the exchange rate from USD to EUR?"
  }'
```

### Test Directly

```python
from currency_agent_system.agent import CurrencyAgent

agent = CurrencyAgent()
async for response in agent.stream("Convert 100 USD to EUR", "test-context"):
    print(response)
```

## 🔒 Supported Currencies

The agent supports all currencies available in the Frankfurter API, including:
- USD (US Dollar)
- EUR (Euro)
- GBP (British Pound)
- JPY (Japanese Yen)
- CHF (Swiss Franc)
- CAD (Canadian Dollar)
- AUD (Australian Dollar)
- And many more...

## 📚 Additional Resources

- **Frankfurter API**: [https://www.frankfurter.app](https://www.frankfurter.app)
- **LangGraph Documentation**: [https://langchain-ai.github.io/langgraph/](https://langchain-ai.github.io/langgraph/)
- **A2A Protocol**: [https://a2a-protocol.org/latest/](https://a2a-protocol.org/latest/)

## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [LangGraph](https://github.com/langchain-ai/langgraph)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)
