"""
Claude Function Calling Agent for Fetch.ai Agentverse
An AI agent that can use tools and call functions to perform actions

This agent:
- Receives queries via Fetch.ai protocol
- Uses Claude's function calling to decide which tools to use
- Executes functions (weather, calculator, search, etc.)
- Returns results in a conversational way
- Supports multi-step workflows
"""

import os
import json
import requests
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec
)

# Load environment variables
load_dotenv()

# Configure Anthropic Claude
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

# Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

# Model configuration
MODEL_NAME = 'claude-3-5-sonnet-20241022'
MAX_TOKENS = 2048
TEMPERATURE = 0.7

# Create agent
agent = Agent(
    name="claude_functions",
    seed="claude-functions-seed-phrase-12345",  # Change this for your agent
    port=8003,
    mailbox=True  # Required for Agentverse deployment
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# System prompt
SYSTEM_PROMPT = """You are a helpful AI assistant with access to various tools and functions. 
You can help users by calling these tools when needed.

When using tools:
- Choose the right tool for the task
- Extract necessary parameters from the user's request
- Explain what you're doing
- Present results in a clear, friendly way

Always aim to be helpful, accurate, and efficient."""


# ========== TOOL DEFINITIONS ==========

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather information for a specific city. Returns temperature, conditions, humidity, and wind speed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name, e.g., 'San Francisco', 'London', 'Tokyo'"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units (celsius or fahrenheit)",
                    "default": "fahrenheit"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations. Supports basic arithmetic, exponents, and common math functions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '2 + 2', '10 * 5', 'sqrt(16)', '2 ** 8'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time in a specific timezone or UTC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo') or 'UTC'",
                    "default": "UTC"
                }
            },
            "required": []
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for information. Returns a summary of relevant results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]


# ========== TOOL IMPLEMENTATIONS ==========

def get_weather(city: str, units: str = "fahrenheit") -> dict:
    """Get weather for a city (mock implementation - replace with real API)"""
    # In production, use a real weather API like OpenWeatherMap
    # For demo purposes, returning mock data
    
    mock_weather = {
        "san francisco": {"temp": 65, "condition": "Partly Cloudy", "humidity": 70, "wind": 12},
        "london": {"temp": 55, "condition": "Rainy", "humidity": 85, "wind": 15},
        "tokyo": {"temp": 72, "condition": "Clear", "humidity": 60, "wind": 8},
        "new york": {"temp": 58, "condition": "Sunny", "humidity": 65, "wind": 10},
        "default": {"temp": 70, "condition": "Clear", "humidity": 50, "wind": 5}
    }
    
    city_lower = city.lower()
    weather = mock_weather.get(city_lower, mock_weather["default"])
    
    # Convert to celsius if needed
    temp = weather["temp"]
    if units == "celsius":
        temp = round((temp - 32) * 5/9, 1)
        unit_symbol = "°C"
    else:
        unit_symbol = "°F"
    
    return {
        "city": city,
        "temperature": f"{temp}{unit_symbol}",
        "condition": weather["condition"],
        "humidity": f"{weather['humidity']}%",
        "wind_speed": f"{weather['wind']} mph"
    }


def calculate(expression: str) -> dict:
    """Safely evaluate mathematical expressions"""
    try:
        # Import math for functions like sqrt, sin, cos, etc.
        import math
        
        # Safe evaluation namespace (no exec, eval of arbitrary code)
        safe_dict = {
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'pi': math.pi,
            'e': math.e,
            'abs': abs,
            'round': round,
            'pow': pow,
        }
        
        # Evaluate the expression
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        
        return {
            "expression": expression,
            "result": result,
            "success": True
        }
    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "success": False
        }


def get_current_time(timezone: str = "UTC") -> dict:
    """Get current time in specified timezone"""
    try:
        from datetime import datetime
        import pytz
        
        if timezone == "UTC":
            tz = pytz.UTC
        else:
            tz = pytz.timezone(timezone)
        
        current_time = datetime.now(tz)
        
        return {
            "timezone": timezone,
            "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S"),
            "day_of_week": current_time.strftime("%A"),
            "success": True
        }
    except Exception as e:
        return {
            "timezone": timezone,
            "error": str(e),
            "success": False
        }


def search_web(query: str, num_results: int = 5) -> dict:
    """Search the web (mock implementation - replace with real search API)"""
    # In production, use DuckDuckGo API, Google Custom Search, or similar
    # For demo purposes, returning mock results
    
    mock_results = [
        {
            "title": f"Result 1 for '{query}'",
            "snippet": f"This is a relevant result about {query}. It contains useful information...",
            "url": f"https://example.com/result1"
        },
        {
            "title": f"Result 2 for '{query}'",
            "snippet": f"Another great source discussing {query} in detail...",
            "url": f"https://example.com/result2"
        },
        {
            "title": f"Result 3 for '{query}'",
            "snippet": f"Comprehensive guide to {query} with examples...",
            "url": f"https://example.com/result3"
        }
    ]
    
    return {
        "query": query,
        "results": mock_results[:num_results],
        "num_results": min(num_results, len(mock_results)),
        "success": True
    }


