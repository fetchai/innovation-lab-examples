# Nike Product Scraper Agent for Agentverse

This project is a sophisticated, AI-powered agent designed to scrape product information from the Nike website based on natural language queries. It serves as a reference implementation for building autonomous agents on the Agentverse platform, leveraging the `uAgents` framework for agent communication and `notte-labs` for intelligent, AI-driven web scraping.

This agent can be discovered and utilized by other agents, such as the ASI:ONE LLM, to fulfill user requests for Nike product data dynamically.

## 🌟 Features

-   **Natural Language Understanding:** Interprets user queries like "find me men's running shoes" or "get me 5 new accessories".
-   **Dynamic Scraping:** Navigates the Nike website, handles popups (cookies, location), and scrapes:
    -   Main product categories (Shoes, Clothing, etc.).
    -   Sub-categories within a main category (e.g., "Running" under "Shoes").
    -   Product listings with details like name, price, and URL.
-   **Robust Logic:** Intelligently handles variations in user queries and website structure. It can distinguish between categories and product queries and defaults gracefully.
-   **Structured Data Output:** Returns clean, structured JSON data, making it easy for other services or agents to consume.
-   **Extensible Architecture:** Built with a clear separation of concerns, making it easy to understand, maintain, and adapt for other websites.

## 🛠️ Tech Stack

