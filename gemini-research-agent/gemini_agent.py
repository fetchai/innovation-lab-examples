import os
from uagents import Agent, Context, Model
from google import genai
from dotenv import load_dotenv

# Load environment variables (ensure GEMINI_API_KEY is in your .env)
load_dotenv()

# --- 1. Define the Message Data Models ---
class ResearchRequest(Model):
    topic: str

class ResearchResponse(Model):
    summary: str

# --- 2. Initialize the Agent ---
research_agent = Agent(
    name="gemini_researcher",
    port=8000,
    seed="gemini_researcher_secret_seed",
    endpoint=["http://127.0.0.1:8000/submit"],
)

# Initialize the Gemini Client
# It will automatically pick up the GEMINI_API_KEY from the environment
gemini_client = genai.Client()

# --- 3. Define the Message Handler ---
@research_agent.on_message(model=ResearchRequest, replies=ResearchResponse)
async def handle_research_request(ctx: Context, sender: str, msg: ResearchRequest):
    ctx.logger.info(f"Received research request from {sender[-8:]} for topic: '{msg.topic}'")
    
    try:
        # Prompt Engineering for the Agent
        system_instruction = "You are a concise, highly factual research assistant."
        prompt = f"{system_instruction}\n\nProvide a structured summary about: {msg.topic}"
        
        # Call the Gemini API
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # Send the AI-generated response back to the sender
        await ctx.send(sender, ResearchResponse(summary=response.text))
        ctx.logger.info("Successfully generated and returned the research summary.")
        
    except Exception as e:
        ctx.logger.error(f"Gemini API Error: {e}")
        await ctx.send(sender, ResearchResponse(summary=f"Agent Error: Could not process request. {str(e)}"))

if __name__ == "__main__":
    research_agent.run()