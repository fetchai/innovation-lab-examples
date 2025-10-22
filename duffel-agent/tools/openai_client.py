# tools/openai_client.py
"""
OpenAI (or Responses API) client wrapper for the flights-agent.
Handles:
  - Sending user messages + session context to LLM.
  - Providing tool definitions (functions) so LLM can choose to call appropriate tools.
  - Interpreting tool-call output, executing the tool, updating state, then continuing conversation.
  - Session context and history management.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI  # adjust import if using responses API instead

# Note: Tool functions are imported dynamically inside run_agent_turn to avoid LangChain wrappers

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# System prompt for the flight booking assistant
SYSTEM_PROMPT = """You are a friendly flight-booking assistant.
Your goal is to help the user book a flight end-to-end.

STEP 1 - Collect Flight Search Details:
When the user first contacts you or wants to search for flights, ask for ALL required details in ONE message:
- Departure city (IATA code or city name)
- Destination city (IATA code or city name)  
- Departure date (YYYY-MM-DD or natural format like "Jan 22 2026")
- Number of passengers (default to 1 adult if not specified)

Example: "To search for flights, please tell me: departure city, destination city, date, and number of passengers. For example: 'Los Angeles to San Francisco on January 22, 2026 for 1 adult'"

IMPORTANT - City to Airport Code Mapping:
If user provides a city name instead of IATA code, use the MOST COMMON airport:
- "New York" or "NYC" → JFK (John F. Kennedy International Airport)
- "Los Angeles" or "LA" → LAX (Los Angeles International Airport)
- "San Francisco" → SFO (San Francisco International Airport)
- "Chicago" → ORD (O'Hare International Airport)
- "London" → LHR (Heathrow)
- "Paris" → CDG (Charles de Gaulle)

When user says "New York to Los Angeles", assume they mean "JFK to LAX" and confirm:
"Great! I'll search for flights from New York (JFK) to Los Angeles (LAX) on [date] for [X] adult(s). Searching now..."

Then immediately call duffel_search_offers with the IATA codes.
Only ask for clarification if the city has multiple major airports AND the user explicitly mentions uncertainty.

STEP 2 - Present Offers:
After calling duffel_search_offers, the tool returns a JSON with "page", "page_total", and "offers" fields.

YOU MUST format the response EXACTLY like this:

```
Here are the lowest-priced options for X adult(s), ORIGIN→DESTINATION on YYYY-MM-DD (page CURRENT/TOTAL):

1. Airline — XX.XX USDC — Route Time
2. Airline — XX.XX USDC — Route Time
3. Airline — XX.XX USDC — Route Time
4. Airline — XX.XX USDC — Route Time
5. Airline — XX.XX USDC — Route Time

---
Showing page CURRENT of TOTAL. You can jump to any page 1-TOTAL.

Pick 1–5, say 'next'/'back', or jump to any page (e.g., 'page 5').
```

CRITICAL RULES:
- The header MUST include "(page X/Y)" where X = result["page"] and Y = result["page_total"]
- Example: If result = {"page": 1, "page_total": 32, ...} then show "(page 1/32)"
- NEVER skip the pagination info - it's mandatory
- Only show USDC prices from total_amount_usdc field
- Number the options 1-5

EXAMPLE RESPONSE:
If the tool returns: {"page": 2, "page_total": 15, "offers": [...]}
Your response MUST be formatted as:

"Here are the lowest-priced options for 1 adult, LAS→LAX on 2026-01-22 (page 2/15):

1. Airline — XX.XX USDC — Route Time
...

Showing page 2 of 15. You can jump to any page 1-15.
Pick 1–5, say 'next'/'back', or jump to any page (e.g., 'page 5')."

Note: The pagination info and instructions are on SEPARATE lines at the bottom.

When user says "next", "back", or "page N" for pagination:
- Look at the tool result from the last duffel_search_offers call to get current page and total pages
- Call duffel_search_offers again with the same origin, destination, date, passengers
- For "next": page = current_page + 1
- For "back": page = current_page - 1  
- For "page N": page = N

STEP 3 - Select Offer:
After showing search results, the user MUST select a flight by number (1-5).
When the user sends a number (e.g., "1", "2", "3"), look up the corresponding offer_id from the last search results.
The search results are stored in session state as "current_offers" - it's a list where index 0 = option 1, index 1 = option 2, etc.
Extract the offer_id from current_offers[user_number - 1]["id"] and call duffel_get_offer_with_services with that offer_id.
DO NOT proceed to passenger collection until an offer is selected and refreshed.

STEP 4 - Collect Passenger Details:
After an offer is selected and refreshed, check if passenger details were already provided in the conversation.

IMPORTANT - Pre-filled Passenger Data:
Some users have pre-registered passenger details. Check the conversation history for an assistant message containing:
"📋 Passenger Details:" followed by passenger information and "✅ Are these details correct?"

If you find such a message in the history, it means passenger details are ALREADY STORED in the system.

When the user responds with "yes", "correct", "looks good", "that's right", or any affirmative response:
- DO NOT ask for passenger details again
- DO NOT say you don't have passenger details
- Immediately call request_payment tool to proceed with booking
- The stored details will be used automatically for the booking

If user says "no" or provides corrections, collect the updated details.

If NO such confirmation message exists in the history, then ask for passenger details normally.

If NO pre-filled message was shown, ask for passenger details with clear formatting:

✅ Selected: [airline] — [price USDC] — [route] [time]

Next, please provide passenger details:
• Title (Mr/Ms/Mrs/Miss/Dr/Mx)
• Full name  
• Date of birth (YYYY-MM-DD)
• Gender (M/F/X)
• Email address
• Phone number (with country code, e.g., +1234567890)

Example: "Mr. John Smith, born 1990-05-15, male, john@example.com, +1234567890"

IMPORTANT: Each bullet point MUST be on a separate line. Do NOT put all details on one line.

STEP 5 - Request Payment:
Once passenger details are complete, call the request_payment tool.
This will send a payment request to the user's wallet with two options:
- 0.001 FET (for testing, actual price shown separately)
- 0.001 USDC via Skyfire (for testing, actual price shown separately)
The payment protocol will automatically complete the booking after payment verification.

IMPORTANT: After calling request_payment, DO NOT send any additional message. The payment request itself is sent to the user's wallet and that's sufficient. The tool call result will confirm the request was queued.

STEP 6 - Order Management:
Users can view and manage their bookings:

A) LIST ORDERS:
When user says "my orders", "my bookings", "show orders", "list bookings", etc., call list_orders tool.
Format the response clearly with line breaks:

