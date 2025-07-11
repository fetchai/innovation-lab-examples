# Currency Agent - uAgent Adapter

This directory contains the **Currency Agent** for the uAgent A2A Adapter framework. The agent provides real-time currency conversion and exchange rate information using external APIs, and can be run as a standalone A2A agent or integrated into a multi-agent system.

## What is the Currency Agent?

- **CurrencyAgentExecutor** (`agent_executor.py`):
  - Handles currency conversion and exchange rate queries.
  - Streams results and handles user input requirements.
- **CurrencyAgent** (`agent.py`):
  - Implements the logic for fetching exchange rates using the Frankfurter API and LangChain tools.
  - Responds only to currency-related queries and politely declines unrelated requests.
- **currency.py**:
  - Orchestrator and entry point for running the Currency Agent as an A2A server and coordinator.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd a2a-examples
   ```

2. **Install dependencies:**
   (Recommended: use a virtual environment)
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install "uagents-adapter[a2a]"
   pip install "a2a-sdk[all]"
   pip install langchain-core langchain-google-genai langchain-openai httpx pydantic python-dotenv
   ```

3. **Set up environment variables:**
   - Create a `.env` file in this directory with any required API keys or model settings. Example:
     ```
     # For Google Gemini (default)
     model_source=google
     # For OpenAI (optional)
     # TOOL_LLM_NAME=gpt-3.5-turbo
     # API_KEY=your_openai_api_key
     # TOOL_LLM_URL=https://api.openai.com/v1
     ```

## Running the Currency Agent

The main entry point for running the Currency Agent is `currency.py`.

```bash
python currency.py
```

This will:
- Start the Currency Agent A2A server (default: http://localhost:10000)
- Start a coordinator agent (default: http://localhost:8100) for routing queries
- Print manifest URLs after startup

## Sample Queries

Send these queries to the coordinator endpoint (default: `http://localhost:8100`) or directly to the Currency Agent endpoint:

```
What is the current exchange rate from USD to EUR?
Convert 100 GBP to JPY.
How many Canadian dollars is 50 Euros?
What was the USD to INR rate on 2023-01-01?
I want to know the exchange rate between AUD and CHF.
```

## Troubleshooting

- **Missing or invalid API key:**
  - Ensure your `.env` file contains the correct model source and any required API keys for Google or OpenAI.
- **Port already in use:**
  - Change the `port` in the agent config in `currency.py` if you see an address-in-use error.
- **Dependency issues:**
  - Double-check you are using the correct pip install commands above.
- **Agent not responding:**
  - Check logs for errors, ensure all environment variables are set, and that the server is running.

## Extending / Adding New Features

To add new features or customize the agent:
1. Edit or extend `agent.py` by adding new tools or logic for additional financial queries.
2. Update the agent configuration in `currency.py` if you add new agent types.
3. Restart the system.

## File Structure

- `agent_executor.py` - Currency AgentExecutor logic (A2A interface)
- `agent.py`          - Currency agent logic and tool integration
- `currency.py`       - Orchestrator and entry point for running the agent
- `readme.md`         - This documentation file

## Example `.env` file

```
# For Google Gemini (default)
model_source=google
# For OpenAI (optional)
# TOOL_LLM_NAME=gpt-3.5-turbo
# API_KEY=your_openai_api_key
# TOOL_LLM_URL=https://api.openai.com/v1
```

## Notes
- The agent uses the Frankfurter API for exchange rates and supports both Google Gemini and OpenAI models for reasoning.
- For more details, see the main project README or the Frankfurter API documentation.

---

For any issues or questions, please refer to the main project documentation or open an issue.
