# chat_proto.py
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict
from textwrap import dedent
import logging
import time
import asyncio
import os
from datetime import datetime



from uagents import Context, Model, Protocol

# Import the necessary components of the chat protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from mcp_client import search_airbnb_listings, get_airbnb_listing_details

# Set up loggin

# OpenAI Agent address for structured output
AI_AGENT_ADDRESS = 'agent1qtlpfshtlcxekgrfcpmv7m9zpajuwu7d5jfyachvpa4u3dkt6k0uwwp2lct'

def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    """Create a chat message with text content and optional end session marker"""
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)
        
    # Create content list with text content
    content = [TextContent(type="text", text=text)]
    
    # Add end session marker if requested
    if end_session:
        content.append(EndSessionContent(type="end-session"))
        
    # Create and return the message
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=str(uuid4()),
        content=content,
    )

# Define the Airbnb request and response models
class AirbnbRequest(Model):
    """Model for requesting Airbnb information"""
    request_type: str  # "search" or "details"
    parameters: dict

class AirbnbResponse(Model):
    """Response with Airbnb information"""
    results: str

# Set up the protocols
chat_proto = Protocol(spec=chat_protocol_spec)
struct_output_client_proto = Protocol(
    name="StructuredOutputClientProtocol", version="0.1.0"
)

class AirbnbRequest(Model):
    """Model for requesting Airbnb information"""
    request_type: str  # "search" or "details"
    parameters: Dict[str, Any]

class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]

