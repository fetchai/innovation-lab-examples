import os
from dotenv import load_dotenv
from google import genai

from uagents import Agent, Context
from models import PromptRequest, PromptResponse

# Load environment variables
load_dotenv()

# Get the API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Create the Gemini agent
agent = Agent(
    name="gemini_agent",
    seed="gemini_agent_recovery_seed",
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"],
)

# Initialize the Gemini client
# Robust error handling for missing API key
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
else:
    print("WARNING: GEMINI_API_KEY is not set in the environment variables.")

# Model configuration
MODEL_NAME = "gemini-2.5-flash"


@agent.on_event("startup")
async def startup(ctx: Context):
    """
    Startup event handler to log the agent's details.
    """
    ctx.logger.info(f"Starting Gemini Agent: {agent.name}")
    ctx.logger.info(f"Agent address: {agent.address}")
    if client is None:
        ctx.logger.error("Gemini client is not initialized. Please check your API key.")
    else:
        ctx.logger.info("Gemini client initialized successfully.")


@agent.on_message(model=PromptRequest, replies=PromptResponse)
async def handle_prompt_request(ctx: Context, sender: str, msg: PromptRequest):
    """
    Message handler for receiving PromptRequest messages.
    Queries the Gemini API and responds with the generated text.
    """
    ctx.logger.info(f"Received prompt from {sender}: '{msg.prompt}'")

    # 1. Error handling: empty prompt
    if not msg.prompt or not msg.prompt.strip():
        ctx.logger.warning("Received empty prompt.")
        await ctx.send(
            sender, PromptResponse(response="", error="Prompt cannot be empty.")
        )
        return

    # 2. Error handling: missing API key / client uninitialized
    if client is None:
        ctx.logger.error("Cannot process prompt: Gemini client is not initialized.")
        await ctx.send(
            sender,
            PromptResponse(
                response="", error="Gemini client not initialized. Check API key."
            ),
        )
        return

    try:
        ctx.logger.info("Querying Gemini API...")

        # Asynchronous flow: we use run_in_executor if the SDK is synchronous,
        # but the google-genai SDK can be called directly. Since it might block,
        # in a fully async environment, it's best practice to run it safely,
        # but for simplicity in this example we will just call it synchronously
        # or use the async capabilities if available (genai.Client is generally sync,
        # though async client can be used, we'll use the default one and assume it handles well
        # or it is fast enough for the example).

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=msg.prompt,
        )

        if response.text:
            ctx.logger.info("Successfully generated response from Gemini.")
            await ctx.send(sender, PromptResponse(response=response.text))
        else:
            ctx.logger.warning("Gemini returned an empty response.")
            await ctx.send(
                sender,
                PromptResponse(response="", error="Gemini returned an empty response."),
            )

    # 3. Error handling: API failures or network failures
    except Exception as e:
        ctx.logger.error(f"Error querying Gemini API: {str(e)}")
        await ctx.send(
            sender, PromptResponse(response="", error=f"Gemini API Error: {str(e)}")
        )


if __name__ == "__main__":
    agent.run()
