import { PlacesClient } from '@googlemaps/places';
import {
  Location,
  Restaurant,
  RestaurantSearchParams,
} from '../types/index.js';

export class GoogleMapsService {
  private client: PlacesClient;

  constructor(apiKey: string) {
    this.client = new PlacesClient({
      apiKey: apiKey,
    });
  }

  /**
   * Calculate the distance between two points using the Haversine formula
   * @param lat1 Latitude of first point
   * @param lon1 Longitude of first point
   * @param lat2 Latitude of second point
   * @param lon2 Longitude of second point
   * @returns Distance in meters
   */
  private calculateDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
  ): number {
    const R = 6371000; // Earth's radius in meters
    const dLat = this.toRadians(lat2 - lat1);
    const dLon = this.toRadians(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRadians(lat1)) *
        Math.cos(this.toRadians(lat2)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c; // Distance in meters
  }

  /**
   * Convert degrees to radians
   */
  private toRadians(degrees: number): number {
    return degrees * (Math.PI / 180);
  }

  /**
   * Search for restaurants using Text Search API
   * Supports direct text queries like "good restaurant in Paris" or "sushi near Tokyo"
   */
  async searchRestaurants(
    params: RestaurantSearchParams
  ): Promise<Restaurant[]> {
    try {
      const {
        location,
        placeName,
        cuisineTypes,
        keyword,
        radius = 2000,
        locale = 'en',
      } = params;

      // Build search query for Text Search API
      let textQuery = '';

      const kwTrimmed = keyword?.trim();
      const placeTrimmed = placeName?.trim() ?? '';
      const keywordDuplicatesPlace =
        Boolean(
          kwTrimmed &&
            placeTrimmed &&
            kwTrimmed.toLowerCase() === placeTrimmed.toLowerCase()
        );
      const effectiveKeyword =
        kwTrimmed && !keywordDuplicatesPlace ? kwTrimmed : undefined;

      // If keyword is provided, prioritize it
      if (effectiveKeyword) {
        textQuery = effectiveKeyword;
        // Add location context
        if (placeName) {
          textQuery += ` in ${placeName}`;
        }
        // If cuisine types are also provided, combine them
        if (cuisineTypes && cuisineTypes.length > 0) {
          textQuery += ` ${cuisineTypes.join(' OR ')}`;
        }
      } else {
        // Build query from cuisine types and location
        const cuisineQuery =
          cuisineTypes && cuisineTypes.length > 0
            ? cuisineTypes.join(' OR ') + ' restaurant'
            : 'good restaurant';

        if (placeName) {
          textQuery = `${cuisineQuery} in ${placeName}`;
        } else {
          textQuery = cuisineQuery;
        }
      }

      // Prepare field mask based on required fields
      const fieldMask = this.getSearchFieldMask();

      // Build request for Text Search API
      let request;
      let response;

      // Use searchNearby only when we have coordinates AND no specific cuisine is requested
      if (
        location &&
        (!cuisineTypes || cuisineTypes.length === 0) &&
        !placeName
      ) {
        request = {
          includedTypes: ['restaurant'],
          locationRestriction: {
            circle: {
              center: {
                latitude: location.latitude,
                longitude: location.longitude,
              },
              radius: radius,
            },
          },
          maxResultCount: 20,
          languageCode: locale,
        };
        console.info('request', request);
        response = await this.client.searchNearby(request, {
          otherArgs: {
            headers: {
              'X-Goog-FieldMask': fieldMask,
            },
          },
        });
      } else {
        // Use searchText for:
        // 1. Place name searches (with or without cuisine)
        // 2. Coordinate searches with specific cuisine
        // 3. Keyword searches
        if (location && !placeName) {
          // Coordinate-based search with cuisine - add location bias
          request = {
            textQuery,
            locationBias: {
              circle: {
                center: {
                  latitude: location.latitude,
                  longitude: location.longitude,
                },
                radius: radius,
              },
            },
            maxResultCount: 20,
            languageCode: locale,
          };
        } else {
          // Place name search or no location provided
          request = {
            textQuery,
            maxResultCount: 20,
            languageCode: locale,
          };
        }
        console.info('request', request);
        response = await this.client.searchText(request, {
          otherArgs: {
            headers: {
              'X-Goog-FieldMask': fieldMask,
            },
          },
        });
      }

      if (!response?.[0]?.places) {
        return [];
      }

      const places = response[0].places;

      // Convert API response to Restaurant objects
      const restaurants: Restaurant[] = [];

      for (const place of places) {
        try {
          const restaurant = this.convertPlaceToRestaurant(place, location);
          if (restaurant) {
            restaurants.push(restaurant);
          }
        } catch (error) {
          console.error('Error converting place to restaurant:', error);
        }
      }

      // Sort restaurants by distance if location provided
      if (location) {
        restaurants.sort((a, b) => {
          const distanceA = a.distance || 0;
          const distanceB = b.distance || 0;
          return distanceA - distanceB;
        });
      }

      return restaurants;
    } catch (error) {
      console.error('Error searching restaurants:', error);
      throw new Error(
        `Failed to search restaurants: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`
      );
    }
  }

  /**
   * Get field mask for search requests based on SKU tiers
   */
  private getSearchFieldMask(): string {
    // Using Pro SKU fields for comprehensive restaurant data
    const proFields = [
      'places.id',
      'places.displayName',
      'places.formattedAddress',
      'places.location',
      'places.types',
      'places.primaryType',
      'places.businessStatus',
      'places.googleMapsUri',
      'places.photos',
    ];

    // Adding Enterprise SKU fields for restaurant-specific data
    const enterpriseFields = [
      'places.rating',
      'places.userRatingCount',
      'places.priceLevel',
      'places.currentOpeningHours',
      'places.internationalPhoneNumber',
      'places.websiteUri',
    ];

    // Adding Enterprise + Atmosphere SKU fields for booking and service info
    const atmosphereFields = [
      'places.reservable',
      'places.curbsidePickup',
      'places.delivery',
      'places.dineIn',
      'places.takeout',
      'places.servesBreakfast',
      'places.servesLunch',
      'places.servesDinner',
      'places.servesBrunch',
      'places.servesBeer',
      'places.servesWine',
      'places.servesVegetarianFood',
      'places.reviews',
    ];

    return [...proFields, ...enterpriseFields, ...atmosphereFields].join(',');
  }

  /**
   * Convert API place response to Restaurant object
   */
  private convertPlaceToRestaurant(
    place: any,
    searchLocation?: Location
  ): Restaurant | null {
    try {
      // Validate required fields
      if (
        !place.id ||
        !place.displayName ||
        !place.formattedAddress ||
        !place.location
      ) {
        return null;
      }

      // Calculate distance if search location provided
      let distance: number | undefined;
      if (searchLocation && place.location) {
        distance = Math.round(
          this.calculateDistance(
            searchLocation.latitude,
            searchLocation.longitude,
            place.location.latitude,
            place.location.longitude
          )
        );
      }

      // Analyze booking information from website
      const bookingInfo = this.analyzeBookingInfo(
        place.websiteUri,
        place.internationalPhoneNumber
      );

      // Generate Google Maps URL
      const googleMapsUrl =
        place.googleMapsUri || this.generateGoogleMapsUrl(place.id);

      // Include photo references (up to 3) for downstream detail rendering.
      const photos =
        place.photos?.slice(0, 3).map((photo: any) => {
          if (photo?.name) return photo.name as string;
          if (photo?.photoReference) return photo.photoReference as string;
          return '';
        }).filter((p: string) => p.length > 0) || [];

      // Convert reviews if present
      const reviews =
        place.reviews?.map((review: any) => ({
          authorName: review.authorAttribution?.displayName || 'Anonymous',
          rating: review.rating || 0,
          text: review.text?.text || '',
          time: review.publishTime ? Date.parse(review.publishTime) : 0,
        })) || [];

      return {
        placeId: place.id,
        name: place.displayName?.text || place.displayName,
        address: place.formattedAddress,
        location: {
          latitude: place.location.latitude,
          longitude: place.location.longitude,
        },
        rating: place.rating || 0,
        userRatingsTotal: place.userRatingCount || 0,
        priceLevel: this.convertPriceLevelFromEnum(place.priceLevel),
        cuisineTypes: this.extractCuisineTypes(place.types || []),
        photos,
        phoneNumber: place.internationalPhoneNumber,
        website: place.websiteUri,
        googleMapsUrl,
        distance,
        bookingInfo,
        reservable: place.reservable || false,
        curbsidePickup: place.curbsidePickup || false,
        delivery: place.delivery || false,
        dineIn: place.dineIn || false,
        takeout: place.takeout || false,
        servesBreakfast: place.servesBreakfast || false,
        servesLunch: place.servesLunch || false,
        servesDinner: place.servesDinner || false,
        servesBrunch: place.servesBrunch || false,
        servesBeer: place.servesBeer || false,
        servesWine: place.servesWine || false,
        servesVegetarianFood: place.servesVegetarianFood || false,
        openingHours: place.currentOpeningHours
          ? {
              openNow: place.currentOpeningHours.openNow || false,
              weekdayText: place.currentOpeningHours.weekdayDescriptions,
            }
          : undefined,
        reviews: reviews.slice(0, 5), // Limit to 5 reviews
      };
    } catch (error) {
      console.error('Error converting place to restaurant:', error);
      return null;
    }
  }

  /**
   * Convert price level enum back to number
   */
  private convertPriceLevelFromEnum(priceLevel?: string): number | undefined {
    if (!priceLevel) return undefined;

    const priceLevels: { [key: string]: number } = {
      PRICE_LEVEL_INEXPENSIVE: 1,
      PRICE_LEVEL_MODERATE: 2,
      PRICE_LEVEL_EXPENSIVE: 3,
      PRICE_LEVEL_VERY_EXPENSIVE: 4,
    };
    return priceLevels[priceLevel];
  }

  /**
   * Analyze booking information from website URL and phone number
   */
  private analyzeBookingInfo(
    website?: string,
    phoneNumber?: string
  ): {
    reservable: boolean;
    bookingUrl?: string;
    bookingPlatform?:
      | 'opentable'
      | 'resy'
      | 'yelp'
      | 'restaurant_website'
      | 'google_reserve'
      | 'other';
    supportsOnlineBooking: boolean;
    requiresPhone: boolean;
  } {
    const bookingInfo: {
      reservable: boolean;
      bookingUrl?: string;
      bookingPlatform?:
        | 'opentable'
        | 'resy'
        | 'yelp'
        | 'restaurant_website'
        | 'google_reserve'
        | 'other';
      supportsOnlineBooking: boolean;
      requiresPhone: boolean;
    } = {
      reservable: false,
      supportsOnlineBooking: false,
      requiresPhone: false,
    };

    // Check if phone number is available for reservations
    if (phoneNumber) {
      bookingInfo.reservable = true;
      bookingInfo.requiresPhone = true;
    }

    // Analyze website for booking platforms
    if (website) {
      const url = website.toLowerCase();
      let hostname = '';
      try {
        hostname = new URL(website).hostname.toLowerCase();
      } catch (_e) {
        // If website is not a valid URL, fallback to substring checks (optional)
        hostname = '';
      }

      // OpenTable detection
      if (hostname === 'opentable.com' || hostname.endsWith('.opentable.com')) {
        return {
          ...bookingInfo,
          reservable: true,
          bookingUrl: website,
          bookingPlatform: 'opentable',
          supportsOnlineBooking: true,
          requiresPhone: false,
        };
      }

      // Resy detection
      if (hostname === 'resy.com' || hostname.endsWith('.resy.com')) {
        return {
          ...bookingInfo,
          reservable: true,
          bookingUrl: website,
          bookingPlatform: 'resy',
          supportsOnlineBooking: true,
          requiresPhone: false,
        };
      }

      // Yelp reservations detection
      if (
        (hostname === 'yelp.com' || hostname.endsWith('.yelp.com')) &&
        (url.includes('reservations') || url.includes('book'))
      ) {
        return {
          ...bookingInfo,
          reservable: true,
          bookingUrl: website,
          bookingPlatform: 'yelp',
          supportsOnlineBooking: true,
          requiresPhone: false,
        };
      }

      // Google Reserve detection
      if (
        hostname === 'reserve.google.com' ||
        (hostname === 'google.com' && url.includes('/reserve'))
      ) {
        return {
          ...bookingInfo,
          reservable: true,
          bookingUrl: website,
          bookingPlatform: 'google_reserve',
          supportsOnlineBooking: true,
          requiresPhone: false,
        };
      }

      // Generic restaurant website with potential booking
      if (this.hasBookingKeywords(url)) {
        return {
          ...bookingInfo,
          reservable: true,
          bookingUrl: website,
          bookingPlatform: 'restaurant_website',
          supportsOnlineBooking: true,
          requiresPhone: false,
        };
      }

      // Website exists but no clear booking platform detected
      bookingInfo.reservable = true;
      bookingInfo.bookingUrl = website;
      bookingInfo.bookingPlatform = 'other';
    }

    return bookingInfo;
  }

  /**
   * Check if URL contains booking-related keywords
   */
  private hasBookingKeywords(url: string): boolean {
    const bookingKeywords = [
      'reservation',
      'reservations',
      'book',
      'booking',
      'table',
      'reserve',
      'dine',
      'dining',
      'order',
      'menu',
    ];

    return bookingKeywords.some(keyword => url.includes(keyword));
  }

  /**
   * Generate Google Maps URL for a restaurant
   */
  private generateGoogleMapsUrl(placeId: string): string {
    // Use place_id for the most accurate Google Maps URL
    // This format directly opens the place in Google Maps
    return `https://www.google.com/maps/search/?api=1&query=Google&query_place_id=${placeId}`;
  }

  /**
   * Extract cuisine types from Google Places types array
   */
  private extractCuisineTypes(types: string[]): string[] {
    const cuisineMap: { [key: string]: string } = {
      chinese_restaurant: 'Chinese',
      japanese_restaurant: 'Japanese',
      korean_restaurant: 'Korean',
      thai_restaurant: 'Thai',
      vietnamese_restaurant: 'Vietnamese',
      indian_restaurant: 'Indian',
      italian_restaurant: 'Italian',
      french_restaurant: 'French',
      mexican_restaurant: 'Mexican',
      american_restaurant: 'American',
      mediterranean_restaurant: 'Mediterranean',
      greek_restaurant: 'Greek',
      turkish_restaurant: 'Turkish',
      spanish_restaurant: 'Spanish',
      german_restaurant: 'German',
      brazilian_restaurant: 'Brazilian',
      seafood_restaurant: 'Seafood',
      steakhouse: 'Steakhouse',
      pizza_restaurant: 'Pizza',
      bakery: 'Bakery',
      cafe: 'Cafe',
      fast_food_restaurant: 'Fast Food',
      fine_dining_restaurant: 'Fine Dining',
      buffet_restaurant: 'Buffet',
      barbecue_restaurant: 'BBQ',
      sushi_restaurant: 'Sushi',
      vegetarian_restaurant: 'Vegetarian',
      vegan_restaurant: 'Vegan',
    };

    const cuisines: string[] = [];

    for (const type of types) {
      // Handle both old format and new format types
      const typeKey =
        typeof type === 'string' ? type : String(type).toLowerCase();
      if (cuisineMap[typeKey]) {
        cuisines.push(cuisineMap[typeKey]);
      }
    }

    // If no specific cuisine found, add generic restaurant type
    if (
      cuisines.length === 0 &&
      (types.includes('restaurant') || types.includes('establishment'))
    ) {
      cuisines.push('Restaurant');
    }

    return cuisines;
  }

  /**
   * Search for restaurants with specific cuisine types
   */
  async searchByCuisine(
    locationOrPlaceName: Location | string,
    cuisineType: string,
    radius: number = 7000,
    locale: string = 'en'
  ): Promise<Restaurant[]> {
    const searchParams: RestaurantSearchParams = {
      ...(typeof locationOrPlaceName === 'string'
        ? { placeName: locationOrPlaceName }
        : { location: locationOrPlaceName }),
      cuisineTypes: [cuisineType],
      mood: '',
      event: 'casual dining',
      radius,
      locale,
    };

    return this.searchRestaurants(searchParams);
  }
}
