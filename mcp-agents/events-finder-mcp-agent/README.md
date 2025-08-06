![Architecture](https://img.shields.io/badge/Architecture-MCP%20Client%20in%20uAgent-blue)
![Protocol](https://img.shields.io/badge/Protocol-Chat%20Protocol-green)
![MCP](https://img.shields.io/badge/MCP-Remote%20Context7-orange)
![AI](https://img.shields.io/badge/AI-OpenAI%20Compatible-purple)

# Events Finder MCP Agent

A Fetch.ai MCP agent for discovering events, retrieving event details, and exploring venues using the Ticketmaster Discovery API. Designed for robust LLM tool use and multi-turn conversations.

---

## Features

- **search_events**: Find events by keyword, location, date range, or classification. Returns a list with event name, date, venue, event ID, and URL.
- **get_event_details**: Retrieve full details for a specific event by event ID, including name, date, venue, city, price range, genres, ticket link, and description.
- **search_venues**: Lookup venues by name or location. Returns a list with venue name, address, venue ID, and URL.

All outputs include IDs for follow-up queries. The agent is designed to clarify ambiguous queries and never invents IDs or URLs.

---

## Setup

1. **Clone the repository** and navigate to this directory.
2. **Create a `.env` file** with your API keys:
    ```
    TICKETMASTER_API_KEY=your_ticketmaster_api_key
    # Choose one of the following LLM services:
    OPENAI_API_KEY=your_openai_api_key
    # OR
    GROQ_API_KEY=your_groq_api_key
    # OR
    ASI1_API_KEY=your_asi1_api_key
    ```
3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

---

## Running the Agent

Start the agent (which wraps the MCP server):

```bash
python agent.py
```

---

## Example Usage

You can interact with the agent using natural language. Here are some example queries:

- **Search for events:**
  - "Are there any rock concerts in New York next month?"
  - "Show me upcoming tech conferences in San Francisco."
  - "Find classical music events in London this weekend."

- **Get event details (after seeing a list):**
  - "Tell me more about the second event."
  - "Can I get details for the event called Jazz Night?"

- **Search for venues:**
  - "Find venues called Madison Square Garden."
  - "Show me stadiums in Los Angeles."

**Multi-turn conversation example:**

1. User: "What concerts are happening in Paris in September?"
2. Agent: *(Returns a numbered list of events with names, dates, venues, and event IDs)*
3. User: "Give me details about the third event."
4. Agent: *(Returns full details for the selected event, including name, date, venue, city, price range, genres, ticket link, and description)*

**Ambiguity clarification example:**

- User: "Tell me more about the concert."
- Agent: "There are several concerts listed. Could you specify which one you mean by its number or name?"

The agent always includes event or venue IDs in responses for easy follow-up, and will ask for clarification if your request is ambiguous.

---

## Environment Variables

- `TICKETMASTER_API_KEY`: Your Ticketmaster Discovery API key.
- **LLM API Key** (choose one):
  - `OPENAI_API_KEY`: Your OpenAI API key 
  - `GROQ_API_KEY`: Your Groq API key
  - `ASI1_API_KEY`: Your ASI1 API key

---

## LLM Configuration

The agent supports any **OpenAI-compatible API** service. You can easily switch between different LLM providers by modifying the `agent.py` file:

### **OpenAI** (Default)
```python
llm_api_key=OPENAI_API_KEY,
model="gpt-4o-mini",
llm_base_url="https://api.openai.com/v1",
```

### **Groq** (Fast Inference)
```python
llm_api_key=GROQ_API_KEY,
model="llama3-8b-8192",
llm_base_url="https://api.groq.com/openai/v1",
```

### **ASI1** (Alternative)
```python
llm_api_key=ASI1_API_KEY,
model="asi1-mini",
llm_base_url="https://api.asi1.ai/v1",
```

**Available ASI1 Models:**
- **asi1-mini**: Fast and efficient model for quick responses
- **asi1-fast**: Optimized for speed with good performance  
- **asi1-extended**: Enhanced model with extended capabilities

### **Other OpenAI-Compatible Services**
You can use any service that provides an OpenAI-compatible API endpoint by updating:
- `llm_api_key`: Your API key
- `model`: The model name for that service
- `llm_base_url`: The API endpoint URL

---

## Notes

- **.env file:** Make sure to add `.env` to your `.gitignore` to avoid committing secrets.
- **LLM flexibility:** The agent works with any OpenAI-compatible API, making it easy to switch between different LLM providers.
- **LLM prompt engineering:** The agent is optimized for tool use, context tracking, and follow-up queries.
- **Extensible:** You can add more tools or customize the agent for other event APIs.

---

## License

This project is licensed under the MIT License. 