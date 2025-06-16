# mcp_client.py
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Any
import json
import logging
import traceback  # Added for detailed error tracing
import os
from datetime import datetime

# Configure logging - increase level for more details
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_client")

# Add file logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"mcp_client_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Function to log to file directly
def log_to_file(message):
    """Write a message directly to the log file"""
    with open(log_file, 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        f.write(f"[{timestamp}] {message}\n")

# Global variable to store MCP session
mcp_session = None
mcp_exit_stack = None

async def connect_to_airbnb_mcp():
    """Connect to the Airbnb MCP server"""
    global mcp_session, mcp_exit_stack
    
    mcp_exit_stack = AsyncExitStack()
    
    try:
        logger.info("Connecting to Airbnb MCP server")
        
        # Configure the MCP server connection using NPX
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            env={}
        )
        
        # Connect to the server
        stdio_transport = await mcp_exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        mcp_session = await mcp_exit_stack.enter_async_context(ClientSession(stdio, write))
        
        # Initialize the session
        await mcp_session.initialize()
        
        # Get available tools to verify connection
        response = await mcp_session.list_tools()
        tools = response.tools
        
        logger.info(f"Connected to Airbnb MCP server with tools: {[tool.name for tool in tools]}")
        return True
        
    except Exception as e:
        if mcp_exit_stack:
            await mcp_exit_stack.aclose()
        logger.error(f"Error connecting to Airbnb MCP server: {str(e)}")
        logger.error(traceback.format_exc())  # Print full stack trace
        return False

