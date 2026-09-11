import type { SearchRecommendationsPayload } from './types.js';
import { resolvePhotoDisplayUrl } from './photoDisplayUrl.js';

/** Public Yelp search — works without YELP_API_KEY (Fusion only adds direct menu/biz URLs). */
function yelpSearchResultsUrl(
  businessName: string,
  address: string,
  searchLocation: string
): string {
  const findDesc = encodeURIComponent(businessName.trim());
  let loc = searchLocation.trim();
  if (loc && !loc.includes(',') && /\b(CA|California)\b/i.test(address)) {
    loc = `${loc}, CA`;
  }
  const findLoc = encodeURIComponent(loc || address);
  return `https://www.yelp.com/search?find_desc=${findDesc}&find_loc=${findLoc}`;
}

function scoreNameMatch(target: string, candidate: string): number {
  const t = target.toLowerCase().trim();
  const c = candidate.toLowerCase().trim();
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

export function pickBestRestaurantForName(
  payload: SearchRecommendationsPayload,
  restaurantName: string
) {
  const ranked = payload.recommendations
    .map(rec => {
      const nameScore = scoreNameMatch(restaurantName, rec.restaurant.name);
      const qualityScore = rec.restaurant.rating * 10 + Math.min(20, rec.restaurant.userRatingsTotal / 100);
      return { rec, total: nameScore + qualityScore };
    })
    .sort((a, b) => b.total - a.total);
  return ranked[0]?.rec;
}

/**
 * Agentverse / many chat UIs collapse single `\n` into a space.
 * Join logical lines with blank lines so each survives as its own paragraph.
 */
function paragraphs(parts: Array<string | undefined | null>): string {
  return parts
    .map(p => (p ?? '').trim())
    .filter(Boolean)
    .join('\n\n');
}

export function formatRestaurantDetails(
  payload: SearchRecommendationsPayload,
  restaurantName: string,
  searchLocation: string,
  focus: 'details' | 'menu' = 'details'
): string {
  const best = pickBestRestaurantForName(payload, restaurantName);
  if (!best) {
    return paragraphs([
      `Couldn't find "${restaurantName}" near "${searchLocation}".`,
      `Tip: add the city, e.g. "details for ${restaurantName} in San Jose".`,
    ]);
  }

  const r = best.restaurant;
  const openNow =
    r.openingHours?.openNow === true
      ? 'Yes'
      : r.openingHours?.openNow === false
        ? 'No'
        : 'No / not listed';

  const blocks: string[] = [];

  blocks.push(
    [
      `📍 Restaurant Details: ${r.name}`,
      `🏠 Address ${r.address}`,
    ].join('\n')
  );

  if (focus === 'menu') {
    const menuLines: string[] = ['🍱 Menu on Yelp'];
    const yelpSearch = yelpSearchResultsUrl(r.name, r.address, searchLocation);
    if (r.yelpMenuUrl) {
      menuLines.push('');
      menuLines.push('Menu:');
      menuLines.push(r.yelpMenuUrl);
    } else {
      menuLines.push(
        `Search Yelp (opens results; pick the listing to see menu/photos): ${yelpSearch}`
      );
      if (r.website) {
        menuLines.push(`Restaurant website (may include a menu): ${r.website}`);
      }
      menuLines.push(
        'Direct Yelp menu link not available right now (common reasons: Yelp API access limits/trial status, or no exact Yelp match).'
      );
    }
    blocks.push(menuLines.join('\n'));
  }

  blocks.push(
    [
      '⭐ Review Summary',
      `Rating: ${r.rating.toFixed(1)} / 5`,
      `Reviews: ${r.userRatingsTotal.toLocaleString()}`,
      '',
      `Open now: ${openNow}`,
    ].join('\n')
  );

  const contactLines = [
    '📞 Contact & Links',
    `Phone: ${r.phoneNumber || 'Not listed'}`,
    `Website / Reservation: ${r.website || 'Not listed'}`,
    '',
    'Google Maps:',
    `${r.googleMapsUrl || 'Not listed'}`,
  ];
  if (focus !== 'menu') {
    if (r.yelpMenuUrl) {
      contactLines.push('');
      contactLines.push('Menu (Yelp):');
      contactLines.push(r.yelpMenuUrl);
    }
  }
  blocks.push(contactLines.join('\n'));

  const photosRaw = r.photos?.slice(0, 3) || [];
  const photoUrls = photosRaw
    .map(resolvePhotoDisplayUrl)
    .filter((u): u is string => Boolean(u));
  if (photoUrls.length > 0) {
    const md = photoUrls
      .map((u, idx) => `![${r.name} — photo ${idx + 1}](${u})`)
      .join('\n\n');
    blocks.push(['📸 Photos', md].join('\n\n'));
  }

  const weekday = r.openingHours?.weekdayText || [];
  blocks.push(
    ['🕒 Opening Hours', weekday.length ? weekday.join('\n') : 'Not listed'].join('\n')
  );

  // Intentionally omit recent customer reviews block for cleaner output.

  return paragraphs(blocks);
}

export type RestaurantDetailsIntent = {
  restaurantName: string;
  searchLocation: string;
  focus?: 'details' | 'menu';
};

export function parseRestaurantDetailsIntent(input: string): RestaurantDetailsIntent | null {
  const txt = input.trim();
  const fallbackLocation = process.env.AGENT_DEFAULT_PLACE || 'San Jose';

  const menuWithLocation = [
    /(?:show\s+)?(?:the\s+)?menu\s+for\s+(.+?)\s+in\s+(.+)/i,
    /^menu\s+for\s+(.+?)\s+in\s+(.+)/i,
  ];
  for (const p of menuWithLocation) {
    const m = txt.match(p);
    if (m?.[1] && m?.[2]) {
      return {
        restaurantName: m[1].trim(),
        searchLocation: m[2].trim(),
        focus: 'menu',
      };
    }
  }

  const menuNoLocation = [
    /(?:show\s+)?(?:the\s+)?menu\s+for\s+(.+)/i,
    /^menu\s+for\s+(.+)/i,
  ];
  for (const p of menuNoLocation) {
    const m = txt.match(p);
    if (m?.[1]) {
      return {
        restaurantName: m[1].trim(),
        searchLocation: fallbackLocation,
        focus: 'menu',
      };
    }
  }

  const patterns = [
    /show details for restaurant named\s+(.+?)\s+in\s+(.+)/i,
    /show details for\s+(.+?)\s+in\s+(.+)/i,
    /show details of restaurant named\s+(.+?)\s+in\s+(.+)/i,
    /show details of\s+(.+?)\s+in\s+(.+)/i,
    /details for restaurant named\s+(.+?)\s+in\s+(.+)/i,
    /details for\s+(.+?)\s+in\s+(.+)/i,
    /details of restaurant named\s+(.+?)\s+in\s+(.+)/i,
    /details of\s+(.+?)\s+in\s+(.+)/i,
  ];
  for (const p of patterns) {
    const m = txt.match(p);
    if (m?.[1] && m?.[2]) {
      return {
        restaurantName: m[1].trim(),
        searchLocation: m[2].trim(),
        focus: 'details',
      };
    }
  }

  // Support detail requests without explicit location.
  const noLocationPatterns = [
    /show details for restaurant named\s+(.+)/i,
    /show details for\s+(.+)/i,
    /show details of restaurant named\s+(.+)/i,
    /show details of\s+(.+)/i,
    /details for restaurant named\s+(.+)/i,
    /details for\s+(.+)/i,
    /details of restaurant named\s+(.+)/i,
    /details of\s+(.+)/i,
  ];
  for (const p of noLocationPatterns) {
    const m = txt.match(p);
    if (m?.[1]) {
      return {
        restaurantName: m[1].trim(),
        searchLocation: fallbackLocation,
        focus: 'details',
      };
    }
  }

  return null;
}
