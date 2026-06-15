from uagents import Model


class PromptRequest(Model):
    """
    Message model for sending a prompt to the Gemini agent.
    """

    prompt: str


class PromptResponse(Model):
    """
    Message model for receiving a response from the Gemini agent.
    """

    response: str
    error: str | None = None
