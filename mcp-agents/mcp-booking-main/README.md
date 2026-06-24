# Restaurant Booking MCP Server

An AI-powered Model Context Protocol (MCP) server for restaurant discovery and booking. This server integrates with Google Maps Places API to find restaurants based on location, cuisine preferences, mood, and event type, then provides intelligent recommendations and booking assistance.

## 🎯 Key Features

- **Smart Restaurant Search**: Find restaurants within 20km radius with advanced filtering
- **Default Taiwan Location**: Automatically searches around Taiwan (24.1501164, 120.6692299) when no coordinates specified
- **AI-Powered Recommendations**: Get top 3 restaurant suggestions with detailed reasoning
- **Google Maps Integration**: Real restaurant data including ratings, reviews, and photos
- **Event-Specific Matching**: Optimized for dating, family gatherings, business meetings, and celebrations
- **Mood-Based Filtering**: Find restaurants matching romantic, casual, upscale, fun, or quiet atmospheres
- **Booking Assistance**: Get reservation instructions and mock booking capabilities

## Features

- 🔍 **Smart Restaurant Search**: Find restaurants within 20km radius based on location, cuisine types, mood, and event type
- 📍 **Google Maps Integration**: Real restaurant data with ratings, reviews, photos, and contact information
- 📅 **Booking Assistance**: Check availability and get reservation instructions
- 🎯 **Event-Specific Matching**: Optimized recommendations for dating, family gatherings, business meetings, etc.
- 🎭 **Mood-Based Filtering**: Find restaurants that match your desired atmosphere (romantic, casual, upscale, etc.)

## Prerequisites

- Node.js 18+
- Google Maps API Key with Places API enabled
- TypeScript knowledge for customization

## Installation

1. **Clone or download this project**

   ```bash
   git clone <repository-url>
   cd mcp-restaurant-booking
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Google Maps API key:

   ```
   GOOGLE_MAPS_API_KEY=your_actual_api_key_here
   ```

4. **Build the project**
   ```bash
   npm run build
   ```

## Getting Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the following APIs:
   - Places API
   - Maps JavaScript API
   - Geolocation API
   - Places API (New)
   - Geocoding API
4. Create credentials (API Key)
5. Restrict the API key to the enabled APIs for security

## Usage

### Running the Server

**Development mode:**

```bash
npm run dev
```

**Production mode:**

```bash
npm start
```

## Running in Docker

To run the MCP Restaurant Booking server in Docker:

```bash
# Build the Docker image
docker build -t mcp/booking .

