import type { Restaurant } from '../types/index.js';

const YELP_SEARCH_URL = 'https://api.yelp.com/v3/businesses/search';

type YelpSearchBusiness = {
  id: string;
  alias: string;
  name: string;
  url: string;
  distance?: number;
};

type YelpSearchResponse = {
  businesses?: YelpSearchBusiness[];
};

function nameMatchScore(target: string, candidate: string): number {
  const t = target.toLowerCase().trim();
  const c = candidate.toLowerCase().trim();
  if (!t || !c) return 0;
  if (t === c) return 1000;
  if (c.includes(t)) return 800;
  if (t.includes(c)) return 600;
  const tWords = new Set(t.split(/\s+/).filter(Boolean));
  const cWords = new Set(c.split(/\s+/).filter(Boolean));
  let overlap = 0;
  for (const w of tWords) {
    if (cWords.has(w)) overlap += 1;
  }
  return overlap * 50;
}

function menuUrlFromAlias(alias: string): string {
  return `https://www.yelp.com/menu/${alias}`;
}

function pickBestBusiness(
  restaurant: Restaurant,
  businesses: YelpSearchBusiness[]
): YelpSearchBusiness | null {
  if (businesses.length === 0) return null;

  let best: YelpSearchBusiness | null = null;
  let bestScore = -1;

  for (const b of businesses) {
    const nameScore = nameMatchScore(restaurant.name, b.name);
    const dist = b.distance;
    const distBoost =
      typeof dist === 'number' && !Number.isNaN(dist)
        ? Math.max(0, 600 - dist) * 0.35
        : 80;
    const total = nameScore + distBoost;
    if (total > bestScore) {
      bestScore = total;
      best = b;
    }
  }

  if (!best) return null;
  const nameScore = nameMatchScore(restaurant.name, best.name);
  const distOk = typeof best.distance === 'number' && best.distance <= 250;
  if (nameScore >= 120 || (nameScore >= 80 && distOk)) {
    return best;
  }
  return null;
}

export type YelpEnrichment = {
  yelpBusinessId?: string;
  yelpAlias?: string;
  yelpUrl?: string;
  yelpMenuUrl?: string;
};

export class YelpService {
  constructor(private readonly apiKey: string | undefined) {}

  isEnabled(): boolean {
    return Boolean(this.apiKey && this.apiKey.trim().length > 0);
  }

  /**
   * Find a Yelp business near the Google place and return profile + menu URLs.
   * Menu is not returned as structured data by Yelp Fusion; we link to Yelp's menu page for the alias.
   */
  async enrichRestaurant(restaurant: Restaurant): Promise<YelpEnrichment> {
    if (!this.isEnabled()) return {};

    const { latitude, longitude } = restaurant.location;
    if (
      typeof latitude !== 'number' ||
      typeof longitude !== 'number' ||
      Number.isNaN(latitude) ||
      Number.isNaN(longitude)
    ) {
      return {};
    }

    const baseParams: Record<string, string> = {
      term: restaurant.name,
      latitude: String(latitude),
      longitude: String(longitude),
      limit: '5',
      radius: '1200',
    };

    try {
      let businesses: YelpSearchBusiness[] = [];
      for (const categories of ['restaurants', '']) {
        const params = new URLSearchParams({ ...baseParams });
        if (categories) params.set('categories', categories);
        const res = await fetch(`${YELP_SEARCH_URL}?${params.toString()}`, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${this.apiKey}`,
            Accept: 'application/json',
          },
          signal: AbortSignal.timeout(12_000),
        });

        if (!res.ok) {
          continue;
        }

        const data = (await res.json()) as YelpSearchResponse;
        businesses = data.businesses ?? [];
        if (businesses.length > 0) break;
      }

      if (businesses.length === 0) {
        return {};
      }

      let match = pickBestBusiness(restaurant, businesses);
      // Yelp already ranks by relevance to term + coordinates; if our strict
      // name check fails, trust the top hit when it is very close.
      if (!match && businesses[0]) {
        const b = businesses[0];
        const d = b.distance;
        if (typeof d === 'number' && d <= 350) {
          match = b;
        }
      }
      if (!match) return {};

      return {
        yelpBusinessId: match.id,
        yelpAlias: match.alias,
        yelpUrl: match.url,
        yelpMenuUrl: menuUrlFromAlias(match.alias),
      };
    } catch {
      return {};
    }
  }
}
