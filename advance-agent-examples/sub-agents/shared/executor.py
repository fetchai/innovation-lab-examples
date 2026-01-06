import uuid
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart, Message, Role
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.apps.app import App


class BaseAgentExecutor(AgentExecutor):
    """
    Executor for the Time Agent that processes queries about current time in cities.
    """

    def __init__(self, app: App, session_service: InMemorySessionService):
        self.app = app
        self.session_service = session_service
        self.runner = Runner(
            app=app,
            session_service=session_service
        )

    def create_response_message(self, text: str) -> Message:
        """Helper to create an A2A Message response."""
        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=text))]
        )

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the agent with the given query and stream results.
        """
        query = context.get_user_input()

        try:
            # Create or get session
            session = await self.session_service.create_session(
                app_name=self.app.name,
                user_id="a2a_user",
            )

            # Convert string query to Content object for Google ADK
            user_content = types.Content(
                parts=[types.Part(text=query)],
                role="user"
            )

            # Run the agent
            response_text = ""
            async for event in self.runner.run_async(
                user_id="a2a_user",
                session_id=session.id,
                new_message=user_content
            ):
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                response_text += part.text

            # If we got a response, send it using enqueue_event with proper Message type
            if response_text:
                await event_queue.enqueue_event(self.create_response_message(response_text))
            else:
                await event_queue.enqueue_event(
                    self.create_response_message(
                        "I couldn't process your request. Please try again.")
                )

        except Exception as e:
            await event_queue.enqueue_event(
                self.create_response_message(
                    f"Error processing request: {str(e)}")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current execution."""
        pass

__all__ = ["BaseAgentExecutor"]