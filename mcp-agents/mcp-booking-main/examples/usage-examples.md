# Usage Examples

This document provides practical examples of how to use the Restaurant Booking MCP Server.

## Example 1: Romantic Date Night

Find restaurants for a romantic dinner date in San Francisco:

```json
{
  "tool": "search_restaurants",
  "parameters": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "cuisineTypes": ["Italian", "French", "Mediterranean"],
    "mood": "romantic",
    "event": "dating",
    "priceLevel": 3,
    "radius": 15000
  }
}
```

**Expected Response:**

- Top 3 restaurants with romantic atmosphere
- High ratings and upscale ambiance
- Italian/French/Mediterranean cuisine focus
- Mid-to-high price range

## Example 2: Family Gathering

Find family-friendly restaurants for a weekend gathering:

```json
{
  "tool": "search_restaurants",
  "parameters": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "cuisineTypes": ["American", "Italian", "Mexican"],
    "mood": "casual",
    "event": "family gathering",
    "priceLevel": 2,
    "radius": 20000
  }
}
```

**Expected Response:**

- Family-friendly restaurants
- Casual atmosphere
- Budget-to-moderate pricing
- Spacious seating arrangements

## Example 3: Business Meeting

Find upscale restaurants suitable for business discussions:

```json
{
  "tool": "search_restaurants",
  "parameters": {
    "latitude": 34.0522,
    "longitude": -118.2437,
    "cuisineTypes": ["American", "Steakhouse"],
    "mood": "upscale",
    "event": "business meeting",
    "priceLevel": 4,
    "radius": 10000
  }
}
```

**Expected Response:**

- Professional, quiet atmosphere
- High-end restaurants
- Suitable for business conversations
- Premium pricing

## Example 4: Get Restaurant Details

Get detailed information about a specific restaurant:

```json
{
  "tool": "get_restaurant_details",
  "parameters": {
    "placeId": "ChIJN1t_tDeuEmsRUsoyG83frY4"
  }
}
```

**Response includes:**

- Complete restaurant information
- Reviews and ratings
- Photos
- Opening hours
- Contact information

## Example 5: Check Availability

Check if a restaurant has availability for your preferred time:

```json
{
  "tool": "check_availability",
  "parameters": {
    "placeId": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "dateTime": "2024-02-14T19:00:00",
    "partySize": 2
  }
}
```

**Response includes:**

- Availability status
- Alternative time suggestions if unavailable
- Booking recommendations

## Example 6: Make a Reservation

Attempt to make a reservation (mock implementation):

```json
{
  "tool": "make_reservation",
  "parameters": {
    "placeId": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "partySize": 4,
    "preferredDateTime": "2024-02-15T18:30:00",
    "contactName": "John Smith",
    "contactPhone": "+1-555-123-4567",
    "contactEmail": "john.smith@email.com",
    "specialRequests": "Window table preferred, celebrating anniversary"
  }
}
```

**Response includes:**

- Booking confirmation or failure
- Reservation details
- Confirmation number
- Alternative options if unsuccessful

## Example 7: Get Booking Instructions

Get instructions on how to make a reservation at a restaurant:

```json
{
  "tool": "get_booking_instructions",
  "parameters": {
    "placeId": "ChIJN1t_tDeuEmsRUsoyG83frY4"
  }
}
```

**Response includes:**

- Phone number for reservations
- Website booking links
- Opening hours
- Special booking notes

## Example 8: Search by Place Name

Find restaurants using a place name instead of coordinates:

```json
{
  "tool": "search_restaurants",
  "parameters": {
    "placeName": "Tokyo, Japan",
    "cuisineTypes": ["Japanese", "Sushi"],
    "mood": "upscale",
    "event": "business meeting",
    "priceLevel": 3,
    "radius": 5000
  }
}
```

**Expected Response:**

- Restaurants near Tokyo city center
- High-quality Japanese cuisine
- Professional atmosphere suitable for business
- Mid-to-high price range

**Alternative place name examples:**

- `"New York, NY"` - Search in New York City
- `"London, UK"` - Search in London
- `"Paris, France"` - Search in Paris
- `"Sydney, Australia"` - Search in Sydney
- `"Times Square, New York"` - Search near specific landmark

## Common Use Cases

### 1. Date Night Planning

```bash
# Step 1: Search for romantic restaurants
search_restaurants -> romantic Italian restaurants

# Step 2: Get details for top choice
get_restaurant_details -> full restaurant info

# Step 3: Check availability
check_availability -> confirm time slot

# Step 4: Get booking instructions
get_booking_instructions -> how to reserve
```

### 2. Group Dining

```bash
# Step 1: Search for family-friendly options
search_restaurants -> casual, large party suitable

# Step 2: Compare multiple options
get_restaurant_details -> for each top choice

# Step 3: Check availability for large group
check_availability -> party size 8+

# Step 4: Make reservation
make_reservation -> book the table
```

### 3. Business Entertainment

```bash
# Step 1: Find upscale, quiet restaurants
search_restaurants -> business meeting suitable

# Step 2: Verify atmosphere and amenities
get_restaurant_details -> check reviews for business suitability

# Step 3: Book appropriate time
check_availability -> lunch or dinner slot

# Step 4: Reserve with special requests
make_reservation -> quiet table, business atmosphere
```

## Tips for Best Results

1. **Be Specific with Cuisine Types**: Use specific cuisines like "Italian", "Japanese" rather than generic terms
2. **Match Mood to Event**: Align mood (romantic, casual, upscale) with event type for better recommendations
3. **Consider Price Level**: Set appropriate price level for your budget and occasion
4. **Use Reasonable Radius**: 10-20km radius typically provides good options without being too broad
5. **Check Multiple Options**: Get details for all top 3 recommendations before deciding
6. **Plan Ahead**: Check availability well in advance for popular restaurants and peak times

## Error Handling

The server handles various error conditions gracefully:

- **Invalid API Key**: Returns error message about authentication
- **No Results Found**: Suggests expanding search criteria
- **Invalid Location**: Prompts for valid latitude/longitude
- **Restaurant Not Found**: Returns appropriate error for invalid place IDs
- **Booking Failures**: Provides alternative suggestions and manual booking instructions
