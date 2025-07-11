#!/usr/bin/env python3
"""
Airbnb MCP Agent for Agentverse

Provides real-time Airbnb property search and booking information 
via Airbnb MCP server integration. Makes it discoverable on ASI:One LLM.
"""

import os
import json
import asyncio
import secrets
from typing import Dict, Any, Optional
from contextlib import AsyncExitStack
import time
import mcp
from mcp.client.stdio import stdio_client
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    EndSessionContent,
    StartSessionContent,
)
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic

# --- Agent Configuration ---

# Load environment variables from a .env file
load_dotenv()

# Get API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")

AGENT_NAME = "airbnb_agent"
AGENT_PORT = 8008

# User sessions store: session_id -> {authenticated, last_activity}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Session timeout (30 minutes)
SESSION_TIMEOUT = 30 * 60

# --- MCP Client Logic ---

class AirbnbMCPClient:
    """Airbnb MCP Client for property search and booking assistance"""
    
    def __init__(self, ctx: Context):
        self._ctx = ctx
        self._session: mcp.ClientSession = None
        self._exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.tools = []  # Will be populated after connection

    async def connect(self):
        """Connect to Airbnb MCP server via npx"""
        try:
            self._ctx.logger.info("Connecting to Airbnb MCP server via npx...")
            
            # Connect to the Airbnb MCP server using npx
            server_params = mcp.StdioServerParameters(
                command="npx",
                args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
                env=None
            )
            
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            self._session = await self._exit_stack.enter_async_context(
                mcp.ClientSession(stdio_transport[0], stdio_transport[1])
            )
            
            await self._session.initialize()
            
            # Get available tools
            list_tools_response = await self._session.list_tools()
            mcp_tools = list_tools_response.tools
            
            self._ctx.logger.info(f"Connected to Airbnb MCP server with {len(mcp_tools)} tools")
            for tool in mcp_tools:
                self._ctx.logger.info(f"Available tool: {tool.name}")
            
            # Convert MCP tools to Anthropic format
            self.tools = self._convert_mcp_tools_to_anthropic_format(mcp_tools)
            
        except Exception as e:
            self._ctx.logger.error(f"Failed to connect to Airbnb MCP server: {e}")
            raise

    def _convert_mcp_tools_to_anthropic_format(self, mcp_tools):
        """Convert MCP tool definitions to Anthropic tool format"""
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description or f"Airbnb tool: {tool.name}",
                "input_schema": tool.inputSchema or {"type": "object", "properties": {}}
            }
            anthropic_tools.append(anthropic_tool)
        return anthropic_tools

    async def process_query(self, query: str) -> str:
        """Process user query using Anthropic for tool selection and then call Airbnb tools"""
        self._ctx.logger.info(f"Processing Airbnb query: '{query}'")
        try:
            # Let Claude decide how to use the Airbnb tools
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{
                    "role": "user", 
                    "content": f"""Help me with this Airbnb request: {query}

Please use the available Airbnb tools to search for properties, get listing details, or provide accommodation assistance. 
Make sure to provide helpful, accurate information about available properties and booking options."""
                }],
                tools=self.tools,
            )

            tool_use = next((content for content in response.content if content.type == 'tool_use'), None)

            # If the model wants to use a tool
            if tool_use:
                tool_name = tool_use.name
                tool_input = tool_use.input
                self._ctx.logger.info(f"Claude selected Airbnb tool: {tool_name} with input: {tool_input}")

                # Call the selected tool on the Airbnb MCP server
                mcp_response = await self._session.call_tool(tool_name, tool_input)
                
                # Debug: Log the raw MCP response
                self._ctx.logger.info(f"MCP Response type: {type(mcp_response)}")
                self._ctx.logger.info(f"MCP Response content type: {type(mcp_response.content)}")
                
                # Format the response for the user
                return self.format_response(mcp_response.content)
            
            # If the model just wants to chat
            text_response = next((content for content in response.content if content.type == 'text'), None)
            if text_response:
                return text_response.text

            return "I can help you search for Airbnb properties, get listing details, and assist with accommodation planning. What would you like to know?"

        except Exception as e:
            self._ctx.logger.error(f"Error processing Airbnb query: {e}")
            return f"Sorry, an error occurred while processing your Airbnb request: {e}"

    def format_response(self, content: Any) -> str:
        """Format the response from Airbnb MCP server for the user"""
        try:
            # Handle different response formats
            if isinstance(content, list):
                if len(content) > 0 and hasattr(content[0], 'text'):
                    # TextContent format
                    raw_data = content[0].text
                elif len(content) > 0 and isinstance(content[0], dict):
                    # Dictionary format
                    raw_data = content[0]
                else:
                    raw_data = content
            elif isinstance(content, dict):
                raw_data = content
            else:
                raw_data = str(content)

            # Parse JSON if it's a string
            if isinstance(raw_data, str):
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    return f"🏠 Airbnb Response:\n{raw_data}"
            else:
                data = raw_data

            # Format based on structure
            if isinstance(data, dict) and "searchResults" in data:
                return self._format_search_results(data)
            elif isinstance(data, dict):
                return self._format_airbnb_response(data)
            else:
                return f"🏠 Airbnb Response:\n{json.dumps(data, indent=2)}"

        except Exception as e:
            self._ctx.logger.error(f"Error formatting response: {e}")
            return f"🏠 Airbnb Response:\n{str(content)}"

    def _format_search_results(self, data: Dict) -> str:
        """Format search results based on actual Airbnb JSON structure"""
        search_results = data.get("searchResults", [])
        search_url = data.get("searchUrl", "")
        
        if not search_results:
            return "🏠 No Airbnb listings found for your search criteria."
        
        # Header with search URL
        formatted_response = f"🏠 **Found {len(search_results)} Airbnb Properties**\n\n"
        if search_url:
            formatted_response += f"🔗 [View all results on Airbnb]({search_url})\n\n"
        
        # Format top 5 results
        for i, result in enumerate(search_results[:5], 1):
            # Extract data from the complex structure
            name = ""
            price = ""
            rating = ""
            bed_info = ""
            badges = ""
            
            try:
                # Extract name
                if "demandStayListing" in result and "description" in result["demandStayListing"]:
                    name_obj = result["demandStayListing"]["description"].get("name", {})
                    if "localizedStringWithTranslationPreference" in name_obj:
                        name = name_obj["localizedStringWithTranslationPreference"]
                
                # Extract price
                if "structuredDisplayPrice" in result and "primaryLine" in result["structuredDisplayPrice"]:
                    price = result["structuredDisplayPrice"]["primaryLine"].get("accessibilityLabel", "")
                
                # Extract rating
                if "avgRatingA11yLabel" in result:
                    rating = result["avgRatingA11yLabel"]
                
                # Extract bed info
                if "structuredContent" in result and "primaryLine" in result["structuredContent"]:
                    bed_info = result["structuredContent"]["primaryLine"]
                
                # Extract badges
                badges = result.get("badges", "")
                
                # Get URL
                url = result.get("url", "")
                
            except (KeyError, TypeError) as e:
                self._ctx.logger.warning(f"Error extracting data from result {i}: {e}")
            
            # Format the listing
            formatted_response += f"**{i}. {name or 'Property Name Not Available'}**\n"
            if url:
                formatted_response += f"🔗 [View Details]({url})\n"
            if bed_info:
                formatted_response += f"🛏️ {bed_info}\n"
            if price:
                formatted_response += f"💰 {price}\n"
            if rating:
                formatted_response += f"⭐ {rating}\n"
            if badges and badges.strip():
                formatted_response += f"🏆 {badges}\n"
            formatted_response += "\n"
        
        if len(search_results) > 5:
            formatted_response += f"... and {len(search_results) - 5} more properties available.\n"
        
        return formatted_response

    def _format_airbnb_response(self, data: Dict) -> str:
        """Format Airbnb API response for better readability"""
        if "listings" in data:
            return self._format_airbnb_listings(data["listings"])
        elif "listing" in data:
            return self._format_single_listing(data["listing"])
        elif "id" in data and "name" in data:
            return self._format_single_listing(data)
        else:
            return f"🏠 **Airbnb Information**\n\n```json\n{json.dumps(data, indent=2)}\n```"

    def _format_airbnb_listings(self, listings: list) -> str:
        """Format multiple Airbnb listings"""
        if not listings:
            return "🏠 No Airbnb listings found for your search criteria."
        
        formatted_response = f"🏠 **Found {len(listings)} Airbnb Properties**\n\n"
        
        for i, listing in enumerate(listings[:5], 1):  # Limit to top 5
            name = listing.get("name", "Property Name Not Available")
            price = listing.get("price", {}).get("total", "Price not available")
            location = listing.get("location", "Location not specified")
            rating = listing.get("rating", "No rating")
            listing_id = listing.get("id", "N/A")
            
            formatted_response += f"**{i}. {name}**\n"
            formatted_response += f"📍 Location: {location}\n"
            formatted_response += f"💰 Price: {price}\n"
            formatted_response += f"⭐ Rating: {rating}\n"
            formatted_response += f"🆔 ID: {listing_id}\n\n"
        
        if len(listings) > 5:
            formatted_response += f"... and {len(listings) - 5} more properties available.\n"
        
        return formatted_response

    def _format_single_listing(self, listing: Dict) -> str:
        """Format a single Airbnb listing with detailed information"""
        name = listing.get("name", "Property Name Not Available")
        description = listing.get("description", "No description available")
        price = listing.get("price", {}).get("total", "Price not available")
        location = listing.get("location", "Location not specified")
        rating = listing.get("rating", "No rating")
        amenities = listing.get("amenities", [])
        host = listing.get("host", {}).get("name", "Host information not available")
        
        formatted_response = f"🏠 **{name}**\n\n"
        formatted_response += f"📍 **Location:** {location}\n"
        formatted_response += f"💰 **Price:** {price}\n"
        formatted_response += f"⭐ **Rating:** {rating}\n"
        formatted_response += f"👤 **Host:** {host}\n\n"
        
        if description:
            formatted_response += f"📝 **Description:**\n{description[:300]}{'...' if len(description) > 300 else ''}\n\n"
        
        if amenities:
            formatted_response += f"🏠 **Amenities:** {', '.join(amenities[:10])}\n"
            if len(amenities) > 10:
                formatted_response += f"... and {len(amenities) - 10} more amenities\n"
        
        return formatted_response

    async def cleanup(self):
        """Clean up the MCP connection"""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._ctx.logger.info("Airbnb MCP connection cleaned up")
        except Exception as e:
            self._ctx.logger.error(f"Error during Airbnb MCP cleanup: {e}")

