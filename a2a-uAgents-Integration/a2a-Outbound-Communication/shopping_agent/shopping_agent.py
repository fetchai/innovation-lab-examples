import asyncio # Import asyncio for timeout handling
from typing import List
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from agno.agent import Agent, Message, RunResponse
from agno.models.openai import OpenAIChat
from agno.tools.exa import ExaTools
from typing_extensions import override

# Define your agno.agent shopping partner
shopping_partner_agno_agent = Agent(
    name="shopping partner",
    model=OpenAIChat(id="gpt-4o"), # Using gpt-4o as per your request
    instructions=[
        "You are a product recommender agent specializing in finding products that match user preferences.",
        "Prioritize finding products that satisfy as many user requirements as possible, but ensure a minimum match of 50%.",
        "Search for products only from authentic and trusted e-commerce websites such as Amazon, Flipkart, Myntra, Meesho, Google Shopping, Nike, and other reputable platforms.",
        "Verify that each product recommendation is in stock and available for purchase.",
        "Avoid suggesting counterfeit or unverified products.",
        "Clearly mention the key attributes of each product (e.g., price, brand, features) in the response.",
        "Format the recommendations neatly and ensure clarity for ease of user understanding.",
    ],
    tools=[ExaTools()],
    show_tool_calls=True,
)

class ShoppingAgentExecutor(AgentExecutor):
    """
    AgentExecutor wrapper for the agno.agent shopping partner.
    This class allows the agno agent to be integrated with the A2A adapter.
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
        print(f"DEBUG: [ShoppingAgentExecutor] Received message: {message.content}")
        
        try:
            # Set a timeout for the agno agent's execution
            print("DEBUG: [ShoppingAgentExecutor] Starting agno agent run with timeout...")
            # We'll give it 90 seconds to complete its task
            result: RunResponse = await asyncio.wait_for(self.agent.arun(message), timeout=90) 
            print(f"DEBUG: [ShoppingAgentExecutor] Agno agent finished run. Response content type: {type(result.content)}")
            
            response_text = str(result.content) 
            await event_queue.enqueue_event(new_agent_text_message(response_text))
            print("DEBUG: [ShoppingAgentExecutor] Event enqueued successfully.")

        except asyncio.TimeoutError:
            error_message = "Agno agent execution timed out after 90 seconds."
            print(f"❌ {error_message}")
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please try again or simplify your query."))
        except Exception as e:
            error_message = f"Error during agno agent execution: {e}"
            print(f"❌ {error_message}")
            import traceback
            traceback.print_exc()
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {error_message}. Please check logs for details."))
        
        print("DEBUG: [ShoppingAgentExecutor] execute method finished.")

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Cancels the agent's execution.
        (Basic implementation: raises an exception as cancellation is not supported here).
        """
        raise Exception("Cancel not supported for this agent executor.")
