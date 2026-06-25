# 🎯 Gemini Task Manager Agent

A Fetch.ai uAgent that takes any goal or task from the user and uses
Google Gemini to break it down into a clear, actionable step-by-step plan.

## What It Does

- User sends a goal via chat (e.g. "Learn ML in 60 days")
- Agent uses Gemini 2.0 Flash to generate a numbered action plan
- Returns a clean, motivational step-by-step breakdown
- Runs on Fetch.ai's uAgents chat protocol

## Tech Stack

- `uagents` — agent runtime + chat protocol
- `google-genai` — Gemini 2.0 Flash LLM
- `python-dotenv` — environment variable management

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:
GEMINI_API_KEY=your_gemini_api_key_here

Get your free Gemini API key at: https://aistudio.google.com/app/apikey

### 3. Run the agent

```bash
python agent.py
```

## Example

**Input:**
Learn machine learning in 60 days

**Output:**
🎯 Task Plan for: 'Learn machine learning in 60 days'

Week 1-2: Learn Python basics and NumPy/Pandas
Week 3-4: Study core ML concepts (regression, classification)

...


## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | ✅ Yes |

## Author

- **Bhargav Rao Mahankali** — GSSoC 2026 Contributor
- GitHub: [@Bhargav-Devv](https://github.com/Bhargav-Devv)
