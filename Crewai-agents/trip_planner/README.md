# Trip Planner

A multimodal AI trip planning system that combines CrewAI agents with uAgents framework to create detailed travel itineraries based on user preferences.

## Overview

This project demonstrates an AI-powered trip planning system that:
- Processes natural language trip requests
- Analyzes destination options based on user criteria
- Creates in-depth city guides with local expertise
- Generates comprehensive travel itineraries with daily plans, recommendations and budget breakdowns

## Architecture

The system consists of multiple specialized agents working together:

1. **Trip Planner Crew AI Agent (main_uagents.py)**: Coordinates the entire planning process
2. **City Selection Expert**: Analyzes and selects the best city based on specific criteria
3. **Local Expert**: Creates detailed city guides with insider knowledge
4. **Amazing Travel Concierge**: Expands the guide into a full travel itinerary

## Prerequisites

- Python 3.11
- OpenAI API key
- [Agentverse](https://agentverse.ai/) account for agent communication

## Installation

1. Clone this repository
2. Create and activate a virtual environment:
   ```
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
   
5. Set up environment variables by copying the example file:
   ```
   cp .env.example .env
   ```
6. Edit `.env` file to add your API keys and settings

## Usage

### Start the Trip Planner Agent

```
python main_uagents.py #change the name of agent and description according to you
```

This will start the main trip planner agent with the specified address. You should see information about the agent's address and server details in the console.

### Start the Client Agent

```
python client_agent.py # check the address of main_uagent if it is same as main uagent's address
```

This starts a client agent that can send trip planning requests to the main agent.

### Example Request

Send a natural language request like:
```
Plan a trip for me from london to paris starting on 22nd of April 2025 and I am interested in mountains beaches and history
```

The system extracts the following parameters:
- Origin: London
- Cities: Paris
- Date Range: starting on 22nd of April 2025
- Interests: mountains, beaches, history

### Response

The system provides a detailed 7-day itinerary including:
- Daily activities
- Accommodation recommendations
- Dining options
- Budget breakdown
- Packing suggestions
- Practical travel tips

## Components

- **main_uagents.py**: Main agent setup and crew coordination
- **client_agent.py**: Client agent for interacting with the trip planner
- **trip_agents.py**: Definitions for specialist trip planning agents
- **trip_tasks.py**: Task definitions for each agent
- **tools/**: Utility functions and tools for the agents
