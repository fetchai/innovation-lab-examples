# News Summarizer Agent

A beginner-friendly Fetch.ai agent that fetches top news headlines for any topic using [NewsAPI](https://newsapi.org/) and summarizes them using the [ASI:One](https://asi1.ai/) LLM.

## What It Does

1. You provide a topic (e.g. "AI", "climate", "sports")
2. The agent fetches the top 5 latest headlines from NewsAPI
3. The headlines are sent to ASI:One LLM for summarization
4. A short, readable summary is printed to the terminal

## Tech Stack

- Python 3.10+
- NewsAPI - free tier, no credit card required
- ASI:One - Fetch.ai's LLM API
- requests - HTTP calls
- python-dotenv - environment variable management

## Setup

### 1. Clone the repo

git clone https://github.com/fetchai/innovation-lab-examples.git
cd innovation-lab-examples/news-summarizer-agent

### 2. Install dependencies

pip install -r requirements.txt

### 3. Set up environment variables

cp .env.example .env

Edit .env and fill in your API keys:

ASI1_API_KEY=your_asi1_api_key_here
NEWS_API_KEY=your_news_api_key_here

- Get a free NewsAPI key at: https://newsapi.org/register
- Get your ASI:One API key at: https://asi1.ai/

### 4. Run the agent

python agent.py

When prompted, enter a topic like AI, climate, or sports.

## Demo

![Demo output](demo.png)

## Environment Variables

| Variable | Description |
|---|---|
| ASI1_API_KEY | Your ASI:One API key from asi1.ai |
| NEWS_API_KEY | Your NewsAPI key from newsapi.org |

## Project Structure

news-summarizer-agent/
├── agent.py          # Main agent logic
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── demo.png          # Demo screenshot
└── README.md         # This file