-   **Agent Framework:** [uAgents](https://fetch.ai/docs/guides/agents/installing-uagent) - A Python framework for building decentralized agents.
-   **Web Scraping:** [Notte SDK](https://www.notte.ai/) - An AI-powered, headless browser automation tool that uses an LLM to understand and interact with web pages.
-   **Data Validation:** [Pydantic](https://docs.pydantic.dev/) - For defining and validating structured data models.
-   **Programming Language:** Python 3.10+

## 🏗️ Architecture and Code Structure

The agent's logic is modularized into three key files to ensure clarity and maintainability.

### `agent.py`
-   **Purpose:** The entry point of the agent.
-   **Responsibilities:**
    -   Initializes the `uAgents.Agent` instance with a mailbox to make it discoverable on the Agentverse.
    -   Sets up the communication protocols (`chat_proto`, `struct_output_client_proto`).
    -   Runs the agent, making it available on the network.

### `chat_proto.py`
-   **Purpose:** Handles all incoming and outgoing communication for the agent.
-   **Key Functions:**
    -   `handle_message()`: Receives plain-text queries from users or other agents. It wraps the query in a `StructuredOutputPrompt` and sends it to the `uAgents` LLM service for interpretation.
    -   `handle_structured_output_response()`: Receives the structured JSON data back from the LLM service. It parses this data into a `NikeScrapeRequest` Pydantic model and passes it to the core scraping logic in `nike_scraper.py`. It then formats the final result and sends it back to the original requester.

### `nike_scraper.py`
-   **Purpose:** Contains the core business logic for scraping the Nike website.
-   **Key Components:**
    -   **Environment Loading:** Loads the `.env` file to make environment variables like `NOTTE_API_KEY` available.
    -   **Pydantic Models:** Defines the data structures for requests (`NikeScrapeRequest`) and responses (`NikeScrapeResponse`, `ProductCategories`, `ShoppingList`, etc.). This ensures type safety and clear data contracts.
    -   **Scraping Functions (`scrape_main_categories`, `scrape_sub_categories`, etc.):** These functions use the Notte SDK to perform specific scraping tasks. They construct detailed prompts for the Notte LLM to guide its interaction with the Nike website.
    -   **`get_nike_info_enhanced()`:** The main orchestrator function. It receives the `NikeScrapeRequest`, determines the required action (e.g., `LIST_PRODUCTS`, `GET_SUB_CATEGORIES`), and calls the appropriate scraping functions. It contains the complex logic for finding category URLs, handling ambiguous queries, and assembling the final response.

## 🚀 Setup and Installation

Follow these steps to get the Nike agent running on your local machine.

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd agents-agentverse/nike-asi-agent
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If a `requirements.txt` file doesn't exist, you can create one from the imports in the Python files.)*

4.  **Set Up Environment Variables:**
    Create a file named `.env` in the `nike-asi-agent` directory and add your Notte API key:
    ```
    NOTTE_API_KEY="your_notte_api_key_here"
    ```

## ▶️ How to Run the Agent

With your environment set up and dependencies installed, run the agent with the following command:

```bash
python agent.py
```

The agent will start, register itself, and begin listening for incoming messages. You can then interact with it using another agent or a client capable of sending messages on the `uAgents` network.

## 🌐 Publishing to the Agentverse

Once your agent is running, you can publish it to the Agentverse to make it discoverable and usable by others.

1.  **Get the Agent Inspector Link:** When you run `python agent.py`, the console will output your agent's address and an inspector link.

2.  **Connect to the Mailbox:** Open the inspector link in your web browser. You will see an interface for your agent. Use this interface to connect your agent to a mailbox on the Agentverse network. This step is crucial for your agent to send and receive messages from other agents.

3.  **Publish the Agent's Profile:** After connecting to the mailbox, you can publish a profile for your agent. This makes it appear in the Agentverse directory. Use the following information for the profile:
    -   **Name:** Nike Product Scraper Agent
    -   **Description:** This AI Agent retrieves detailed information about Nike products using the Notte SDK for web scraping. It can provide lists of product categories and specific products within those categories, including names, prices, and URLs. Simply ask the agent to list categories or products (optionally specifying a category) to get comprehensive Nike product information.
    -   **Tags:** `e-commerce`, `shopping`, `data-extraction`, `web-scraping`, `nike`

Now your agent is live and part of the Agentverse ecosystem!

## 💡 How It Works: The Agent's Flow

1.  A user or another agent (like ASI:ONE) sends a natural language query (e.g., "show me men's running shoes") to the Nike agent's address.
2.  `chat_proto.py`'s `handle_message` function receives the query.
3.  It sends the query to the `uAgents` LLM service, asking it to convert the text into a structured `NikeScrapeRequest` (e.g., `gender='MEN'`, `category_name='running'`, `action='LIST_PRODUCTS'`).
4.  `chat_proto.py`'s `handle_structured_output_response` receives this structured request.
5.  It calls `get_nike_info_enhanced()` in `nike_scraper.py` with the request object.
6.  `get_nike_info_enhanced()` orchestrates the scraping process:
    -   It might first call `scrape_main_categories()` to find the URL for the "Shoes" category page.
    -   Then, it might call `scrape_sub_categories()` on the "Shoes" page to find the URL for the "Running" sub-category.
    -   Finally, it calls another scraping function to get the product listings from the "Running" page.
7.  The final, structured data (`ShoppingList`) is returned to `chat_proto.py`.
8.  `chat_proto.py` formats this data into a user-friendly text message and sends it back to the original requester.

## 🧩 How to Extend and Build Your Own Agent

This project serves as a blueprint for creating your own web-scraping agents for the Agentverse.

1.  **Identify a Target Website:** Choose a website you want to scrape (e.g., Amazon, Airbnb, Wikipedia).
2.  **Define Your Data Models:** In your `scraper.py`, define Pydantic models for the data you want to extract (e.g., `AmazonProduct`, `AirbnbListing`). Also, define a request model similar to `NikeScrapeRequest` to capture the different actions your agent can perform.
3.  **Write Scraping Logic:** Use the Notte SDK to write functions to scrape the target website. Start simple (e.g., just getting main categories) and build up complexity. Use detailed prompts to guide the Notte LLM.
4.  **Create the Orchestrator:** Write a main handler function like `get_nike_info_enhanced()` to manage the different scraping actions based on the incoming request.
5.  **Wire up the Agent:** Use `agent.py` and `chat_proto.py` as templates. Update `chat_proto.py` to use your new request and response models.
6.  **Test and Refine:** Run your agent and test it with various queries. Refine your Notte prompts and your orchestration logic until it's reliable.

By following this pattern, you can build powerful, autonomous agents that can be discovered and used by others in the Agentverse ecosystem.

**Tags:** `e-commerce` `shopping` `data-extraction` `web-scraping` `nike`

**Description:** This AI Agent retrieves detailed information about Nike products using the Notte SDK for web scraping. It can provide lists of product categories and specific products within those categories, including names, prices, and URLs. Simply ask the agent to list categories or products (optionally specifying a category) to get comprehensive Nike product information.

{{ ... }}

This is the model used when sending direct structured requests to the agent (e.g., from another agent or service). For natural language queries via ASI1, the LLM will help construct this request.

```python
from uagents import Model
from typing import Optional
from enum import Enum

class NikeAction(str, Enum):
    SCRAPE_CATEGORIES = "scrape_categories"
    SCRAPE_PRODUCTS = "scrape_products"
    LIST_CATEGORIES = "list_categories"  # Equivalent to SCRAPE_CATEGORIES for now
    LIST_PRODUCTS = "list_products"    # Equivalent to SCRAPE_PRODUCTS for now

class NikeScrapeRequest(Model):
    category_name: Optional[str] = None  # e.g., "Shoes", "Running", "Basketball"
    action: NikeAction  # The specific action for the agent to perform
```

**Output Data Model**

This is the model used when the agent sends back a structured response.

```python
from uagents import Model

class NikeScrapeResponse(Model):
    results: str # A formatted string containing the scraped categories or products
```

**Setup and Running the Agent:**

1.  **Environment Variable:** Ensure the `NOTTE_API_KEY` environment variable is set with your valid Notte SDK API key.
    ```bash
    export NOTTE_API_KEY="your_notte_api_key_here"
    ```
2.  **Dependencies:** This project uses `uagents`, `notte-sdk`, and `requests`. It's recommended to use a virtual environment. You can install them using pip:
    ```bash
    pip install uagents notte-sdk requests
    ```
    (A `requirements.txt` file will be added soon for easier dependency management.)
3.  **Running the Agent:** Navigate to the `nike-asi-agent` directory and run:
    ```bash
    python agent.py
    ```
    The agent will start and print its address.

**Key Features & Recent Changes:**

*   Uses `notte.Session(headless=False)` for category and product scraping, potentially improving interaction with dynamic website content.
*   Product scraping leverages `session.scrape()` from the Notte SDK for more direct data extraction.
*   Enhanced error handling and logging throughout the scraping process.

**Example Natural Language Queries (for ASI1 LLM interaction):**

*   "Show me Nike categories"
*   "List Nike basketball shoes"
*   "Get Nike running products"
*   "Scrape all Nike product categories"
*   "What are the latest men's arrivals on Nike?" (This might require the LLM to infer `action='scrape_products'` and `category_name='New Arrivals'` or similar)

**Setup and Usage:**

1.  **Environment Variable:** Ensure the `NOTTE_API_KEY` environment variable is set with your valid Notte SDK API key.
    ```bash
    export NOTTE_API_KEY="your_notte_api_key_here"
    ```
2.  **Run the Agent:**
    ```bash
    python agent.py
    ```
    The agent will start and print its address. It will be discoverable on ASI1 if mailboxing is correctly configured.

**Note on Rate Limiting:** The agent implements a rate limit of 30 requests per hour per user by default.
```
