import type { RestaurantSearchParams } from '../types/index.js';

export type PriceLevelLabel = 1 | 2 | 3 | 4;

/** Structured input sent to MCP search_restaurants */
export interface AgentSearchParams {
  placeName: string;
  cuisineTypes: string[];
  keyword?: string;
  mood: string;
  event: string;
  radius?: number;
  priceLevel?: PriceLevelLabel;
  locale?: string;
  strictCuisineFiltering?: boolean;
}

/** Parsed NL query ready for search */
export interface ParsedUserQuery extends AgentSearchParams {
  rawQuery: string;
}

export interface SearchRecommendationsPayload {
  searchCriteria: RestaurantSearchParams;
  totalFound: number;
  recommendations: Array<{
    restaurant: {
      placeId: string;
      name: string;
      address: string;
      rating: number;
      userRatingsTotal: number;
      priceLevel?: number;
      cuisineTypes: string[];
      googleMapsUrl?: string;
      yelpBusinessId?: string;
      yelpAlias?: string;
      yelpUrl?: string;
      yelpMenuUrl?: string;
      website?: string;
      phoneNumber?: string;
      photos?: string[];
      openingHours?: {
        openNow: boolean;
        weekdayText?: string[];
      };
      reviews?: Array<{
        authorName: string;
        rating: number;
        text: string;
        time: number;
      }>;
    };
    score: number;
    reasoning: string;
    suitabilityForEvent: number;
    moodMatch: number;
  }>;
}

export type RecommendationAgentOptions = {
  mcpUrl: string;
  /** Max picks to show (2–3) */
  topN?: number;
  locale?: string;
};
