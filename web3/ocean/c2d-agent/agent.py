import os
import asyncio
import aiohttp
import json
import re
from uuid import uuid4
from datetime import datetime
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)


AGENT_NAME = os.getenv("SIMPLE_AGENT_NAME", "Demographics Agent")
PORT = 8005  # Different port to avoid conflicts

# Compute service configuration
COMPUTE_SERVICE_URL = os.getenv("COMPUTE_SERVICE_URL", "http://localhost:3000")

# ASI:One API configuration
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_API_URL = "https://api.asi1.ai/v1/chat/completions"

# Create the agent
agent = Agent(
    name=AGENT_NAME,
    port=PORT,
    mailbox=True,
)

# Create the chat protocol
simple_chat_proto = Protocol(spec=chat_protocol_spec)

def create_text_chat(text: str) -> ChatMessage:
    """Helper function to create a text chat message"""
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )

def extract_json_from_result(result_content: str) -> dict:
    """Extract JSON from the compute result content"""
    try:
        # Look for JSON between the markers
        start_marker = "=== DEMOGRAPHICS ANALYSIS RESULT ==="
        end_marker = "=== END RESULT ==="
        
        start_idx = result_content.find(start_marker)
        end_idx = result_content.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            json_text = result_content[start_idx + len(start_marker):end_idx].strip()
            return json.loads(json_text)
        else:
            # Fallback: try to find JSON anywhere in the content
            json_match = re.search(r'\{.*\}', result_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return None
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return None

async def ask_asi_one_llm(user_question: str, demographics_data: dict) -> str:
    """Ask ASI:One LLM to answer the user question based on demographics data"""
    if not ASI_ONE_API_KEY:
        return "ASI:One API key not configured. Cannot answer questions."
    
    try:
        # Prepare the prompt
        prompt = f"""
Based on the following demographics data, please answer this question: "{user_question}"

Demographics Data:
{json.dumps(demographics_data, indent=2)}

Please provide a simple one sentence answer based on the data above.
"""
        
        headers = {
            "Authorization": f"Bearer {ASI_ONE_API_KEY}",
            "x-session-id": str(uuid4()),
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "asi1-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(ASI_ONE_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "No response from LLM")
                else:
                    return f"Error calling ASI:One API: {response.status}"
                    
    except Exception as e:
        return f"Error asking LLM: {str(e)}"

async def start_compute_job() -> dict:
    """Start a compute job and return the response"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{COMPUTE_SERVICE_URL}/compute/start") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Failed to start compute job: {response.status}"}
        except Exception as e:
            return {"error": f"Error starting compute job: {str(e)}"}

async def check_compute_status() -> dict:
    """Check the status of the compute job"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{COMPUTE_SERVICE_URL}/compute/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Failed to check status: {response.status}"}
        except Exception as e:
            return {"error": f"Error checking status: {str(e)}"}

async def get_compute_result() -> dict:
    """Get the compute result"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{COMPUTE_SERVICE_URL}/compute/result") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Failed to get result: {response.status}"}
        except Exception as e:
            return {"error": f"Error getting result: {str(e)}"}

async def reset_compute_job() -> dict:
    """Reset the compute job state"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{COMPUTE_SERVICE_URL}/compute/reset") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Failed to reset job: {response.status}"}
        except Exception as e:
            return {"error": f"Error resetting job: {str(e)}"}

async def poll_compute_job(ctx: Context, sender: str, job_id: str) -> dict:
    """Poll the compute job until completion and return the JSON data"""
    max_attempts = 30  # 5 minutes max (30 * 10 seconds)
    attempts = 0
    
    ctx.logger.info(f"Starting to poll compute job: {job_id}")
    
    while attempts < max_attempts:
        await asyncio.sleep(10)  # Wait 10 seconds between polls
        attempts += 1
        
        status_response = await check_compute_status()
        
        if "error" in status_response:
            return {"error": f"Error checking status: {status_response['error']}"}
        
        status = status_response.get("status")
        ctx.logger.info(f"Poll attempt {attempts}: Job status = {status}")
        
        if status == "completed":
            # Get the result
            result_response = await get_compute_result()
            
            if "error" in result_response:
                return {"error": f"Error getting result: {result_response['error']}"}
            
            result = result_response.get("result", {})
            result_content = result.get("resultContent", "No content available")
            
            # Extract JSON from the result
            demographics_data = extract_json_from_result(result_content)
            
            if demographics_data:
                return {"success": True, "data": demographics_data}
            else:
                return {"error": "Could not extract JSON data from compute result"}
            
        elif status == "error":
            error_msg = status_response.get("error", "Unknown error")
            return {"error": f"Compute job failed: {error_msg}"}
            
        elif status == "running":
            # Continue polling
            continue
        else:
            return {"error": f"Unexpected status: {status}"}
    
    return {"error": "Compute job did not complete within timeout period (5 minutes)"}

@simple_chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""
    # Store the original user question
    user_question = ""
    
    # Send acknowledgement immediately
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(), 
            acknowledged_msg_id=msg.msg_id
        ),
    )

    # Process each content item in the message
    for item in msg.content:
        if isinstance(item, TextContent):
            user_question = item.text
            ctx.logger.info(f"Got a message from {sender}: {user_question}")
            
            # For ANY message, start a compute job
            ctx.logger.info("Starting compute job for any message received...")
            
            # Start the compute job
            start_response = await start_compute_job()
            
            if "error" in start_response:
                # Only send error message if compute job fails to start
                await ctx.send(sender, create_text_chat(f"Failed to start compute job: {start_response['error']}"))
                continue
            
            job_id = start_response.get("jobId", "unknown")
            ctx.logger.info(f"Compute job started! Job ID: {job_id}")
            
            # Poll for completion (no intermediate messages)
            ctx.logger.info("Polling for completion...")
            poll_result = await poll_compute_job(ctx, sender, job_id)
            
            if "error" in poll_result:
                # Send error message
                await ctx.send(sender, create_text_chat(f"Error: {poll_result['error']}"))
            else:
                # Get the demographics data
                demographics_data = poll_result["data"]
                
                # Ask ASI:One LLM to answer the user's question
                llm_answer = await ask_asi_one_llm(user_question, demographics_data)
                
                # Send the LLM answer
                await ctx.send(sender, create_text_chat(llm_answer))
            
            # Reset the job for next time
            reset_response = await reset_compute_job()
            if "error" in reset_response:
                ctx.logger.warning(f"Failed to reset compute job: {reset_response['error']}")
            
        else:
            ctx.logger.info(f"Got unexpected content type from {sender}")

@simple_chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements"""
    ctx.logger.info(f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}")

# Include the protocol in the agent
agent.include(simple_chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()