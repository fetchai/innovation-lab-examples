import asyncio
from typing import List
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunResponse
from agno.models.google import Gemini
from agno.tools.exa import ExaTools
from typing_extensions import override
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

books_recommender_agno_agent = Agent(
    name="books recommender",
    model=Gemini(id="gemini-2.0-flash"),
    instructions=[
        "You are a highly detailed book recommender agent specializing in finding books that precisely match user preferences.",
        "Prioritize finding books that satisfy as many user requirements as possible, but ensure a minimum match of 50%.",
        "Search for books only from authentic and trusted sources such as Amazon, Goodreads, Barnes & Noble, Book Depository, Audible, Google Books, and other reputable platforms.",
        "Verify that each book recommendation is available for purchase or reading.",
        "Avoid suggesting pirated or unverified sources.",
        "**CRITICAL: Provide up to 10 comprehensive and detailed book recommendations.**",
        "**For each book, include the following extensive details:**",
        "  - Book Title and Author(s)",
        "  - Direct Link to the book page on the source website",
        "  - Price (with currency, if applicable for purchase)",
        "  - Average Rating (e.g., 4.5/5 stars from Goodreads or Amazon)",
        "  - Key Details and Specifications (e.g., genre, publication date, page count, format: paperback/hardcover/ebook/audiobook)",
        "  - A brief summary of the book plot or content",
        "  - Pros and Cons based on reader reviews",
        "  - Availability status (In Stock/Available for Purchase/Out of Stock)",
        "  - Book Cover Image URL (a direct link to the book's cover image from a trusted source, e.g., Amazon, Goodreads, or publisher's website)",
        "**After listing individual book details, provide a comparative analysis section.**",
        "  - Compare the top 3-5 recommended books based on key criteria (e.g., price, rating, genre suitability, reader feedback).",
        "  - Highlight their similarities and differences to help the user make an informed decision.",
        "Format the recommendations neatly and ensure clarity for ease of user understanding, presenting them as a structured report with clear headings and bullet points. Use a table for the comparative analysis if appropriate. Include the book cover image URLs in the output, ensuring they are valid and accessible."
    ],
    tools=[ExaTools()],
    show_tool_calls=True,
)

class BooksRecommenderAgentExecutor(AgentExecutor):
    """
    AgentExecutor wrapper for the agno.agent books recommender.
    """
    def __init__(self):
        self.agent = books_recommender_agno_agent

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Executes the agno agent's logic based on the incoming A2A message.
        """
        message_content = ""
        for part in context.message.parts:
            if isinstance(part, Part):
                if isinstance(part.root, TextPart):
                    message_content = part.root.text
                    break
        
        if not message_content:
            await event_queue.enqueue_event(new_agent_text_message("Error: No message content received."))
            return

        message: Message = Message(role="user", content=message_content)
        logger.info(f"Received message: {message.content}")
        
        try:
            logger.info("Starting agno agent run with timeout...")
            result: RunResponse = await asyncio.wait_for(self.agent.arun(message), timeout=180)
            logger.info(f"Agno agent finished run. Response content type: {type(result.content)}")
            
            response_text = str(result.content)
            await event_queue.enqueue_event(new_agent_text_message(response_text))
            logger.info("Event enqueued successfully.")

        except asyncio.TimeoutError:
            error_message = "Agno agent execution timed out after 180 seconds. The query might be too complex or require more time."
            logger.error(error_message)
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please try again or simplify your query."))
        except Exception as e:
            error_message = f"Error during agno agent execution: {e}"
            logger.error(error_message, exc_info=True)
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please check logs for details."))
        
        logger.info("execute method finished.")

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Cancels the agent's execution.
        """
        raise Exception("Cancel not supported for this agent executor.")