async def search_airbnb_listings(location: str, limit: int = 4, **kwargs):
    """Search for Airbnb listings with detailed logging"""
    global mcp_session
    
    # Log to both console and file
    logger.debug(f"==== SEARCH REQUEST STARTED ====")
    logger.debug(f"Location: {location}")
    logger.debug(f"Additional parameters: {kwargs}")
    
    # Direct file logging
    log_to_file(f"==== SEARCH REQUEST STARTED ====")
    log_to_file(f"Location: {location}")
    log_to_file(f"Additional parameters: {kwargs}")
    log_to_file(f"Current time: {datetime.now().isoformat()}")
    log_to_file(f"MCP session exists: {mcp_session is not None}")
    
    if not mcp_session:
        logger.error("No MCP session available")
        return {"success": False, "message": "Not connected to Airbnb MCP server"}
    
    try:
        # Prepare parameters
        params = {"location": location, **kwargs}
        logger.info(f"Searching for listings in {location} with params: {params}")
        
        # Call the airbnb_search tool with detailed logging
        logger.debug("About to call airbnb_search tool")
        log_to_file(f"CALLING MCP TOOL: airbnb_search with params: {params}")
        
        try:
            start_time = datetime.now()
            log_to_file(f"MCP CALL START TIME: {start_time.isoformat()}")
            
            result = await mcp_session.call_tool("airbnb_search", params)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
        except Exception as call_error:
            raise  # Re-raise the exception for normal error handling
        
        # Extract text content from the response
        if hasattr(result.content, '__iter__') and not isinstance(result.content, str):
            
            for i, item in enumerate(result.content):
                logger.debug(f"Processing item {i} of type: {type(item)}")
                
                if hasattr(item, 'text'):
                    logger.debug(f"Item has text attribute of length: {len(item.text) if hasattr(item.text, '__len__') else 'unknown'}")
                    logger.debug(f"Text sample: {item.text[:100]}..." if hasattr(item.text, '__len__') else "Cannot display text")
                    
                    try:
                        # Parse the JSON response
                        logger.debug("Attempting to parse JSON")
                        parsed_content = json.loads(item.text)
                        logger.debug(f"JSON parsed successfully with keys: {list(parsed_content.keys())}")
                        
                        search_results = parsed_content.get("searchResults", [])
                        logger.debug(f"Found {len(search_results)} search results")
                        
                        # Limit results
                        limited_results = search_results[:limit]
                        logger.debug(f"Limited to {len(limited_results)} results")
                        
                        # Extract only essential information for each listing
                        simplified_listings = []
                        for j, listing in enumerate(limited_results):
                            logger.debug(f"Processing listing {j+1} with ID: {listing.get('id', 'N/A')}")
                            
                            try:
                                listing_name = listing.get("demandStayListing", {}).get("description", {}).get("name", {}).get("localizedStringWithTranslationPreference", "Unnamed Listing")
                                listing_price = listing.get("structuredDisplayPrice", {}).get("primaryLine", {}).get("accessibilityLabel", "Price not available")
                                
                                listing_info = {
                                    "id": listing.get("id", "N/A"),
                                    "name": listing_name,
                                    "price": listing_price,
                                    "rating": listing.get("avgRatingA11yLabel", "Not rated"),
                                    "url": listing.get("url", "N/A")
                                }
                                logger.debug(f"Extracted listing info: {listing_info}")
                                simplified_listings.append(listing_info)
                            except Exception as listing_err:
                                logger.error(f"Error processing listing {j+1}: {str(listing_err)}")
                        
                        # Create a simple formatted output
                        logger.debug("Creating formatted output")
                        log_to_file("CREATING FORMATTED OUTPUT FOR SEARCH RESULTS")
                        formatted_output = f"AIRBNB LISTINGS IN {location.upper()}\n\n"
                        formatted_output += f"Found {len(search_results)} listings. Showing top {len(simplified_listings)}:\n\n"
                        
                        for j, listing in enumerate(simplified_listings, 1):
                            formatted_output += f"{j}. {listing['name']}\n"
                            formatted_output += f"   Price: {listing['price']}\n"
                            formatted_output += f"   Rating: {listing['rating']}\n"
                            formatted_output += f"   ID: {listing['id']}\n"
                            formatted_output += f"   URL: {listing['url']}\n\n"
                        
                        logger.debug("Returning successful result")
                        log_to_file(f"FORMATTED OUTPUT CREATED (length: {len(formatted_output)})")
                        log_to_file(f"FORMATTED OUTPUT SAMPLE: {formatted_output[:200]}...")
                        
                        result_dict = {
                            "success": True,
                            "message": "Successfully retrieved listings",
                            "formatted_output": formatted_output,
                            "listings": simplified_listings,
                            "total_listings": len(search_results)
                        }
                        
                        return result_dict
                        
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decode error: {str(json_err)}")
                        logger.error(f"Text that failed to parse: {item.text[:500]}...")
                        return {"success": False, "message": "Error parsing JSON response"}
                else:
                    logger.debug(f"Item does not have text attribute")
            
            return {"success": False, "message": "No valid content found in response"}
        else:
            return {"success": False, "message": f"Unexpected response format: {type(result.content)}"}
    
    except Exception as e:
        error_msg = f"Error searching for Airbnb listings: {str(e)}"
        return {"success": False, "message": error_msg}

