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

- **Search for events:**
  - `search_events({"keyword": "rock", "countryCode": "US", "startDateTime": "2025-08-01T00:00:00Z", "endDateTime": "2025-08-31T23:59:59Z"})`
- **Get event details:**
  - `get_event_details({"id": "<event_id>"})`
- **Search for venues:**
  - `search_venues({"keyword": "stadium", "countryCode": "US"})`

---

## Environment Variables

- `TICKETMASTER_API_KEY`: Your Ticketmaster Discovery API key.
- `ASI1_API_KEY`: Your ASI1 LLM API key.

---

## Notes

- **.env file:** Make sure to add `.env` to your `.gitignore` to avoid committing secrets.
- **LLM prompt engineering:** The agent is optimized for tool use, context tracking, and follow-up queries.
- **Extensible:** You can add more tools or customize the agent for other event APIs.

---

## License

This project is licensed under the MIT License. 