# Map tool names to functions
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
    "get_current_time": get_current_time,
    "search_web": search_web
}


# ========== HELPER FUNCTIONS ==========

def create_text_chat(text: str) -> ChatMessage:
    """Create a ChatMessage with TextContent"""
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text, type="text")]
    )


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return the result as a string"""
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        result = TOOL_FUNCTIONS[tool_name](**tool_input)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e), "success": False})


# ========== AGENT HANDLERS ==========

@agent.on_event("startup")
async def startup(ctx: Context):
    """Initialize agent on startup"""
    ctx.logger.info("🛠️ Starting Claude Function Calling Agent...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        ctx.logger.info("✅ Claude Function Calling API configured")
        ctx.logger.info(f"🔧 Available tools: {', '.join(TOOL_FUNCTIONS.keys())}")
    else:
        ctx.logger.error("❌ Anthropic API key not set")
    
    # Initialize storage
    ctx.storage.set("total_messages", 0)
    ctx.storage.set("total_tool_calls", 0)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with function calling"""
    
    try:
        # Extract text from message
        user_text = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break
        
        if not user_text:
            ctx.logger.warning("No text content in message")
            return
        
        # Log incoming message
        ctx.logger.info(f"📨 Message from {sender}: {user_text[:50]}...")
        
        # Send acknowledgement
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        ))
        
        # Build messages for Claude
        messages = [{
            "role": "user",
            "content": user_text
        }]
        
        # Loop to handle multiple tool calls
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call Claude with tools
            ctx.logger.info(f"🤔 Calling Claude (iteration {iteration})...")
            
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )
            
            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Extract tool use from response
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                
                ctx.logger.info(f"🔧 Claude wants to use {len(tool_uses)} tool(s)")
                
                # Add assistant's response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Execute each tool
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.name
                    tool_input = tool_use.input
                    
                    ctx.logger.info(f"⚙️ Executing tool: {tool_name}")
                    
                    # Execute the tool
                    result = execute_tool(tool_name, tool_input)
                    
                    ctx.logger.info(f"✅ Tool result: {result[:100]}...")
                    
                    # Track stats
                    total_calls = ctx.storage.get("total_tool_calls") or 0
                    ctx.storage.set("total_tool_calls", total_calls + 1)
                    
                    # Add tool result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result
                    })
                
                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue the loop to get Claude's final response
                continue
                
            else:
                # Claude provided a final answer
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text
                
                ctx.logger.info(f"✅ Final response: {response_text[:50]}...")
                
                # Track stats
                total = ctx.storage.get("total_messages") or 0
                ctx.storage.set("total_messages", total + 1)
                
                # Send response back to user
                await ctx.send(sender, create_text_chat(response_text))
                ctx.logger.info(f"💬 Response sent to {sender}")
                
                # Exit the loop
                break
        
        if iteration >= max_iterations:
            ctx.logger.warning("⚠️ Max iterations reached")
            await ctx.send(sender, create_text_chat(
                "I've reached the maximum number of tool calls for this request. Please try breaking it into smaller questions."
            ))
        
    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        import traceback
        ctx.logger.error(traceback.format_exc())
        
        error_msg = f"""❌ **Error Processing Request**

{str(e)[:200]}

Please try:
- Rephrasing your question
- Breaking complex requests into simpler ones
- Waiting a moment and trying again
"""
        
        await ctx.send(sender, create_text_chat(error_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle message acknowledgements"""
    ctx.logger.debug(f"✓ Message {msg.acknowledged_msg_id} acknowledged by {sender}")


# Include the chat protocol
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🛠️ Starting Claude Function Calling Agent...")
    print(f"📍 Agent address: {agent.address}")
    
    if anthropic_api_key:
        print("✅ Claude Function Calling API configured")
        print(f"   Using model: {MODEL_NAME}")
    else:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        print("   Please add it to your .env file")
        exit(1)
    
    print("\n🔧 Available Tools:")
    for tool in TOOLS:
        print(f"   • {tool['name']}: {tool['description'][:60]}...")
    
    print("\n🎯 Example Queries:")
    print("   • What's the weather in San Francisco?")
    print("   • Calculate 15 * 23 + 100")
    print("   • What time is it in Tokyo?")
    print("   • Search for latest AI news")
    
    print("\n✅ Agent is running! Send queries via ASI One.")
    print("   Press Ctrl+C to stop.\n")
    
    agent.run()