# Run the container on the same network as Redis
docker run --rm -i mcp/booking
```

### Available Tools

The MCP server provides the following tools:

#### 1. `search_restaurants`

Find restaurants based on location, cuisine, mood, and event type.

**Parameters:**

- `latitude` (number, optional): Search latitude (default: 24.1501164 - Taiwan)
- `longitude` (number, optional): Search longitude (default: 120.6692299 - Taiwan)
- `placeName` (string, optional): Place name to search near (e.g., "New York", "Tokyo", "London"). Alternative to providing latitude/longitude coordinates.
- `cuisineTypes` (string[]): Array of cuisine preferences
- `mood` (string): Desired atmosphere
- `event` (string): Type of occasion
- `radius` (number, optional): Search radius in meters (default: 20000)
- `priceLevel` (number, optional): Price preference (1-4)

**Example with default Taiwan location:**

```json
{
  "cuisineTypes": ["Chinese", "Taiwanese"],
  "mood": "casual",
  "event": "family gathering",
  "priceLevel": 2
}
```

**Example with explicit coordinates (Taipei):**

```json
{
  "latitude": 25.033,
  "longitude": 121.5654,
  "cuisineTypes": ["Italian", "Mediterranean"],
  "mood": "romantic",
  "event": "dating",
  "radius": 15000,
  "priceLevel": 3
}
```

**Example with place name (New York):**

```json
{
  "placeName": "New York, NY",
  "cuisineTypes": ["Italian", "American"],
  "mood": "upscale",
  "event": "business meeting",
  "radius": 10000,
  "priceLevel": 3
}
```

**Example with keyword search for specific food types:**

```json
{
  "keyword": "hotpot",
  "mood": "casual",
  "event": "family gathering",
  "radius": 10000
}
```

#### 2. `get_restaurant_details`

Get detailed information about a specific restaurant.

**Parameters:**

- `placeId` (string): Google Places ID of the restaurant

#### 3. `get_booking_instructions`

Get instructions on how to make a reservation.

**Parameters:**

- `placeId` (string): Google Places ID of the restaurant

#### 4. `check_availability`

Check availability for a reservation (mock implementation).

**Parameters:**

- `placeId` (string): Google Places ID
- `dateTime` (string): Preferred date/time in ISO format
- `partySize` (number): Number of people

#### 5. `make_reservation`

Attempt to make a reservation (mock implementation).

**Parameters:**

- `placeId` (string): Google Places ID
- `partySize` (number): Number of people
- `preferredDateTime` (string): ISO format date/time
- `contactName` (string): Name for reservation
- `contactPhone` (string): Phone number
- `contactEmail` (string, optional): Email address
- `specialRequests` (string, optional): Special requests

## How It Works

### 1. Restaurant Discovery

- Uses Google Places Nearby Search API to find restaurants within specified radius
- Filters by cuisine types using keyword matching
- Retrieves detailed information for each restaurant

### 2. AI Recommendation Engine

The recommendation system scores restaurants based on:

- **Rating & Reviews (40% weight)**: Higher ratings and more reviews = better score
- **Review Count (20% weight)**: More reviews indicate reliability
- **Cuisine Match (20% weight)**: How well restaurant cuisine matches preferences
- **Event Suitability (10% weight)**: Appropriateness for the specified event type
- **Mood Match (10% weight)**: Atmosphere alignment with desired mood

### 3. Event-Specific Scoring

Different events have different criteria:

- **Dating**: Prefers mid-to-high-end, romantic cuisines, avoids fast food
- **Family Gathering**: Prefers family-friendly, budget-to-mid-range options
- **Business Meeting**: Prefers quiet, professional, upscale environments
- **Casual Dining**: Flexible criteria, budget-friendly options
- **Celebration**: Prefers high-end, special occasion venues

### 4. Mood Matching

Analyzes restaurant names, reviews, and characteristics for mood keywords:

- **Romantic**: intimate, cozy, candlelit, wine
- **Casual**: relaxed, friendly, laid-back
- **Upscale**: elegant, sophisticated, fine dining
- **Fun**: lively, energetic, vibrant
- **Quiet**: peaceful, serene, calm

## Development

### Project Structure

```
src/
├── types/           # TypeScript type definitions
├── services/        # Core business logic
│   ├── googleMapsService.ts      # Google Maps API integration
│   ├── restaurantRecommendationService.ts  # AI recommendation engine
│   └── bookingService.ts         # Booking logic (mock)
└── index.ts         # MCP server implementation
```

### Scripts

- `npm run build`: Compile TypeScript
- `npm run dev`: Run in development mode with hot reload
- `npm start`: Run compiled version
- `npm run lint`: Run ESLint
- `npm run lint:fix`: Fix ESLint issues

### Customization

#### Adding New Cuisine Types

Edit the `cuisineMap` in `src/services/googleMapsService.ts`:

```typescript
const cuisineMap: { [key: string]: string } = {
  new_cuisine_type: "Display Name",
  // ... existing mappings
};
```

#### Modifying Recommendation Logic

Update scoring algorithms in `src/services/restaurantRecommendationService.ts`:

- `calculateRestaurantScore()`: Overall scoring logic
- `calculateEventSuitability()`: Event-specific criteria
- `calculateMoodMatch()`: Mood matching logic

#### Adding New Event Types

1. Update the `event` enum in `src/types/index.ts`
2. Add event criteria in `calculateEventSuitability()` method

## Limitations

- **Booking**: Currently uses mock implementation. Real booking requires integration with restaurant-specific systems or third-party services like OpenTable
- **API Quotas**: Google Places API has usage limits and costs
- **Real-time Data**: Restaurant hours and availability may not be real-time
- **Geographic Coverage**: Limited to areas covered by Google Places API

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:

1. Check the Google Maps API documentation
2. Verify your API key has proper permissions
3. Check API quotas and billing
4. Review server logs for error details

## Future Enhancements

- [ ] Real booking system integration (OpenTable, Resy, etc.)
- [ ] User preference learning
- [x] Multi-language support
- [ ] Advanced filtering (dietary restrictions, accessibility)
- [ ] Integration with calendar systems
- [x] Price comparison features
- [ ] Social features (reviews, sharing)

## Additional Browser Control

Using Browser MCP

- https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc
- https://docs.browsermcp.io/setup-server#cursor

## Sample

- Prompt: - While searching restaurants, please perform as professional personal assistant to evaluate the condition I provided, do not ask too many questions for me to choose, pick the best suitable selection for me, checking the reservation options and guide how to do the reservation. also list down the Signature Dishes from that restaurant and Approximately pricing per person. When booking info has booking url using external url, use the mcp browse tool to work and find reservation steps.
- can you help me book a restaurant nearby hongkong 太平洋廣場, I want to have a date with my wife within a fine-dining at evening 6pm. cost is not a concern and needs to be romatic
