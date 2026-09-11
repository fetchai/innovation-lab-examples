import { formatRecommendationPicks } from './formatRecommendationPicks.js';
import {
  formatRestaurantDetails,
  parseRestaurantDetailsIntent,
  type RestaurantDetailsIntent,
} from './formatRestaurantDetails.js';
import { searchRestaurantsViaMcp } from './mcpSearchClient.js';
import { parseNaturalLanguageQuery } from './parseNaturalLanguageQuery.js';
import type { RecommendationAgentOptions } from './types.js';

const DEFAULT_MCP_URL =
  process.env.MCP_SERVER_URL || 'http://127.0.0.1:3000/mcp';

/**
 * End-to-end: natural language → MCP search_restaurants → formatted picks.
 */
export async function recommendFromNaturalLanguage(
  userQuery: string,
  options?: Partial<RecommendationAgentOptions>
): Promise<string> {
  const parsed = parseNaturalLanguageQuery(userQuery);
  const mcpUrl = options?.mcpUrl ?? DEFAULT_MCP_URL;
  const topN = options?.topN ?? 3;
  const locale = options?.locale ?? parsed.locale ?? 'en';

  const payload = await searchRestaurantsViaMcp(mcpUrl, {
    ...parsed,
    locale,
  });

  return formatRecommendationPicks(payload, topN);
}

export async function respondToUserQuery(
  userQuery: string,
  options?: Partial<RecommendationAgentOptions>
): Promise<string> {
  const detailsIntent = parseRestaurantDetailsIntent(userQuery);
  if (!detailsIntent) {
    return recommendFromNaturalLanguage(userQuery, options);
  }

  const mcpUrl = options?.mcpUrl ?? DEFAULT_MCP_URL;
  const locale = options?.locale ?? 'en';
  const payload = await searchRestaurantsViaMcp(mcpUrl, {
    placeName: detailsIntent.searchLocation,
    keyword: detailsIntent.restaurantName,
    cuisineTypes: [],
    mood: 'casual',
    event: 'casual',
    locale,
    strictCuisineFiltering: false,
  });

  return formatRestaurantDetails(
    payload,
    detailsIntent.restaurantName,
    detailsIntent.searchLocation,
    detailsIntent.focus ?? 'details'
  );
}

export type { RestaurantDetailsIntent };

export {
  parseNaturalLanguageQuery,
  formatRecommendationPicks,
  searchRestaurantsViaMcp,
  formatRestaurantDetails,
  parseRestaurantDetailsIntent,
};
