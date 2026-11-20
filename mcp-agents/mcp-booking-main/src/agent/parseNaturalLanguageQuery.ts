import type { ParsedUserQuery } from './types.js';

const DEFAULT_PLACE =
  process.env.AGENT_DEFAULT_PLACE || 'Taipei, Taiwan';

const CUISINE_KEYWORDS: Array<{ match: RegExp; label: string }> = [
  { match: /\bitalian\b/i, label: 'Italian' },
  { match: /\bjapanese\b/i, label: 'Japanese' },
  { match: /\bsushi\b/i, label: 'Japanese' },
  { match: /\bramen\b/i, label: 'Japanese' },
  { match: /\bmexican\b/i, label: 'Mexican' },
  { match: /\bchinese\b/i, label: 'Chinese' },
  { match: /\bdim sum\b/i, label: 'Chinese' },
  { match: /\bindian\b/i, label: 'Indian' },
  { match: /\bfrench\b/i, label: 'French' },
  { match: /\bthai\b/i, label: 'Thai' },
  { match: /\bkorean\b/i, label: 'Korean' },
  { match: /\bmediterranean\b/i, label: 'Mediterranean' },
  { match: /\bamerican\b/i, label: 'American' },
  { match: /\bsteakhouse\b|\bsteak\b/i, label: 'Steakhouse' },
  { match: /\bseafood\b/i, label: 'Seafood' },
  { match: /\bbbq\b|\bbarbecue\b/i, label: 'Barbecue' },
  { match: /\bvietnamese\b/i, label: 'Vietnamese' },
  { match: /\bgreek\b/i, label: 'Greek' },
  { match: /\bspanish\b|\btapas\b/i, label: 'Spanish' },
  { match: /\bpizza\b/i, label: 'Italian' },
];

const MOOD_RULES: Array<{ match: RegExp; mood: string }> = [
  { match: /\bromantic\b|\bdate night\b|\bcandlelit\b/i, mood: 'romantic' },
  { match: /\bquiet\b|\bintimate\b|\blow[- ]key\b/i, mood: 'quiet' },
  { match: /\bupscale\b|\bfine dining\b|\bluxury\b|\bbougie\b/i, mood: 'upscale' },
  { match: /\blively\b|\bfun\b|\benergetic\b/i, mood: 'fun' },
  { match: /\bcasual\b|\brelaxed\b/i, mood: 'casual' },
];

const EVENT_RULES: Array<{ match: RegExp; event: string }> = [
  { match: /\bbusiness\b|\blunch meeting\b|\bclient\b|\bwork\b/i, event: 'business' },
  { match: /\bbirthday\b|\banniversary\b|\bcelebration\b|\bparty\b/i, event: 'celebration' },
  { match: /\bfamily\b|\bkids\b|\bchildren\b/i, event: 'family' },
  { match: /\bdate\b|\bromantic\b|\banniversary dinner\b/i, event: 'dating' },
  { match: /\bgathering\b|\bfriends\b|\bgroup\b/i, event: 'gathering' },
  { match: /\bdinner\b|\blunch\b|\bbrunch\b|\bmeal\b|\beat\b/i, event: 'casual' },
];

const PRICE_RULES: Array<{ match: RegExp; level: 1 | 2 | 3 | 4 }> = [
  { match: /\bcheap\b|\baffordable\b|\bbudget\b/i, level: 1 },
  { match: /\bmoderate\b|\bmid[- ]range\b/i, level: 2 },
  { match: /\bpricey\b|\bsplurge\b/i, level: 3 },
  { match: /\bexpensive\b|\bfine dining\b|\bluxury\b/i, level: 4 },
];

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Strip location and cuisine tokens to derive a dish keyword for Google text search (optional).
 * The resolved place name must not become the keyword (avoids e.g. "San Jose in San Jose").
 */
function extractKeyword(
  q: string,
  _cuisines: string[],
  placeName: string
): string | undefined {
  let s = q;
  const place = placeName.trim();
  if (place) {
    s = s.replace(
      new RegExp(`\\b(?:in|near|around)\\s+${escapeRegExp(place)}\\b`, 'i'),
      ' '
    );
    s = s.replace(new RegExp(`\\b${escapeRegExp(place)}\\b`, 'gi'), ' ');
  }
  for (const { match } of CUISINE_KEYWORDS) {
    s = s.replace(match, ' ');
  }
  s = s.replace(/\b(?:in|near|around|for|a|an|the|dinner|lunch|brunch|breakfast|restaurant|place|spot)\b/gi, ' ');
  s = s.replace(/\b(?:romantic|casual|quiet|fun|upscale|business|family|celebration|date|gathering)\b/gi, ' ');
  s = s.trim().replace(/\s+/g, ' ');
  if (!s || s.length < 2) return undefined;
  if (place && s.toLowerCase() === place.toLowerCase()) return undefined;
  return s.length > 48 ? s.slice(0, 48).trim() : s;
}

function extractPlaceName(q: string): string | undefined {
  const m = q.match(
    /\b(?:in|near|around)\s+([A-Za-z][A-Za-z\s,'.-]{1,80}?)(?:\s*$|\s+(?:for|with|tonight|today)?\s*$)/i
  );
  if (m?.[1]) {
    return m[1].replace(/\s+$/, '').trim();
  }
  return undefined;
}

function inferMood(q: string): string {
  for (const { match, mood } of MOOD_RULES) {
    if (match.test(q)) return mood;
  }
  return 'casual';
}

function inferEvent(q: string): string {
  for (const { match, event } of EVENT_RULES) {
    if (match.test(q)) return event;
  }
  return 'casual';
}

function inferPriceLevel(q: string): 1 | 2 | 3 | 4 | undefined {
  for (const { match, level } of PRICE_RULES) {
    if (match.test(q)) return level;
  }
  return undefined;
}

/**
 * Rule-based NL → structured params. No network calls; stateless.
 */
export function parseNaturalLanguageQuery(userText: string): ParsedUserQuery {
  const rawQuery = userText.trim();
  const q = rawQuery;
  const lower = q.toLowerCase();

  const cuisineTypes: string[] = [];
  const seen = new Set<string>();
  for (const { match, label } of CUISINE_KEYWORDS) {
    if (match.test(lower) && !seen.has(label)) {
      seen.add(label);
      cuisineTypes.push(label);
    }
  }

  const placeName = extractPlaceName(q) || DEFAULT_PLACE;
  const mood = inferMood(lower);
  const event = inferEvent(lower);
  const priceLevel = inferPriceLevel(lower);
  const keyword = extractKeyword(q, cuisineTypes, placeName);

  return {
    rawQuery,
    placeName,
    cuisineTypes,
    ...(keyword ? { keyword } : {}),
    mood,
    event,
    ...(priceLevel !== undefined ? { priceLevel } : {}),
    locale: process.env.AGENT_LOCALE || 'en',
  };
}
