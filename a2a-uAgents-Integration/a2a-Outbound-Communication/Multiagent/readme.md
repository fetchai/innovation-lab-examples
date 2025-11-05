# Multi-Agent Orchestrator System

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4) ![multiagent](https://img.shields.io/badge/multiagent-FF6B6B)

## 🎯 Multi-Agent System: Your Intelligent Task Routing Assistant

Need specialized AI assistance for different types of tasks? The Multi-Agent Orchestrator System is an intelligent coordination platform that automatically routes your queries to the most appropriate specialist agent. Using advanced LLM-based routing with fallback keyword matching, this system ensures your questions reach the expert that can best answer them.

### What it Does

This system intelligently coordinates three specialized AI agents (Research, Coding, and Analysis) and automatically routes your queries to the right specialist based on the content and intent of your request.

## ✨ Key Features

* **Intelligent Routing** - LLM-powered query routing with keyword matching fallback
* **Three Specialized Agents** - Research, Coding, and Data Analysis specialists
* **Automatic Coordination** - No need to choose which agent to use
* **Multi-Port Architecture** - Each agent runs on its own dedicated port
* **Mailbox Integration** - Connects to AgentVerse for message routing
* **Priority-Based Selection** - Agents have configurable priority levels
* **Fallback Strategy** - Graceful degradation to keyword matching if LLM routing fails

## 🔧 Setup

### Prerequisites

- Python 3.10 or higher (3.10.14 recommended)
- pip (Python package manager)
- ASI1 API key for LLM routing

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd Multiagent
```

2. **Set Python version (if using pyenv):**
```bash
pyenv local 3.10.14
```

3. **Install dependencies:**
```bash
pip install uagents-adapter[a2a]
pip install a2a-sdk[all]
pip install python-dotenv
pip install httpx
pip install requests
```

4. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# ASI1 API Key (required for LLM routing and agent processing)
ASI1_API_KEY=your_asi1_api_key_here

# Optional: Model and URL configuration
MODEL=asi1-mini
BASE_URL=https://api.asi1.ai/v1/chat/completions

# Optional: Individual agent API configuration
ASI1_API_URL=https://api.asi1.ai/v1/chat/completions
ASI1_MODEL=asi1-mini
```

**How to get API keys:**
- **ASI1 API Key**: Sign up at [ASI1.ai](https://asi1.ai)

### How to Start

Run the application with:

```bash
python main.py
```

Or if you have Python version issues:

```bash
~/.pyenv/versions/3.10.14/bin/python main.py
```

The system will start on the following ports:
- **Research Specialist**: `http://localhost:10020`
- **Coding Specialist**: `http://localhost:10022`
- **Analysis Specialist**: `http://localhost:10023`
- **Coordinator**: `http://localhost:8200`

**To stop the application:** Press `CTRL+C` in the terminal

## 🤖 Agent Specializations

### 1. Research Specialist (Port 10020)
**Specialties:** research, analysis, fact-finding, summarization

**Best for:**
- Information gathering on any topic
- Market research and trend analysis
- Academic literature reviews
- Fact-checking and verification
- Executive summaries

**Example Queries:**
```
Research the latest developments in quantum computing and summarize the key breakthroughs from 2024.
What are the current trends in renewable energy adoption in Europe?
Analyze the impact of AI on healthcare diagnostics.
```

### 2. Coding Specialist (Port 10022)
**Specialties:** coding, debugging, programming

**Best for:**
- Code generation in any language
- Debugging and error fixing
- Code review and optimization
- Algorithm implementation
- Unit test creation

**Example Queries:**
```
Write a Python function that implements a binary search algorithm with error handling and unit tests.
Debug this code: def add(a, b): return a + b
Review and optimize this sorting function.
Create a REST API endpoint for user authentication.
```

### 3. Analysis Specialist (Port 10023)
**Specialties:** data analysis, insights, forecasting

**Best for:**
- Data trend analysis
- Statistical insights
- Performance metrics
- Growth forecasting
- Comparative analysis

**Example Queries:**
```
Analyze the following sales data and provide insights on growth trends: Q1: $120K, Q2: $145K, Q3: $168K, Q4: $195K
Compare the performance metrics between Product A and Product B.
Forecast next quarter's revenue based on historical data.
```

## 🔄 How Routing Works

### LLM-Based Routing (Primary)
1. Query is sent to the coordinator
2. LLM analyzes the query intent and context
3. LLM selects the most appropriate specialist
4. Query is forwarded to the selected agent

### Keyword Matching (Fallback)
1. If LLM routing fails, system uses keyword matching
2. Keywords are matched against agent specialties
3. Scoring system with priority multipliers
4. Highest scoring agent is selected

### Fallback Agent
- If no suitable agent is found, defaults to Research Specialist
- Ensures all queries receive a response

## 🔧 Technical Architecture

- **Framework**: uAgents + A2A Protocol
- **AI Models**: ASI1 Mini for routing and processing
- **Routing**: LLM-based with keyword fallback
- **Communication**: HTTP-based A2A protocol
- **Coordination**: MultiA2AAdapter for intelligent routing

## 📊 System Components

### 1. **Main Orchestrator (`main.py`)**
- Sets up all three specialist agents
- Configures A2A servers for each agent
- Creates the MultiA2AAdapter coordinator
- Manages system lifecycle

### 2. **Research Agent (`agents/research_agent.py`)**
- Conducts thorough research
- Provides structured, factual information
- Cites sources when possible
- Delivers executive summaries

### 3. **Coding Agent (`agents/coding_agent.py`)**
- Generates clean, documented code
- Follows best practices and conventions
- Includes error handling
- Provides explanatory comments

### 4. **Analysis Agent (`agents/analysis_agent.py`)**
- Analyzes data patterns and trends
- Generates actionable insights
- Creates visualizations (when applicable)
- Delivers strategic recommendations

## 🆘 Troubleshooting

### Common Issues

1. **Import Error for MultiA2AAdapter**:
   - Check Python version: `python --version` (should be 3.10.x)
   - If using Python 3.13+, switch to 3.10.14:
   ```bash
   pyenv local 3.10.14
   ```
   - Or use full path: `~/.pyenv/versions/3.10.14/bin/python main.py`

2. **Port Conflicts**: Check if ports are already in use. Kill them with:
   ```bash
   lsof -ti:10020,10022,10023,8200 | xargs kill -9
   ```

3. **Missing API Key Error**: Ensure `ASI1_API_KEY` is set in your `.env` file

4. **LLM Routing Failed (404)**: The `BASE_URL` in `.env` should be the full endpoint:
   ```
   BASE_URL=https://api.asi1.ai/v1/chat/completions
   ```

5. **Missing `os` module error**: Fixed in latest version - ensure you have the updated agent files

### Performance Tips

- LLM routing provides better accuracy but requires API calls
- Keyword matching is faster but less intelligent
- Configure agent priorities in `main.py` to influence routing decisions
- Each agent has independent processing, so they can handle concurrent requests

## 📈 Use Cases

- **Development Teams**: Route coding questions to coding specialist, research to research specialist
- **Data Analysis**: Automatically send data queries to analysis specialist
- **Research Projects**: Comprehensive information gathering with automatic specialist routing
- **Multi-Domain Queries**: System intelligently breaks down and routes complex multi-part queries

## 🔒 Configuration Options

### In `main.py`:

**Agent Configuration:**
```python
A2AAgentConfig(
    name="agent_name",
    description="Agent description",
    url="http://localhost:PORT",
    port=PORT,
    specialties=["specialty1", "specialty2"],
    priority=3  # 1-5, higher = more likely to be selected
)
```

**Routing Strategy:**
- `"llm"` - Uses LLM for intelligent routing (recommended)
- `"keyword_match"` - Uses keyword matching only (faster, less accurate)

## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)
