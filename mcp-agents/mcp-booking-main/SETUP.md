# Quick Setup Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies

```bash
npm install
```

### 2. Get Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable these APIs:
   - Places API
   - Places API (New)
   - Geocoding API
   - Geolocation API
   - Maps Javascript API
4. Create an API Key
5. Restrict the key to the enabled APIs

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```
GOOGLE_MAPS_API_KEY=your_actual_api_key_here
```

### 4. Build and Run

```bash
npm run build
npm start
```

## 🧪 Test the Server

Run the test script:

```bash
node test-server.js
```

## 🔧 Available Tools

1. **search_restaurants** - Find restaurants with AI recommendations
2. **get_restaurant_details** - Get detailed restaurant information
3. **get_booking_instructions** - Get reservation instructions
4. **check_availability** - Check table availability (mock)
5. **make_reservation** - Make a reservation (mock)

## 📖 Usage Examples

### Find Restaurants in Taiwan (Default Location)

```json
{
  "cuisineTypes": ["Chinese", "Taiwanese"],
  "mood": "casual",
  "event": "family gathering",
  "priceLevel": 2
}
```

### Find Romantic Restaurants in Taipei

```json
{
  "latitude": 25.033,
  "longitude": 121.5654,
  "cuisineTypes": ["Italian", "French"],
  "mood": "romantic",
  "event": "dating",
  "priceLevel": 3
}
```

### Family-Friendly Options (Custom Location)

```json
{
  "latitude": 40.7128,
  "longitude": -74.006,
  "cuisineTypes": ["American", "Italian"],
  "mood": "casual",
  "event": "family gathering",
  "priceLevel": 2
}
```

## 🎯 Key Features

- **Smart Search**: 20km radius with cuisine, mood, and event filtering
- **AI Recommendations**: Top 3 suggestions with detailed reasoning
- **Real Data**: Google Maps integration with ratings, reviews, photos
- **Event Matching**: Optimized for dating, family, business, celebrations
- **Mood Filtering**: Romantic, casual, upscale, fun, quiet atmospheres

## 🔍 How It Works

1. **Search**: Uses Google Places API to find restaurants
2. **Analyze**: AI scores based on rating, cuisine match, event suitability, mood
3. **Rank**: Returns top 3 with detailed reasoning
4. **Book**: Provides reservation instructions and mock booking

## 💡 Tips

- Use specific cuisine types for better results
- Match mood to event type (romantic + dating, casual + family)
- Set appropriate price level for your budget
- Check multiple options before deciding

## 🚨 Troubleshooting

**"API Key Required" Error:**

- Make sure `.env` file exists with valid `GOOGLE_MAPS_API_KEY`
- Verify API key has Places API enabled
- Check API key restrictions

**No Results Found:**

- Increase search radius
- Try broader cuisine types
- Check if location coordinates are valid

**Build Errors:**

- Run `npm install` to ensure all dependencies are installed
- Check Node.js version (requires 18+)

## 📚 Next Steps

1. See `examples/usage-examples.md` for detailed examples
2. Read `README.md` for complete documentation
3. Customize recommendation logic in `src/services/`
4. Add real booking integration for production use
