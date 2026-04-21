export interface Location {
  latitude: number;
  longitude: number;
}

export interface RestaurantSearchParams {
  location?: Location; // Made optional when placeName is provided
  placeName?: string; // 🆕 NEW: Alternative to location - place name to geocode
  cuisineTypes: string[];
  mood: string;
  event: string;
  radius?: number; // in meters, default 20km
  priceLevel?: 1 | 2 | 3 | 4; // 1 = inexpensive, 4 = very expensive
  keyword?: string; // 🆕 NEW: Search for specific food types like "hotpot", "sushi", "pizza", etc.
  locale?: string; // 🆕 NEW: Locale for search results (e.g., "en", "zh-TW", "ja", "ko")
  strictCuisineFiltering?: boolean; // 🆕 NEW: If true, exclude restaurants that don't match cuisine criteria
}

export interface Restaurant {
  placeId: string;
  name: string;
  address: string;
  location: Location;
  rating: number;
  userRatingsTotal: number;
  priceLevel?: number;
  cuisineTypes: string[];
  photos?: string[];
  phoneNumber?: string;
  website?: string;
  googleMapsUrl?: string;
  /** Yelp Fusion match (optional; set when YELP_API_KEY is configured) */
  yelpBusinessId?: string;
  yelpAlias?: string;
  yelpUrl?: string;
  /** Yelp menu page for this business (alias-based URL) */
  yelpMenuUrl?: string;
  distance?: number; // 🆕 NEW: Distance from search location in meters
  bookingInfo?: {
    reservable?: boolean;
    bookingUrl?: string;
    bookingPlatform?:
      | 'opentable'
      | 'resy'
      | 'yelp'
      | 'restaurant_website'
      | 'google_reserve'
      | 'other';
    supportsOnlineBooking?: boolean;
    requiresPhone?: boolean;
  };
  reservable?: boolean;
  curbsidePickup?: boolean;
  delivery?: boolean;
  dineIn?: boolean;
  takeout?: boolean;
  servesBreakfast?: boolean;
  servesLunch?: boolean;
  servesDinner?: boolean;
  servesBrunch?: boolean;
  servesBeer?: boolean;
  servesWine?: boolean;
  servesVegetarianFood?: boolean;
  openingHours?: {
    openNow: boolean;
    periods?: Array<{
      open: { day: number; time: string };
      close?: { day: number; time: string };
    }>;
    weekdayText?: string[];
  };
  reviews?: Array<{
    authorName: string;
    rating: number;
    text: string;
    time: number;
  }>;
}

export interface RestaurantRecommendation {
  restaurant: Restaurant;
  score: number;
  reasoning: string;
  suitabilityForEvent: number; // 1-10 scale
  moodMatch: number; // 1-10 scale
}

export interface BookingRequest {
  restaurant: Restaurant;
  partySize: number;
  preferredDateTime: string; // ISO string
  specialRequests?: string;
  contactInfo: {
    name: string;
    phone: string;
    email?: string;
  };
}

export interface BookingResponse {
  success: boolean;
  bookingId?: string;
  confirmationDetails?: string;
  message: string;
  alternativeOptions?: Restaurant[];
}

export interface GooglePlacesResponse {
  results: Array<{
    place_id: string;
    name: string;
    formatted_address: string;
    geometry: {
      location: {
        lat: number;
        lng: number;
      };
    };
    rating?: number;
    user_ratings_total?: number;
    price_level?: number;
    types: string[];
    photos?: Array<{
      photo_reference: string;
      height: number;
      width: number;
    }>;
    opening_hours?: {
      open_now: boolean;
    };
  }>;
  status: string;
  next_page_token?: string;
}

export interface GooglePlaceDetailsResponse {
  result: {
    place_id: string;
    name: string;
    formatted_address: string;
    formatted_phone_number?: string;
    website?: string;
    geometry: {
      location: {
        lat: number;
        lng: number;
      };
    };
    rating?: number;
    user_ratings_total?: number;
    price_level?: number;
    types: string[];
    photos?: Array<{
      photo_reference: string;
      height: number;
      width: number;
    }>;
    reservable?: boolean;
    curbside_pickup?: boolean;
    delivery?: boolean;
    dine_in?: boolean;
    takeout?: boolean;
    serves_breakfast?: boolean;
    serves_lunch?: boolean;
    serves_dinner?: boolean;
    serves_brunch?: boolean;
    serves_beer?: boolean;
    serves_wine?: boolean;
    serves_vegetarian_food?: boolean;
    opening_hours?: {
      open_now: boolean;
      periods?: Array<{
        open: { day: number; time: string };
        close?: { day: number; time: string };
      }>;
      weekday_text?: string[];
    };
    reviews?: Array<{
      author_name: string;
      rating: number;
      text: string;
      time: number;
    }>;
  };
  status: string;
}

// 🆕 NEW: Google Geocoding API response interface
export interface GoogleGeocodingResponse {
  results: Array<{
    formatted_address: string;
    geometry: {
      location: {
        lat: number;
        lng: number;
      };
      location_type: string;
    };
    place_id: string;
    types: string[];
  }>;
  status: string;
}
