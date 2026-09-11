import type { SearchRecommendationsPayload } from './types.js';
import { resolvePhotoDisplayUrl } from './photoDisplayUrl.js';

function priceLevelToLabel(level?: number): string {
  if (level === undefined || level === null) return 'Not listed';
  const n = Math.min(4, Math.max(0, Math.round(level)));
  if (n <= 0) return 'Not listed';
  return `${'$'.repeat(n)} (${n}/4)`;
}

/**
 * Human-friendly, non-JSON output for chat / Agentverse.
 */
export function formatRecommendationPicks(
  payload: SearchRecommendationsPayload,
  topN = 3
): string {
  const picks = payload.recommendations.slice(0, Math.min(topN, 3));
  if (picks.length === 0) {
    return 'No matches right now — try another area or cuisine.';
  }

  const lines: string[] = ['🍽️ Top Restaurant Picks:', ''];

  picks.forEach((rec, i) => {
    const r = rec.restaurant;
    const reviews =
      r.userRatingsTotal > 0 ? ` (${r.userRatingsTotal.toLocaleString()} reviews)` : '';
    lines.push(`${i + 1}. ${r.name}`);
    lines.push(`   ⭐ ${r.rating.toFixed(1)}${reviews}`);
    lines.push(`   💰 ${priceLevelToLabel(r.priceLevel)}`);
    lines.push(`   ✨ Why: ${rec.reasoning}`);
    const img = r.photos?.length
      ? resolvePhotoDisplayUrl(r.photos[0] ?? '')
      : null;
    if (img) {
      lines.push(`   ![${r.name}](${img})`);
    }
    lines.push('');
  });

  return lines.join('\n').trimEnd();
}
