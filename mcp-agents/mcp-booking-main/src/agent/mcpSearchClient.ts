import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import type { AgentSearchParams, SearchRecommendationsPayload } from './types.js';

function parseSearchPayload(text: string): SearchRecommendationsPayload {
  const data = JSON.parse(text) as SearchRecommendationsPayload;
  if (!data || !Array.isArray(data.recommendations)) {
    throw new Error('Unexpected MCP response: missing recommendations array');
  }
  return data;
}

/**
 * Single-shot MCP call: connect → tools/call search_restaurants → close.
 */
export async function searchRestaurantsViaMcp(
  mcpEndpointUrl: string,
  params: AgentSearchParams
): Promise<SearchRecommendationsPayload> {
  const client = new Client({ name: 'restaurant-recommendation-agent', version: '1.0.0' });
  const url = new URL(mcpEndpointUrl);
  const transport = new StreamableHTTPClientTransport(url);

  try {
    await client.connect(transport);

    const result = await client.callTool({
      name: 'search_restaurants',
      arguments: {
        placeName: params.placeName,
        cuisineTypes: params.cuisineTypes,
        ...(params.keyword ? { keyword: params.keyword } : {}),
        mood: params.mood,
        event: params.event,
        ...(params.radius !== undefined ? { radius: params.radius } : {}),
        ...(params.priceLevel !== undefined ? { priceLevel: params.priceLevel } : {}),
        ...(params.locale ? { locale: params.locale } : { locale: 'en' }),
        ...(params.strictCuisineFiltering !== undefined
          ? { strictCuisineFiltering: params.strictCuisineFiltering }
          : {}),
      },
    });

    const blocks = Array.isArray(result.content) ? result.content : [];

    if (result.isError) {
      const msg =
        blocks.map(c => (c.type === 'text' ? c.text : '')).join(' ') ||
        'MCP tool returned an error';
      throw new Error(msg);
    }

    const textBlock = blocks.find(
      (c): c is { type: 'text'; text: string } => c.type === 'text'
    );
    if (!textBlock || textBlock.type !== 'text') {
      throw new Error('MCP tool returned no text content');
    }

    const trimmed = textBlock.text.trim();
    if (trimmed.startsWith('No restaurants found')) {
      return {
        searchCriteria: {
          cuisineTypes: params.cuisineTypes,
          mood: params.mood,
          event: params.event,
          placeName: params.placeName,
        },
        totalFound: 0,
        recommendations: [],
      };
    }

    return parseSearchPayload(trimmed);
  } finally {
    await client.close();
  }
}