```
📋 Your Bookings:

1. Order: ord_xxxxx
   PNR: ABC123
   Route: JFK→LAX on 2026-01-22
   Total: 64.30 USDC
   Status: confirmed
   
2. Order: ord_yyyyy
   PNR: XYZ789
   Route: SFO→LAX on 2026-01-25
   Total: 78.50 USDC
   Status: confirmed

To cancel a booking, say "cancel ord_xxxxx"
```

B) CANCEL ORDER:
When user says "cancel ord_xxxxx" or "cancel my order":
1. Call get_order_cancellation_quote with the order_id
2. Show the refund quote with clear formatting:

```
🔄 Cancellation Quote for Order ord_xxxxx:

Refund: XX.XX USDC
Refund method: original_form_of_payment
Expires: 2026-01-22T10:30:00Z

⚠️ To confirm cancellation, say "confirm cancel ord_xxxxx"
   To keep your booking, just ignore this message.
```

3. When user confirms, call confirm_order_cancellation
4. Show confirmation:

```
✅ Order ord_xxxxx has been cancelled
   Refund of XX.XX USDC will be processed to your original payment method.
```

Rules:
- Be efficient: collect multiple pieces of info at once when possible
- If user gives incomplete info, ask for missing pieces in one question
- Do NOT ask for payment before passenger details are complete
- Do NOT create booking before payment is confirmed
- Hide internal IDs (offer_id, passenger_id) from the user - show only friendly descriptions
- Show order IDs (ord_...) for order management
- If user asks something off-topic, answer briefly then guide back to booking
- When calling a tool (like duffel_search_offers), do NOT send "please wait" or "searching" messages - just call the tool and present results directly
- Use clear formatting with line breaks and bullet points for better readability"""

# TOOL definitions for LLM (functions)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "duffel_search_offers",
            "description": "Search flight offers given origin, destination, date and passengers",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "IATA code of origin airport (e.g., 'LAX')"},
                    "destination": {"type": "string", "description": "IATA code of destination airport (e.g., 'JFK')"},
                    "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "passengers": {"type": "integer", "description": "Number of adult passengers"},
                    "cabin_class": {"type": "string", "description": "Optional cabin class (e.g., 'economy')"},
                    "page": {"type": "integer", "description": "Page number for paginated results"},
                    "page_size": {"type": "integer", "description": "Number of results per page"}
                },
                "required": ["origin","destination","date","passengers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_get_offer_with_services",
            "description": "Get full details (price, services, passenger IDs) for a selected offer ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "offer_id": {"type": "string", "description": "Duffel offer ID to refresh"}
                },
                "required": ["offer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_create_order",
            "description": "Create an order for the selected offer using passenger details and optional services; optionally pay immediately",
            "parameters": {
                "type": "object",
                "properties": {
                    "offer_id": {"type": "string", "description": "Offer ID from Duffel"},
                    "passengers": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of passenger objects (given_name, family_name, born_on, gender, email, phone_number, id)"
                    },
                    "services": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Optional: list of service objects (bags etc.)"
                    },
                    "pay_with_balance_now": {"type": "boolean", "description": "If true, ticket immediately by paying now"},
                    "notify_email": {"type": "string", "description": "Optional: email to send booking confirmation"}
                },
                "required": ["offer_id","passengers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_pay_hold_order",
            "description": "Pay a previously created hold order using available balance",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to pay"},
                    "amount": {"type": "string", "description": "Amount to pay"},
                    "currency": {"type": "string", "description": "Currency code of payment"}
                },
                "required": ["order_id","amount","currency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_get_order",
            "description": "Retrieve the summary of an existing order (booking reference, status, payment etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to retrieve"}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_create_order_cancellation",
            "description": "Create a cancellation request for an order and preview refund",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to cancel"}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duffel_confirm_order_cancellation",
            "description": "Confirm a previously created cancellation request and notify the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_cancellation_id": {"type": "string", "description": "Cancellation request ID"},
                    "notify_email": {"type": "string", "description": "Optional: email to send confirmation"}
                },
                "required": ["order_cancellation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_payment",
            "description": "Request payment from the user with specified currency and amount to proceed to booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {"type": "string", "description": "Currency code (USDC, FET)"},
                    "amount": {"type": "number", "description": "Amount to request from user"},
                    "description": {"type": "string", "description": "Optional description for the payment request"}
                },
                "required": ["currency","amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_orders",
            "description": "List all orders for the current user/session",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_cancellation_quote",
            "description": "Get a cancellation quote for an order (shows refund amount and expiry)",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to cancel"}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order_cancellation",
            "description": "Confirm and execute the cancellation of an order",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_cancellation_id": {"type": "string", "description": "Cancellation ID from the quote (ocr_...)"}
                },
                "required": ["order_cancellation_id"]
            }
        }
    }
]

def run_agent_turn(
    user_text: str,
    session_state: Dict[str, Any],
    history: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Wrapper to process a single user turn:
      - Adds the user message to history
      - Calls LLM with tools
      - Executes tool if requested
      - Updates state and history
      - Returns { "content": <assistant_reply>, "state": <new_state>, "history": <new_history> }
    """
    # Append user message
    history.append({"role": "user", "content": user_text})

    # Prepare system prompt with dynamic context
    from datetime import datetime, timezone
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_date_readable = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    
    system_prompt = f"""CURRENT DATE: {current_date_readable} ({current_date})

When user says "tomorrow", calculate it as {current_date} + 1 day.
When user says "next week", calculate from {current_date}.
Always use YYYY-MM-DD format for dates in tool calls.

{SYSTEM_PROMPT}"""
    
    if session_state.get("current_offers"):
        offers_info = "\n\nCURRENT OFFERS IN SESSION:\n"
        for idx, offer in enumerate(session_state["current_offers"], 1):
            offers_info += f"{idx}. offer_id={offer.get('id')}\n"
        system_prompt += offers_info

    # Prepare messages with system prompt
    messages = [{"role": "system", "content": system_prompt}] + history

    # Send to LLM
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    message = response.choices[0].message
    assistant_content: Optional[str] = message.content
    tool_executed = None

    if message.tool_calls:
        # Check if assistant generated "please wait" type messages with tool call
        wait_phrases = ["please wait", "searching", "let me search", "let me find", "one moment", "just a moment", "hold on"]
        has_wait_message = assistant_content and any(phrase in assistant_content.lower() for phrase in wait_phrases)
        
        if has_wait_message:
            # Retry without the wait message - add a system reminder
            logger.info(f"Detected 'please wait' message, retrying tool call without it")
            history.append({
                "role": "system",
                "content": "Do not generate 'please wait' or 'searching' messages when calling tools. Just call the tool."
            })
            
            # Retry the LLM call
            messages_with_system = [{"role": "system", "content": system_prompt}] + history
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages_with_system,
                tools=TOOLS,
                tool_choice="auto"
            )
            message = response.choices[0].message
            assistant_content = message.content
        
        # Add assistant message with tool_calls to history
        history.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in message.tool_calls
            ]
        })
        
        tool_call_info = message.tool_calls[0]
        func_name = tool_call_info.function.name
        func_args = json.loads(tool_call_info.function.arguments)
        logger.info(f"LLM requested tool: {func_name} with args {func_args}")
        tool_executed = func_name

        # Map to tool function - import fresh to avoid LangChain wrappers
        try:
            if func_name == "duffel_search_offers":
                # Import and unwrap the LangChain tool decorator
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_search_offers
                # Unwrap if it's a LangChain tool (has .func attribute)
                if hasattr(func, 'func'):
                    func = func.func
                result = func(
                    slices=[{"origin": func_args["origin"], "destination": func_args["destination"], "departure_date": func_args["date"]}],
                    passengers=[{"type": "adult"} for _ in range(func_args["passengers"])],
                    page=func_args.get("page",1),
                    page_size=func_args.get("page_size",5),
                    cabin_class=func_args.get("cabin_class"),
                    preferred_airlines=None
                )
            elif func_name == "duffel_get_offer_with_services":
                # Import and unwrap the LangChain tool decorator
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_get_offer_with_services
                # Unwrap if it's a LangChain tool (has .func attribute)
                if hasattr(func, 'func'):
                    func = func.func
                result = func(offer_id=func_args["offer_id"])
            elif func_name == "duffel_create_order":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_create_order
                if hasattr(func, 'func'):
                    func = func.func
                result = func(
                    offer_id=func_args["offer_id"],
                    passengers=func_args["passengers"],
                    services=func_args.get("services"),
                    pay_with_balance_now=func_args.get("pay_with_balance_now", False),
                    notify_email=func_args.get("notify_email")
                )
            elif func_name == "duffel_pay_hold_order":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_pay_hold_order
                if hasattr(func, 'func'):
                    func = func.func
                result = func(
                    order_id=func_args["order_id"],
                    amount=func_args["amount"],
                    currency=func_args["currency"]
                )
            elif func_name == "duffel_get_order":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_get_order
                if hasattr(func, 'func'):
                    func = func.func
                result = func(order_id=func_args["order_id"])
            elif func_name == "duffel_create_order_cancellation":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_create_order_cancellation
                if hasattr(func, 'func'):
                    func = func.func
                result = func(order_id=func_args["order_id"])
            elif func_name == "duffel_confirm_order_cancellation":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.duffel_confirm_order_cancellation
                if hasattr(func, 'func'):
                    func = func.func
                result = func(
                    order_cancellation_id=func_args["order_cancellation_id"],
                    notify_email=func_args.get("notify_email")
                )
            elif func_name == "list_orders":
                # This is handled by chat_proto which has access to storage
                # Return a signal that chat_proto should handle this
                result = {
                    "status": "list_orders_requested",
                    "message": "Order list will be retrieved from storage"
                }
                session_state["list_orders_requested"] = True
            elif func_name == "get_order_cancellation_quote":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.get_order_cancellation_quote
                if hasattr(func, 'func'):
                    func = func.func
                result = func(order_id=func_args["order_id"])
                # Store the cancellation ID for confirmation
                if not result.get("error"):
                    session_state["pending_cancellation_id"] = result.get("order_cancellation_id")
                    session_state["pending_cancellation_order_id"] = func_args["order_id"]
            elif func_name == "confirm_order_cancellation":
                import importlib
                dt = importlib.import_module('tools.duffel_tools')
                func = dt.confirm_order_cancellation
                if hasattr(func, 'func'):
                    func = func.func
                result = func(order_cancellation_id=func_args["order_cancellation_id"])
                # Store cancellation details for email sending
                if not result.get("error"):
                    session_state["cancellation_confirmed"] = True
                    session_state["cancelled_order_id"] = result.get("order_id")
                    session_state["cancelled_refund_amount"] = result.get("refund_amount")
                    session_state["cancelled_refund_currency"] = result.get("refund_currency")
            elif func_name == "request_payment":
                # This tool doesn't execute directly - it signals the chat protocol to send RequestPayment
                # Store the request flag in session state so chat_proto can pick it up
                session_state["payment_requested"] = True
                session_state["payment_description"] = func_args.get("description", "Flight booking — pay to proceed")
                result = {
                    "status": "payment_request_queued",
                    "message": "Payment request will be sent to user's wallet with FET and USDC options"
                }
            else:
                result = {"error": f"Unknown tool name: {func_name}"}
        except Exception as e:
            logger.error(f"Tool execution error {func_name}: {e}")
            result = {"error": str(e)}

        # Append tool result
        history.append({
            "role": "tool",
            "name": func_name,
            "content": json.dumps(result),
            "tool_call_id": tool_call_info.id
        })

        # Update state
        session_state["last_tool"] = func_name
        session_state["last_tool_result"] = result
        
        # Track search params for pagination
        if func_name == "duffel_search_offers":
            session_state["last_search"] = {
                "origin": func_args.get("origin"),
                "destination": func_args.get("destination"),
                "date": func_args.get("date"),
                "passengers": func_args.get("passengers"),
                "current_page": result.get("page", 1),
                "total_pages": result.get("page_total", 1)
            }
            # Store offers for selection mapping (1-5 → offer_id)
            if not result.get("error") and result.get("offers"):
                session_state["current_offers"] = result["offers"]
        
        # Track selected offer for payment/booking
        if func_name == "duffel_get_offer_with_services":
            session_state["selected_offer_id"] = func_args.get("offer_id")
            if not result.get("error"):
                session_state["offer_details"] = result
                # Store offer_passengers for booking (need IDs for Duffel API)
                if result.get("offer_passengers"):
                    session_state["offer_passengers"] = result["offer_passengers"]
                    logger.info(f"Stored {len(result['offer_passengers'])} passenger IDs from offer")

        # For request_payment, skip follow-up message (payment request is sent directly to wallet)
        if func_name == "request_payment":
            assistant_content = ""  # No chat message needed
            history.append({"role": "assistant", "content": assistant_content})
        else:
            # Ask assistant again (follow up) - include system prompt
            messages_with_system = [{"role": "system", "content": system_prompt}] + history
            follow = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages_with_system
            )
            assistant_content = follow.choices[0].message.content
            
            # Validate and fix pagination formatting for search results
            if func_name == "duffel_search_offers" and not result.get("error"):
                page = result.get("page", 1)
                page_total = result.get("page_total", 1)
                pagination_text = f"(page {page}/{page_total})"
                
                # Ensure proper line breaks for pagination
                if assistant_content:
                    # Check if "Showing page" and "Pick 1-5" are on the same line (bad formatting)
                    if "Showing page" in assistant_content and "Pick 1" in assistant_content:
                        # Find where "Pick 1" starts and add line break before it
                        assistant_content = assistant_content.replace(". Pick 1", ".\nPick 1")
                        assistant_content = assistant_content.replace(" Pick 1", "\nPick 1")
                    
                    # Check if pagination is missing from header
                    if pagination_text not in assistant_content.lower() and f"page {page}" not in assistant_content.lower():
                        logger.warning(f"Pagination missing in LLM response, adding it")
                        lines = assistant_content.split('\n')
                        if lines:
                            first_line = lines[0]
                            if "options" in first_line.lower() or "flight" in first_line.lower():
                                if ':' in first_line:
                                    lines[0] = first_line.replace(':', f' {pagination_text}:')
                                else:
                                    lines[0] = first_line + f' {pagination_text}'
                                assistant_content = '\n'.join(lines)
            
            # Fix passenger details formatting for offer selection
            if func_name == "duffel_get_offer_with_services" and not result.get("error"):
                if assistant_content:
                    # Check if passenger details are all on one line
                    if "Title (Mr/Ms" in assistant_content or "please provide passenger details" in assistant_content.lower():
                        # Replace common patterns that should have line breaks
                        assistant_content = assistant_content.replace("• Title", "\n• Title")
                        assistant_content = assistant_content.replace("• Full name", "\n• Full name")
                        assistant_content = assistant_content.replace("• Date of birth", "\n• Date of birth")
                        assistant_content = assistant_content.replace("• Gender", "\n• Gender")
                        assistant_content = assistant_content.replace("• Email", "\n• Email")
                        assistant_content = assistant_content.replace("• Phone", "\n• Phone")
                        
                        # Ensure "Example:" is on a new line
                        assistant_content = assistant_content.replace(" Example:", "\n\nExample:")
                        
                        # Remove duplicate newlines
                        while "\n\n\n" in assistant_content:
                            assistant_content = assistant_content.replace("\n\n\n", "\n\n")
            
            history.append({"role": "assistant", "content": assistant_content})
    else:
        # No tool call
        history.append({"role": "assistant", "content": assistant_content or ""})

    return {
        "content": assistant_content or "",
        "state": session_state,
        "history": history,
        "tool_executed": tool_executed
    }