# --- uAgent Setup ---

chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name=AGENT_NAME, port=AGENT_PORT, mailbox=True)

# Store MCP clients per session
airbnb_clients: Dict[str, AirbnbMCPClient] = {}

def is_session_valid(session_id: str) -> bool:
    """Check if session is valid and hasn't expired"""
    if session_id not in user_sessions:
        return False
    
    session = user_sessions[session_id]
    current_time = time.time()
    
    if current_time - session["last_activity"] > SESSION_TIMEOUT:
        # Session expired
        del user_sessions[session_id]
        return False
    
    # Update last activity
    session["last_activity"] = current_time
    return True

async def get_airbnb_client(ctx: Context, session_id: str) -> AirbnbMCPClient:
    """Get or create Airbnb MCP client for session"""
    if session_id not in airbnb_clients:
        client = AirbnbMCPClient(ctx)
        await client.connect()
        airbnb_clients[session_id] = client
    return airbnb_clients[session_id]

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""
    
    # Extract text from content (handle both list and direct text formats)
    try:
        if isinstance(msg.content, list):
            # Content is a list, extract text from first item
            if len(msg.content) > 0:
                if hasattr(msg.content[0], 'text'):
                    user_text = msg.content[0].text
                else:
                    user_text = str(msg.content[0])
            else:
                user_text = "[Empty message]"
        elif hasattr(msg.content, 'text'):
            # Content has direct text attribute
            user_text = msg.content.text
        else:
            # Fallback to string representation
            user_text = str(msg.content)
    except Exception as e:
        ctx.logger.error(f"Error extracting message text: {e}")
        user_text = "[Could not parse message]"
    
    ctx.logger.info(f"Received message from {sender}: '{user_text}'")
    
    # Extract or create session ID
    session_id = getattr(msg, 'session_id', None) or str(uuid4())
    
    # Validate session
    if not is_session_valid(session_id):
        user_sessions[session_id] = {
            "authenticated": True,
            "last_activity": time.time()
        }
    
    try:
        # Get Airbnb MCP client for this session
        airbnb_client = await get_airbnb_client(ctx, session_id)
        
        # Process the query
        response_text = await airbnb_client.process_query(user_text)
        
        # Send response
        response_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=str(uuid4()),
            content=[TextContent(type="text", text=response_text)]
        )
        
        await ctx.send(sender, response_msg)
        ctx.logger.info(f"Sent response to {sender}")
        
    except Exception as e:
        ctx.logger.error(f"Error handling message: {e}")
        error_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=str(uuid4()),
            content=[TextContent(type="text", text=f"Sorry, I encountered an error: {str(e)}")]
        )
        await ctx.send(sender, error_msg)

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender}")

@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    """Clean up resources on shutdown"""
    ctx.logger.info("Shutting down Airbnb agent...")
    for client in airbnb_clients.values():
        await client.cleanup()

agent.include(chat_proto)

if __name__ == "__main__":
    print(f"Airbnb Agent starting on http://localhost:{AGENT_PORT}")
    print(f"Agent address: {agent.address}")
    print("🏠 Ready to help you find the perfect Airbnb!")
    agent.run()
