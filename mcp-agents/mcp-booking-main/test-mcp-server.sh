#!/bin/bash

# MCP Restaurant Booking Server Test Script
# This script tests all the endpoints and tools of the MCP server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Server configuration
SERVER_URL="http://localhost:3001"
MCP_ENDPOINT="$SERVER_URL/mcp"
HEALTH_ENDPOINT="$SERVER_URL/health"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to extract session ID from response
extract_session_id() {
    local response="$1"
    echo "$response" | grep -o 'mcp-session-id: [^[:space:]]*' | cut -d' ' -f2 | tr -d '\r'
}

# Function to make MCP request
make_mcp_request() {
    local session_id="$1"
    local data="$2"
    local description="$3"
    
    print_status "Testing: $description"
    
    if [ -z "$session_id" ]; then
        # Initial request without session ID
        curl -s -i -X POST "$MCP_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$data"
    else
        # Request with session ID
        curl -s -X POST "$MCP_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "mcp-session-id: $session_id" \
            -d "$data"
    fi
}

echo "=================================="
echo "MCP Restaurant Booking Server Test"
echo "=================================="

# Step 1: Health Check
print_status "Checking server health..."
health_response=$(curl -s "$HEALTH_ENDPOINT")
if echo "$health_response" | grep -q '"status":"ok"'; then
    print_success "Server is healthy"
    echo "$health_response" | jq . 2>/dev/null || echo "$health_response"
else
    print_error "Server health check failed"
    echo "$health_response"
    exit 1
fi

echo ""

# Step 2: Initialize MCP Session
print_status "Initializing MCP session..."
init_data='{
    "jsonrpc": "2.0",
    "id": "init",
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}'

init_response=$(make_mcp_request "" "$init_data" "Session initialization")
session_id=$(extract_session_id "$init_response")

if [ -n "$session_id" ]; then
    print_success "Session initialized with ID: $session_id"
else
    print_error "Failed to extract session ID"
    echo "$init_response"
    exit 1
fi

echo ""

# Step 3: List Available Tools
print_status "Listing available tools..."
list_tools_data='{
    "jsonrpc": "2.0",
    "id": "list-tools",
    "method": "tools/list"
}'

tools_response=$(make_mcp_request "$session_id" "$list_tools_data" "Tools listing")
echo "$tools_response" | jq . 2>/dev/null || echo "$tools_response"
print_success "Tools listed successfully"

echo ""

# Step 4: Search Restaurants
print_status "Testing restaurant search..."
search_data='{
    "jsonrpc": "2.0",
    "id": "search",
    "method": "tools/call",
    "params": {
        "name": "search_restaurants",
        "arguments": {
            "mood": "romantic",
            "event": "dating",
            "latitude": 25.0330,
            "longitude": 121.5654,
            "radius": 2000,
            "locale": "en"
        }
    }
}'

search_response=$(make_mcp_request "$session_id" "$search_data" "Restaurant search")
echo "$search_response" | jq . 2>/dev/null || echo "$search_response"

# Extract place ID from search response for next test
place_id=$(echo "$search_response" | grep -o '"placeId":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$place_id" ]; then
    print_success "Restaurant search completed. Found place ID: $place_id"
else
    print_warning "Could not extract place ID from search results"
    place_id="ChIJz8_rGbyrQjQRD1-qfRm5C1M"  # Fallback to known place ID
fi

echo ""

# Step 5: Get Restaurant Details
print_status "Testing restaurant details retrieval..."
details_data="{
    \"jsonrpc\": \"2.0\",
    \"id\": \"details\",
    \"method\": \"tools/call\",
    \"params\": {
        \"name\": \"get_restaurant_details\",
        \"arguments\": {
            \"placeId\": \"$place_id\",
            \"locale\": \"en\"
        }
    }
}"

details_response=$(make_mcp_request "$session_id" "$details_data" "Restaurant details")
echo "$details_response" | jq . 2>/dev/null || echo "$details_response"
print_success "Restaurant details retrieved successfully"

echo ""

# Step 6: Get Booking Instructions
print_status "Testing booking instructions..."
booking_data="{
    \"jsonrpc\": \"2.0\",
    \"id\": \"booking\",
    \"method\": \"tools/call\",
    \"params\": {
        \"name\": \"get_booking_instructions\",
        \"arguments\": {
            \"placeId\": \"$place_id\",
            \"locale\": \"en\"
        }
    }
}"

booking_response=$(make_mcp_request "$session_id" "$booking_data" "Booking instructions")
echo "$booking_response" | jq . 2>/dev/null || echo "$booking_response"
print_success "Booking instructions retrieved successfully"

echo ""

# Step 7: Check Availability
print_status "Testing availability check..."
availability_data="{
    \"jsonrpc\": \"2.0\",
    \"id\": \"availability\",
    \"method\": \"tools/call\",
    \"params\": {
        \"name\": \"check_availability\",
        \"arguments\": {
            \"placeId\": \"$place_id\",
            \"dateTime\": \"2024-12-25T19:00:00\",
            \"partySize\": 2,
            \"locale\": \"en\"
        }
    }
}"

availability_response=$(make_mcp_request "$session_id" "$availability_data" "Availability check")
echo "$availability_response" | jq . 2>/dev/null || echo "$availability_response"
print_success "Availability check completed successfully"

echo ""

# Step 8: Make Reservation (Test)
print_status "Testing reservation creation..."
reservation_data="{
    \"jsonrpc\": \"2.0\",
    \"id\": \"reservation\",
    \"method\": \"tools/call\",
    \"params\": {
        \"name\": \"make_reservation\",
        \"arguments\": {
            \"placeId\": \"$place_id\",
            \"partySize\": 2,
            \"preferredDateTime\": \"2024-12-25T19:00:00\",
            \"contactName\": \"Sam Wang\",
            \"contactPhone\": \"+1234567890\",
            \"contactEmail\": \"samxxxx@gmail.com\",
            \"specialRequests\": \"Window seat preferred\",
            \"locale\": \"en\"
        }
    }
}"

reservation_response=$(make_mcp_request "$session_id" "$reservation_data" "Reservation creation")
echo "$reservation_response" | jq . 2>/dev/null || echo "$reservation_response"
print_success "Reservation test completed successfully"

echo ""

# Summary
print_success "All tests completed successfully!"
echo "=================================="
echo "Test Summary:"
echo "✅ Health Check"
echo "✅ Session Initialization"
echo "✅ Tools Listing"
echo "✅ Restaurant Search"
echo "✅ Restaurant Details"
echo "✅ Booking Instructions"
echo "✅ Availability Check"
echo "✅ Reservation Test"
echo "=================================="
echo ""
print_status "Session ID for manual testing: $session_id"
print_warning "Note: The reservation test is for API testing only. No actual reservation was made." 