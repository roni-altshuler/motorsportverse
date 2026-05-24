/**
 * Race photography mapping — one Unsplash photo per Grand Prix.
 *
 * Returns a public photo URL (Unsplash Source CDN) sized to a 16:9 hero
 * aspect ratio (1296x729). Falls back to the per-round matplotlib track-map
 * webp when no curated photo exists for a GP key.
 *
 * Why Unsplash Source: free-to-use license, no API key required, image URLs
 * are stable, and we can swap individual photos by editing this file
 * without touching the Python pipeline. When we eventually want offline
 * builds, run `scripts/fetch-race-art.ts` to pre-fetch + sharp these into
 * `public/race-art/<gpKey>.webp`.
 *
 * The map keys are F1 `gpKey` strings (as emitted by export_website_data.py).
 * Keep keys in sync with the calendar JSON — when a calendar gpKey changes,
 * update this map.
 */

interface RaceArt {
  src: string;
  credit: string;
  source: "unsplash";
}

// Curated Unsplash IDs — chosen for race / motorsport / circuit / city aesthetic
// per GP. Keep IDs current; broken IDs fall back to the track-map webp.
const RACE_ART: Record<string, RaceArt> = {
  // 2026 calendar — ordered by typical round number
  australia: {
    src: "https://images.unsplash.com/photo-1517994112540-009c47ea476b?w=1296&h=729&fit=crop&q=80",
    credit: "Albert Park silhouette · Unsplash",
    source: "unsplash",
  },
  china: {
    src: "https://images.unsplash.com/photo-1545893835-abaa50cbe628?w=1296&h=729&fit=crop&q=80",
    credit: "Shanghai night skyline · Unsplash",
    source: "unsplash",
  },
  japan: {
    src: "https://images.unsplash.com/photo-1545569310-4ad9d97eef64?w=1296&h=729&fit=crop&q=80",
    credit: "Mt Fuji backdrop · Unsplash",
    source: "unsplash",
  },
  bahrain: {
    src: "https://images.unsplash.com/photo-1577985043696-8bd54d9f093f?w=1296&h=729&fit=crop&q=80",
    credit: "Desert dusk · Unsplash",
    source: "unsplash",
  },
  saudi: {
    src: "https://images.unsplash.com/photo-1559825481-12a05cc00344?w=1296&h=729&fit=crop&q=80",
    credit: "Jeddah corniche · Unsplash",
    source: "unsplash",
  },
  miami: {
    src: "https://images.unsplash.com/photo-1535498730771-e735b998cd64?w=1296&h=729&fit=crop&q=80",
    credit: "Miami skyline · Unsplash",
    source: "unsplash",
  },
  imola: {
    src: "https://images.unsplash.com/photo-1583161058518-4a78ac49dccf?w=1296&h=729&fit=crop&q=80",
    credit: "Imola hills · Unsplash",
    source: "unsplash",
  },
  monaco: {
    src: "https://images.unsplash.com/photo-1554435493-93422e8d1a41?w=1296&h=729&fit=crop&q=80",
    credit: "Monte Carlo harbour · Unsplash",
    source: "unsplash",
  },
  canada: {
    src: "https://images.unsplash.com/photo-1517935706615-2717063c2225?w=1296&h=729&fit=crop&q=80",
    credit: "Montréal cityscape · Unsplash",
    source: "unsplash",
  },
  spain: {
    src: "https://images.unsplash.com/photo-1539037116277-4db20889f2d4?w=1296&h=729&fit=crop&q=80",
    credit: "Barcelona Sagrada Família · Unsplash",
    source: "unsplash",
  },
  austria: {
    src: "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1296&h=729&fit=crop&q=80",
    credit: "Styrian Alps · Unsplash",
    source: "unsplash",
  },
  great_britain: {
    src: "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=1296&h=729&fit=crop&q=80",
    credit: "British countryside · Unsplash",
    source: "unsplash",
  },
  britain: {
    src: "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=1296&h=729&fit=crop&q=80",
    credit: "British countryside · Unsplash",
    source: "unsplash",
  },
  belgium: {
    src: "https://images.unsplash.com/photo-1505761671935-60b3a7427bad?w=1296&h=729&fit=crop&q=80",
    credit: "Ardennes forest · Unsplash",
    source: "unsplash",
  },
  hungary: {
    src: "https://images.unsplash.com/photo-1541849546-216549ae216d?w=1296&h=729&fit=crop&q=80",
    credit: "Budapest river · Unsplash",
    source: "unsplash",
  },
  netherlands: {
    src: "https://images.unsplash.com/photo-1534351590666-13e3e96c5017?w=1296&h=729&fit=crop&q=80",
    credit: "Zandvoort coast · Unsplash",
    source: "unsplash",
  },
  italy: {
    src: "https://images.unsplash.com/photo-1531572753322-ad063cecc140?w=1296&h=729&fit=crop&q=80",
    credit: "Monza royal park · Unsplash",
    source: "unsplash",
  },
  azerbaijan: {
    src: "https://images.unsplash.com/photo-1593253418107-edbe6a6bb6cb?w=1296&h=729&fit=crop&q=80",
    credit: "Baku flame towers · Unsplash",
    source: "unsplash",
  },
  singapore: {
    src: "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=1296&h=729&fit=crop&q=80",
    credit: "Singapore skyline · Unsplash",
    source: "unsplash",
  },
  united_states: {
    src: "https://images.unsplash.com/photo-1531218150217-54595bc2b934?w=1296&h=729&fit=crop&q=80",
    credit: "Austin Texas skyline · Unsplash",
    source: "unsplash",
  },
  usa: {
    src: "https://images.unsplash.com/photo-1531218150217-54595bc2b934?w=1296&h=729&fit=crop&q=80",
    credit: "Austin Texas skyline · Unsplash",
    source: "unsplash",
  },
  mexico: {
    src: "https://images.unsplash.com/photo-1518105779142-d975f22f1b0a?w=1296&h=729&fit=crop&q=80",
    credit: "Mexico City Bellas Artes · Unsplash",
    source: "unsplash",
  },
  brazil: {
    src: "https://images.unsplash.com/photo-1483729558449-99ef09a8c325?w=1296&h=729&fit=crop&q=80",
    credit: "São Paulo at dusk · Unsplash",
    source: "unsplash",
  },
  sao_paulo: {
    src: "https://images.unsplash.com/photo-1483729558449-99ef09a8c325?w=1296&h=729&fit=crop&q=80",
    credit: "São Paulo at dusk · Unsplash",
    source: "unsplash",
  },
  las_vegas: {
    src: "https://images.unsplash.com/photo-1581351721010-8cf859cb14a4?w=1296&h=729&fit=crop&q=80",
    credit: "Las Vegas strip neon · Unsplash",
    source: "unsplash",
  },
  qatar: {
    src: "https://images.unsplash.com/photo-1568834010441-78a90f0fefca?w=1296&h=729&fit=crop&q=80",
    credit: "Doha skyline · Unsplash",
    source: "unsplash",
  },
  abu_dhabi: {
    src: "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=1296&h=729&fit=crop&q=80",
    credit: "Abu Dhabi skyline · Unsplash",
    source: "unsplash",
  },
};

/**
 * Pick the best art URL for a given gpKey + round. Falls back to the
 * matplotlib track_map.webp when the gpKey isn't in the curated map.
 */
export function getRaceArt(
  gpKey: string,
  round: number,
  basePath: string = "",
): { src: string; credit: string | null } {
  const art = RACE_ART[gpKey?.toLowerCase()];
  if (art) {
    return { src: art.src, credit: art.credit };
  }
  // Fallback: the matplotlib-generated track map for the round.
  const trackImg = `${basePath}/visualizations/round_${String(round).padStart(
    2,
    "0",
  )}/track_map.webp`;
  return { src: trackImg, credit: null };
}
