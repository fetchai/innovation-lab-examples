import asyncio
from typing import List
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunOutput
from agno.models.google import Gemini
from agno.tools.exa import ExaTools
from typing_extensions import override
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

shopping_partner_agno_agent = Agent(
    name="shopping partner",
    model=Gemini(id="gemini-2.0-flash"),
    instructions=[
        "You are a highly detailed product recommender agent specializing in finding products that precisely match user preferences.",
        "Prioritize finding products that satisfy as many user requirements as possible, but ensure a minimum match of 50%.",
        "Search for products only from authentic and trusted e-commerce websites such as Amazon, Flipkart, Myntra, Meesho, Google Shopping, Nike, and other reputable platforms.",
        "Verify that each product recommendation is in stock and available for purchase.",
        "Avoid suggesting counterfeit or unverified products.",
        "**CRITICAL: Provide up to 10 comprehensive and detailed product recommendations.**",
        "**For each product, include the following extensive details:**",
        "  - Product Name and Brand",
        "  - Direct Link to the product page on the e-commerce website",
        "  - Price (with currency)",
        "  - Customer Rating (e.g., 4.5/5 stars, or average review score)",
        "  - Key Features and Specifications (e.g., dimensions, materials, technical specs)",
        "  - A brief summary of Pros and Cons based on customer reviews",
        "  - Availability status (In Stock/Out of Stock)",
        "**After listing individual product details, provide a comparative analysis section.**",
        "  - Compare the top 3-5 recommended products based on key criteria (e.g., price, features, rating, best use case).",
        "  - Highlight their similarities and differences to help the user make an informed decision.",
        "Format the recommendations neatly and ensure clarity for ease of user understanding, presenting them as a structured report with clear headings and bullet points. Use a table for the comparative analysis if appropriate."
    ],
    tools=[ExaTools()],
)

class ShoppingAgentExecutor(AgentExecutor):
    """
    AgentExecutor wrapper for the agno.agent shopping partner.
    """
    def __init__(self):
        self.agent = shopping_partner_agno_agent

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
            result: RunOutput = await asyncio.wait_for(self.agent.arun(message), timeout=180)
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