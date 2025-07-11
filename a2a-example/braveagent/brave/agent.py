import os
import requests
from dotenv import load_dotenv
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from typing_extensions import override

# Load environment variables
load_dotenv()

class BraveSearchAgentExecutor(AgentExecutor):
    """Brave Search Agent that specializes in web and local search queries using the Brave Search API."""
    
    def __init__(self):
        self.url = "https://api.search.brave.com/res/v1/web/search"
        self.local_url = "https://api.search.brave.com/res/v1/local/pois"
        self.desc_url = "https://api.search.brave.com/res/v1/local/descriptions"
        self.api_key = os.getenv("BRAVE_API_KEY")
        if not self.api_key:
            raise ValueError("BRAVE_API_KEY environment variable is required")
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        self.system_prompt = """You are a Brave Search AI Agent. Your expertise includes:
1. Performing web searches for general queries, news, articles, and online content
2. Conducting local searches for businesses, restaurants, and services
3. Providing concise and relevant search results
4. Handling queries with specific search types (web or local)
5. Summarizing search results for clarity

Search Commands you can handle:
- WEB:[query] - Perform a web search
- LOCAL:[query] - Perform a local search for businesses or places
- SEARCH:[query] - Perform a general search (defaults to web search)
- SUMMARIZE:[query] - Summarize search results for a query

Always provide clear, concise, and well-structured search results.
        """
    
    @override
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message_content = ""
        for part in context.message.parts:
            if isinstance(part, Part) and isinstance(part.root, TextPart):
                message_content = part.root.text
                break
        
        try:
            # Parse command if it's a structured search request
            if message_content.startswith("WEB:"):
                await self._handle_web_search_command(message_content, event_queue)
            elif message_content.startswith("LOCAL:"):
                await self._handle_local_search_command(message_content, event_queue)
            elif message_content.startswith("SEARCH:"):
                await self._handle_general_search_command(message_content, event_queue)
            elif message_content.startswith("SUMMARIZE:"):
                await self._handle_summarize_command(message_content, event_queue)
            else:
                # General search request
                await self._handle_general_search_command(f"SEARCH:{message_content}", event_queue)
                
        except Exception as e:
            await event_queue.enqueue_event(
                new_agent_text_message(f"❌ Search error: {str(e)}")
            )
    
    async def _handle_web_search_command(self, command: str, event_queue: EventQueue):
        """Handle WEB:query commands."""
        query = command.replace("WEB:", "", 1)
        if not query:
            await event_queue.enqueue_event(
                new_agent_text_message("❌ Usage: WEB:query (e.g., WEB:Python programming)")
            )
            return
        
        results = await self._perform_web_search(query)
        formatted_response = f"""🌐 Brave Search Agent - Web Search
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Query: {query}

{results}

✅ Web search by Brave Search Agent
        """
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    async def _handle_local_search_command(self, command: str, event_queue: EventQueue):
        """Handle LOCAL:query commands."""
        query = command.replace("LOCAL:", "", 1)
        if not query:
            await event_queue.enqueue_event(
                new_agent_text_message("❌ Usage: LOCAL:query (e.g., LOCAL:pizza near Central Park)")
            )
            return
        
        results = await self._perform_local_search(query)
        formatted_response = f"""📍 Brave Search Agent - Local Search
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Query: {query}

{results}

✅ Local search by Brave Search Agent
        """
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    async def _handle_general_search_command(self, command: str, event_queue: EventQueue):
        """Handle SEARCH:query commands."""
        query = command.replace("SEARCH:", "", 1)
        if not query:
            await event_queue.enqueue_event(
                new_agent_text_message("❌ Usage: SEARCH:query (e.g., SEARCH:latest AI news можем")
            )
            return
        
        results = await self._perform_web_search(query)
        formatted_response = f"""🌐 Brave Search Agent - General Search
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Query: {query}

{results}

✅ General search by Brave Search Agent
        """
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    async def _handle_summarize_command(self, command: str, event_queue: EventQueue):
        """Handle SUMMARIZE:query commands."""
        query = command.replace("SUMMARIZE:", "", 1)
        if not query:
            await event_queue.enqueue_event(
                new_agent_text_message("❌ Usage: SUMMARIZE:query (e.g., SUMMARIZE:AI advancements 2025)")
            )
            return
        
        results = await self._perform_web_search(query)
        # Simplified summarization (could be enhanced with NLP if needed)
        summary = "\n".join(line for line in results.split("\n") if "Description:" in line)
        formatted_response = f"""📝 Brave Search Agent - Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Query: {query}

{summary}

✅ Summary by Brave Search Agent
        """
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    async def _perform_web_search(self, query: str, count: int = 10) -> str:
        """Perform a web search using the Brave Search API."""
        if len(query) > 400:
            raise ValueError("Query exceeds 400 characters")
        count = min(max(count, 1), 20)  # Clamp count to 1-20

        params = {"q": query, "count": count}
        try:
            response = requests.get(self.url, params=params, headers=self.headers)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Brave API error: {str(e)}")

        data = response.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found"

        return "\n\n".join(
            f"Title: {r.get('title', 'N/A')}\nDescription: {r.get('description', 'N/A')}\nURL: {r.get('url', 'N/A')}"
            for r in results
        )
    
    async def _perform_local_search(self, query: str, count: int = 5) -> str:
        """Perform a local search using the Brave Search API."""
        if len(query) > 400:
            raise ValueError("Query exceeds 400 characters")
        count = min(max(count, 1), 20)  # Clamp count to 1-20

        params = {"q": query, "search_lang": "en", "result_filter": "locations", "count": count}
        try:
            response = requests.get(self.url, params=params, headers=self.headers)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Brave API error: {str(e)}")

        data = response.json()
        location_ids = [r["id"] for r in data.get("locations", {}).get("results", []) if r.get("id")]

        if not location_ids:
            return await self._perform_web_search(query, count)

        params = {"ids": location_ids}
        try:
            poi_response = requests.get(self.local_url, params=params, headers=self.headers)
            poi_response.raise_for_status()
            desc_response = requests.get(self.desc_url, params=params, headers=self.headers)
            desc_response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Brave API error: {str(e)}")

        poi_data = poi_response.json()
        desc_data = desc_response.json().get("descriptions", {})

        results = []
        for loc in poi_data.get("results", []):
            address = ", ".join(
                filter(
                    None,
                    [
                        loc.get("address", {}).get(key, "")
                        for key in ["streetAddress", "addressLocality", "addressRegion", "postalCode"]
                    ],
                )
            ) or "N/A"
            result = (
                f"Name: {loc.get('name', 'N/A')}\n"
                f"Address: {address}\n"
                f"Phone: {loc.get('phone', 'N/A')}\n"
                f"Rating: {loc.get('rating', {}).get('ratingValue', 'N/A')} "
                f"({loc.get('rating', {}).get('ratingCount', 0)} reviews)\n"
                f"Description: {desc_data.get(loc.get('id'), 'No description available')}"
            )
            results.append(result)

        return "\n---\n".join(results) or "No local results found"
    
    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(new_agent_text_message("Search task cancelled."))