class StructuredOutputResponse(Model):
    output: dict[str, Any]

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages from users"""
    # Extract text content from the message
    text_content = None
    if msg.content:
        text_content = next((item.text for item in msg.content if isinstance(item, TextContent)), None)
        if text_content:
            ctx.logger.info(f"Got a message from {sender}: {text_content}")
    
    # Store the sender for this session
    ctx.storage.set(str(ctx.session), sender)
    
    # Send acknowledgement
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    # Process message content
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            continue
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Processing text message: {item.text}")
            
            # Create prompt for AI agent
            prompt_text = dedent(f"""
                You are an AI assistant that processes user requests for Airbnb rentals.
                Your task is to generate a JSON object that strictly follows the provided schema for an `AirbnbRequest`.
                The JSON object must include the `request_type` and `parameters` fields.
                Your entire output must be ONLY the JSON object. Do not include any conversational text, markdown formatting, or the schema definition itself.

                Analyze the following user query and create the JSON object.

                User query: \"{item.text}\"
            """)
            
            ctx.logger.info(f"Preparing to send prompt to AI agent: {AI_AGENT_ADDRESS}")
            
            try:
                # Set a flag in storage to track that we're waiting for AI response
                ctx.storage.set("waiting_for_ai_response", "true")
                ctx.storage.set("ai_request_time", str(time.time()))
                
                # Send the prompt to the AI agent
                ctx.logger.info("Sending prompt to AI agent...")
                await ctx.send(
                    AI_AGENT_ADDRESS,
                    StructuredOutputPrompt(
                        prompt=prompt_text,
                        output_schema=AirbnbRequest.schema()
                    )
                )
                
                ctx.logger.info("Successfully sent prompt to AI agent")
                ctx.logger.info(f"Now waiting for response from: {AI_AGENT_ADDRESS}")
                
                # Get the session sender from storage
                session_sender = ctx.storage.get(str(ctx.session))
                if session_sender:
                    ctx.logger.info(f"Using session sender: {session_sender}")
                else:
                    ctx.logger.warning("No session sender found in storage")
                    
                # Schedule a check for AI response timeout
                ctx.logger.info("Scheduling timeout check for AI response")
                asyncio.create_task(check_ai_response_timeout(ctx, session_sender))
                
            except Exception as e:
                ctx.logger.error(f"Error sending to AI agent: {e}")
                session_sender = ctx.storage.get(str(ctx.session))
                
                # If we have a session sender, attempt fallback search
                if session_sender:
                    ctx.logger.warning("Attempting direct search as fallback")
                    await handle_fallback_search(ctx, session_sender, item.text)
                else:
                    ctx.logger.error("Cannot perform fallback: No session sender found")
        else:
            ctx.logger.info(f"Got unexpected content type: {type(item)}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )

@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_structured_output_response(
    ctx: Context, sender: str, msg: StructuredOutputResponse
):
    """Handle structured output responses from the AI agent"""
    try:
        # Log basic information about the received response
        ctx.logger.info(f"Received structured output response from {sender}")
        ctx.logger.info(f"Output type: {type(msg.output)}")
        ctx.logger.info(f"Output content: {msg.output}")
        
        # Get the session sender from storage
        session_sender = ctx.storage.get(str(ctx.session))
        if session_sender is None:
            ctx.logger.error("Discarding message because no session sender found in storage")
            return

        # Check for unknown values in the output
        output_str = str(msg.output)
        if "<UNKNOWN>" in output_str:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I couldn't understand what Airbnb information you're looking for. Please specify if you want to search for listings in a location or get details about a specific listing."
                )
            )
            return

        # Check if we were waiting for this response
        waiting_flag = ctx.storage.get("waiting_for_ai_response")
        ctx.logger.info(f"Waiting flag status: {waiting_flag}")
        
        # Clear the waiting flag
        if waiting_flag == "true":
            ctx.storage.set("waiting_for_ai_response", "false")
            ctx.logger.info("Cleared waiting flag")
        
        # Parse the output to AirbnbRequest model
        try:
            ctx.logger.info("Parsing output to AirbnbRequest model")
            request = AirbnbRequest.parse_obj(msg.output)
            ctx.logger.info(f"Successfully parsed request: {request.request_type} with parameters: {request.parameters}")
        except Exception as parse_err:
            ctx.logger.error(f"Error parsing output: {parse_err}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I had trouble understanding the request. Please try rephrasing your question."
                )
            )
            return
        
        # Validate request has required fields
        if not request.request_type or not request.parameters:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I couldn't identify the request type or parameters. Please provide more details for your Airbnb query."
                )
            )
            return

        try:
            if request.request_type == "search":
                ctx.logger.info("Processing search request")
                # Get search parameters
                location = request.parameters.get("location")
                
                if not location:
                    ctx.logger.info("No location provided, asking for clarification")
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a location to search for Airbnb listings. Please specify where you want to stay."
                        ),
                    )
                    return
                
                # Set default limit and extract optional parameters
                limit = 4  # Show 4 listings by default
                
                # Get optional parameters
                checkin = request.parameters.get("checkin")
                checkout = request.parameters.get("checkout")
                adults = request.parameters.get("adults", 2)
                children = request.parameters.get("children")
                infants = request.parameters.get("infants")
                pets = request.parameters.get("pets")
                min_price = request.parameters.get("minPrice")
                max_price = request.parameters.get("maxPrice")
                
                # Build kwargs
                kwargs = {}
                if checkin: kwargs["checkin"] = checkin
                if checkout: kwargs["checkout"] = checkout
                if adults: kwargs["adults"] = adults
                if children: kwargs["children"] = children
                if infants: kwargs["infants"] = infants
                if pets: kwargs["pets"] = pets
                if min_price: kwargs["minPrice"] = min_price
                if max_price: kwargs["maxPrice"] = max_price
                
                ctx.logger.info(f"Calling search_airbnb_listings with location: {location}, limit: {limit}, kwargs: {kwargs}")
                
                # Call the search function
                search_result = await search_airbnb_listings(location, limit, **kwargs)
                
                # Process the search result
                if search_result.get("success", False):
                    formatted_output = search_result.get("formatted_output", "")
                    ctx.logger.info(f"Sending successful search result (length: {len(formatted_output)})")
                    await ctx.send(session_sender, create_text_chat(formatted_output))
                    ctx.logger.info("Response sent successfully")
                else:
                    error_message = search_result.get("message", "An error occurred while searching for listings.")
                    ctx.logger.error(f"Search failed: {error_message}")
                    await ctx.send(session_sender, create_text_chat(f"Sorry, I couldn't find any listings: {error_message}"))
            
            elif request.request_type == "details":
                # Get required listing ID parameter
                listing_id = request.parameters.get("id")
                if not listing_id:
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a listing ID to get details. Please provide the ID of the Airbnb listing you're interested in."
                        )
                    )
                    return
                
                # Extract other parameters
                kwargs = {}
                for param in ["checkin", "checkout"]:
                    if param in request.parameters:
                        kwargs[param] = request.parameters[param]
                
                # Call the details function
                details_result = await get_airbnb_listing_details(listing_id, **kwargs)
                
                # Process the details result
                if details_result.get("success", False):
                    formatted_output = details_result.get("formatted_output", "")
                    await ctx.send(session_sender, create_text_chat(formatted_output))
                else:
                    error_message = details_result.get("message", "An error occurred while getting listing details.")
                    await ctx.send(session_sender, create_text_chat(f"Sorry, I couldn't get the listing details: {error_message}"))
            
            else:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        f"I don't recognize the request type '{request.request_type}'. Please ask for a 'search' or 'details'."
                    )
                )
        except Exception as e:
            ctx.logger.error(f"Error processing request: {e}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    f"I encountered an error while processing your request: {str(e)}"
                )
            )
    except Exception as outer_err:
        ctx.logger.error(f"Outer exception in handle_structured_output_response: {outer_err}")
        import traceback
        ctx.logger.error(f"Error traceback: {traceback.format_exc()}")
        try:
            session_sender = ctx.storage.get(str(ctx.session))
            if session_sender:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        "Sorry, I encountered an unexpected error while processing your request. Please try again later."
                    )
                )
        except Exception as final_err:
            ctx.logger.error(f"Final error recovery failed: {final_err}")

