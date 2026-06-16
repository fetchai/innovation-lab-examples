# Pharmacy Locator Agent

- **Category:** `Getting Started`, `Integration`
- **Difficulty:** Beginner

A beginner-friendly uAgent that helps users find nearby pharmacies. It uses the [ASI:One LLM](https://asi1.ai/) to parse natural language location queries and connects to the free [OpenStreetMap Overpass API](https://overpass-api.de/) to fetch real-world data.

## Prerequisites

- Python 3.10+
- An API key for [ASI:One](https://asi1.ai/) (to parse user intent/locations).

> **Note:** The OpenStreetMap Overpass API is completely free and public, requiring no API key.

## Installation

Navigate to the agent directory and install dependencies:

```bash
cd pharmacy-locator-agent
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set up your environment variables:

```bash
cp .env.example .env
```

Edit the `.env` file and add your `ASI_ONE_API_KEY`.

## Running the Agent

Start the agent:

```bash
python agent.py
```

The agent will print its address in the console.

## Expected Output

You can interact with the agent via the Agentverse chat interface or a local chat script.

**User:** `Find me a pharmacy near London`

**Agent:** 
```
Searching for pharmacies in **London**... 🔍

Here are 5 pharmacies I found in London:

1. **Boots**
   📍 Address: Oxford Street London
   📞 Phone: +44 20 1234 5678
   🕒 Hours: Mo-Su 08:00-22:00

...

*Data provided by OpenStreetMap (Overpass API)*
```
