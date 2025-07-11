# Brave Search Agent - uAgent Adapter

This directory contains the **Brave Search Agent** for the uAgent A2A Adapter framework. The agent enables web and local search capabilities using the Brave Search API, and can be run as a standalone A2A agent or integrated into a multi-agent system.

## What is the Brave Search Agent?

- **BraveSearchAgentExecutor** (`agent.py`):
  - Handles web, local, and general search queries using the Brave Search API.
  - Supports commands like `WEB:`, `LOCAL:`, `SEARCH:`, and `SUMMARIZE:` for flexible search and summarization.
  - Returns structured, concise results for easy consumption by users or other agents.

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
   ```

3. **Set up environment variables:**
   - Obtain a Brave Search API key from https://search.brave.com/api
   - Create a `.env` file in this directory with:
     ```
     BRAVE_API_KEY=your_brave_api_key_here
     ```

## Running the Brave Search Agent

The main entry point for running the Brave Search Agent is `main.py`.

```bash
python main.py
```

This will:
- Start the Brave Search A2A server (default: http://localhost:10020)
- Start a coordinator agent (default: http://localhost:8200) for routing queries
- Print manifest URLs after startup

## Sample Queries

Send these queries to the coordinator endpoint (default: `http://localhost:8200`) or directly to the Brave Search agent endpoint:

### Web Search
```
WEB:Python programming tutorials
WEB:Latest news on electric vehicles
```

### Local Search
```
LOCAL:pizza near Central Park
LOCAL:bookstores in San Francisco
```

### General Search
```
SEARCH:AI breakthroughs in 2024
SEARCH:Best productivity apps
```

### Summarize Search Results
```
SUMMARIZE:AI advancements 2025
SUMMARIZE:climate change effects
```

## Troubleshooting

- **Missing API Key:**
  - Ensure your `.env` file contains a valid `BRAVE_API_KEY`.
- **Port already in use:**
  - Change the `port` in the agent config in `main.py` if you see an address-in-use error.
- **Dependency issues:**
  - Double-check you are using the correct pip install commands above.
- **Agent not responding:**
  - Check logs for errors, ensure all environment variables are set, and that the server is running.

## Extending / Adding New Search Features

To add new search features or customize the agent:
1. Edit or extend `agent.py` by subclassing `AgentExecutor` and implementing new command handlers.
2. Update the agent configuration in `main.py` if you add new agent types.
3. Restart the system.

## File Structure

- `agent.py`      - Brave Search agent executor logic
- `function.py`   - Orchestrator and entry point for running the agent
- `readme.md`     - This documentation file

## Example `.env` file

```
BRAVE_API_KEY=your_brave_api_key_here
```

## Notes
- The agent uses the Brave Search API for both web and local search.
- For more details, see the main project README or the Brave Search API documentation.

---

For any issues or questions, please refer to the main project documentation or open an issue.