async def get_airbnb_listing_details(listing_id: str, **kwargs):
    """Get details for a specific Airbnb listing with detailed logging"""
    global mcp_session
    
    logger.debug(f"==== DETAILS REQUEST STARTED ====")
    logger.debug(f"Listing ID: {listing_id}")
    logger.debug(f"Additional parameters: {kwargs}")
    
    if not mcp_session:
        logger.error("No MCP session available")
        return {"success": False, "message": "Not connected to Airbnb MCP server"}
    
    try:
        # Prepare parameters
        params = {"id": listing_id, **kwargs}
        logger.info(f"Getting details for listing {listing_id} with params: {params}")
        
        # Call the airbnb_listing_details tool
        logger.debug("About to call airbnb_listing_details tool")
        result = await mcp_session.call_tool("airbnb_listing_details", params)
        logger.debug(f"Tool call completed - Result type: {type(result)}")
        
        # Debug the content structure
        logger.debug(f"Content type: {type(result.content)}")
        if hasattr(result.content, '__iter__') and not isinstance(result.content, str):
            logger.debug(f"Content is iterable with {len(result.content)} items")
        
        # Extract text content from the response
        if hasattr(result.content, '__iter__') and not isinstance(result.content, str):
            logger.debug("Processing iterable content")
            
            for i, item in enumerate(result.content):
                logger.debug(f"Processing item {i} of type: {type(item)}")
                
                if hasattr(item, 'text'):
                    logger.debug(f"Item has text attribute of length: {len(item.text) if hasattr(item.text, '__len__') else 'unknown'}")
                    logger.debug(f"Text sample: {item.text[:100]}..." if hasattr(item.text, '__len__') else "Cannot display text")
                    
                    try:
                        # Parse the JSON response
                        logger.debug("Attempting to parse JSON")
                        details = json.loads(item.text)
                        logger.debug(f"JSON parsed successfully with keys: {list(details.keys())}")
                        
                        # Extract only essential information
                        logger.debug("Extracting essential details")
                        simplified_details = {
                            "name": details.get("name", "N/A"),
                            "description": details.get("description", "No description available"),
                            "bedrooms": details.get("bedrooms", "N/A"),
                            "bathrooms": details.get("bathrooms", "N/A"),
                            "guests": details.get("maxGuests", "N/A"),
                            "price": details.get("price", {}).get("rate", "N/A")
                        }
                        
                        # Extract amenities
                        amenities = details.get("amenities", [])
                        logger.debug(f"Found {len(amenities)} amenities")
                        
                        amenity_names = []
                        for j, amenity in enumerate(amenities[:5]):
                            amenity_name = amenity.get("name", "Unknown Amenity")
                            logger.debug(f"Amenity {j+1}: {amenity_name}")
                            amenity_names.append(amenity_name)
                        
                        simplified_details["amenities"] = amenity_names
                        
                        # Create a simple formatted output
                        logger.debug("Creating formatted output")
                        formatted_output = f"DETAILS FOR LISTING: {simplified_details['name']}\n\n"
                        formatted_output += f"Bedrooms: {simplified_details['bedrooms']}\n"
                        formatted_output += f"Bathrooms: {simplified_details['bathrooms']}\n"
                        formatted_output += f"Max Guests: {simplified_details['guests']}\n"
                        formatted_output += f"Price: {simplified_details['price']}\n\n"
                        
                        if simplified_details['amenities']:
                            formatted_output += "Top Amenities:\n"
                            for j, amenity in enumerate(simplified_details['amenities'], 1):
                                formatted_output += f"- {amenity}\n"
                        
                        # Add a short description
                        desc = simplified_details['description']
                        short_desc = desc[:200] + "..." if len(desc) > 200 else desc
                        formatted_output += f"\nDescription: {short_desc}\n"
                        
                        logger.debug("Returning successful result")
                        result_dict = {
                            "success": True,
                            "message": "Successfully retrieved listing details",
                            "formatted_output": formatted_output,
                            "details": simplified_details
                        }
                        logger.debug("==== DETAILS REQUEST COMPLETED SUCCESSFULLY ====")
                        return result_dict
                        
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decode error: {str(json_err)}")
                        logger.error(f"Text that failed to parse: {item.text[:500]}...")
                        return {"success": False, "message": "Error parsing JSON response"}
                else:
                    logger.debug(f"Item does not have text attribute")
            
            logger.error("No valid content found in response")
            return {"success": False, "message": "No valid content found in response"}
        else:
            logger.error(f"Unexpected response format: {type(result.content)}")
            if isinstance(result.content, str):
                logger.error(f"Content (string): {result.content[:500]}...")
            return {"success": False, "message": f"Unexpected response format: {type(result.content)}"}
    
    except Exception as e:
        error_msg = f"Error getting Airbnb listing details: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())  # Print full stack trace
        return {"success": False, "message": error_msg}

async def cleanup_mcp_connection():
    """Clean up MCP connection"""
    global mcp_session, mcp_exit_stack
    
    if mcp_exit_stack:
        try:
            await mcp_exit_stack.aclose()
            logger.info("MCP connection closed")
        except Exception as e:
            logger.error(f"Error closing MCP connection: {str(e)}")
            logger.error(traceback.format_exc())  # Print full stack trace
    
    mcp_session = None
    mcp_exit_stack = None