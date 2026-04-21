/**
 * Turn Places API (New) photo resource names into browser-openable URLs.
 * Used for markdown image embeds in chat.
 */
export function resolvePhotoDisplayUrl(photoRef: string): string | null {
  const raw = (photoRef || '').trim();
  if (!raw) return null;
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    return raw;
  }
  const key = process.env.GOOGLE_MAPS_API_KEY?.trim();
  if (!key) return null;
  if (raw.startsWith('places/')) {
    return `https://places.googleapis.com/v1/${raw}/media?maxWidthPx=1200&key=${encodeURIComponent(key)}`;
  }
  return null;
}
