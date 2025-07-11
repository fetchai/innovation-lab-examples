# uAgent Adapter - Agents Directory

This directory contains specialized agent executors for use with the uAgent A2A Adapter framework. Each agent is designed for a specific domain (research, coding, analysis) and can be orchestrated together in a multi-agent system.

## Agents Overview

- **ResearchAgentExecutor** (`research_agent.py`):
  - Specializes in information gathering, research, and analysis.
  - Uses environment variables for API configuration.
- **CodingAgentExecutor** (`coding_agent.py`):
  - Specializes in code generation, debugging, and code review.
  - Uses a system prompt for software engineering tasks.
- **AnalysisAgentExecutor** (`analysis_agent.py`):
  - Specializes in data analysis, insights, and forecasting.
  - Handles structured analysis commands.

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
   - Copy `.env.example` to `.env` and fill in your API keys and configuration.
   - For the research agent, set `ASI1_API_KEY` and optionally `ASI1_API_URL` and `ASI1_MODEL` in your `.env` file.

## Running the Multi-Agent System

The main entry point for running all agents together is `main.py`.

```bash
python main.py
```

This will:
- Set up and start individual A2A servers for each agent (research, coding, analysis)
- Start a coordinator agent that routes queries to the appropriate specialist
- Print the manifest URLs for each agent after startup


## Sample Queries

You can use these sample queries to test the system by sending them to the coordinator (or directly to the respective agent endpoints):

### Research Agent
```
Research the impact of renewable energy adoption in Europe.
What are the latest advancements in quantum computing?
Summarize the key findings from recent AI ethics research.
```

### Coding Agent
```
CODE:python:merge two sorted lists
DEBUG:def add(a, b): return a + b  # but it sometimes returns the wrong result
REVIEW:def factorial(n): return 1 if n==0 else n*factorial(n-1)
OPTIMIZE:def slow_sum(lst): total = 0; for i in lst: total += i; return total
EXPLAIN:def quicksort(arr): ...
TEST:def is_prime(n): ...
```

### Analysis Agent
```
ANALYZE:Q2 sales data for trends
TRENDS:website traffic data for the last 6 months
COMPARE:Product A vs Product B sales performance
METRICS:customer churn data
INSIGHTS:employee satisfaction survey results
FORECAST:next quarter revenue
```

## Troubleshooting

- **Missing API Key:**
  - Ensure your `.env` file contains a valid `ASI1_API_KEY` for the research agent.
- **Port already in use:**
  - Change the `port` in the agent config if you see an address-in-use error.
- **Dependency issues:**
  - Double-check you are using the correct pip install commands above.
- **Agent not responding:**
  - Check logs for errors, ensure all environment variables are set, and that the server is running.

## Extending / Adding New Agents

To add a new agent:
1. Create a new file (e.g., `my_agent.py`) in this directory.
2. Subclass `AgentExecutor` and implement the `execute` method.
3. Add your agent to the orchestrator in main.py`:
   - Import your executor
   - Add a new `A2AAgentConfig` and executor instance to the lists
4. Restart the system.

## File Structure

- `research_agent.py` - Research specialist agent
- `coding_agent.py`   - Coding specialist agent
- `analysis_agent.py` - Data analysis specialist agent
- `readme.md`         - This documentation file

## Example `.env` file

```
# For ResearchAgentExecutor
ASI1_API_KEY=your_asi1_api_key_here
ASI1_API_URL=https://api.asi1.ai/v1/chat/completions
ASI1_MODEL=asi1-mini
```

## Notes
- Ensure your API keys are valid and have sufficient quota.
- The agents use both `requests` (sync) and `httpx` (async) for HTTP calls.
- The multi-agent system uses the `A2AAgentConfig` and `a2a_servers` utilities from the adapter for orchestration.
- For more details, see the main project README.

---

For any issues or questions, please refer to the main project documentation or open an issue.
