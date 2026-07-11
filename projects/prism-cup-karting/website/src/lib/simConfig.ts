// Client-safe league constants for the in-browser Race Night simulator.
// A hand-kept mirror of src/prism_cup/config.py (roster, items, tracks,
// rubber-banding draw table). No node:fs — this file ships to the client.

export interface SimRacer {
  id: string;
  name: string;
  short: string;
  vibe: string;
  weightClass: "light" | "medium" | "heavy";
  accel: number;
  topSpeed: number;
  knockResistance: number;
  itemLuck: number;
  color: string;
}

export interface SimTrack {
  id: string;
  name: string;
  laps: number;
  hazard: number;
  boostPadDensity: number;
  color: string;
}

export interface SimItem {
  id: string;
  name: string;
  effect: string;
  rarity: "common" | "uncommon" | "rare";
  power: number;
}

export const RACERS: SimRacer[] = [
  { id: "fenna", name: "Fenna Blaze", short: "Fenna", vibe: "Daredevil fox", weightClass: "light", accel: 9, topSpeed: 6, knockResistance: 3, itemLuck: 1.0, color: "#FF5A5F" },
  { id: "sprocket", name: "Sprocket", short: "Sprocket", vibe: "Caffeinated squirrel", weightClass: "light", accel: 10, topSpeed: 5, knockResistance: 2, itemLuck: 1.1, color: "#F2C14E" },
  { id: "pip", name: "Pip Nimbus", short: "Pip", vibe: "Cloud sprite", weightClass: "light", accel: 9, topSpeed: 5, knockResistance: 3, itemLuck: 1.12, color: "#7ED4FF" },
  { id: "crumb", name: "Colonel Crumb", short: "Crumb", vibe: "Gingerbread brigadier", weightClass: "light", accel: 8, topSpeed: 6, knockResistance: 4, itemLuck: 0.95, color: "#D9A05B" },
  { id: "inkwell", name: "Duke Inkwell", short: "Inkwell", vibe: "Jazz-singing octopus", weightClass: "medium", accel: 7, topSpeed: 7, knockResistance: 5, itemLuck: 1.05, color: "#B07CFF" },
  { id: "marina", name: "Marina Volt", short: "Marina", vibe: "Electric-eel engineer", weightClass: "medium", accel: 7, topSpeed: 8, knockResistance: 5, itemLuck: 1.0, color: "#35E0C8" },
  { id: "rusty", name: "Rusty Piston", short: "Rusty", vibe: "Fairground robot", weightClass: "medium", accel: 6, topSpeed: 7, knockResistance: 6, itemLuck: 0.98, color: "#9AA7B8" },
  { id: "thistle", name: "Sir Reginald Thistle", short: "Thistle", vibe: "Peacock aristocrat", weightClass: "medium", accel: 8, topSpeed: 7, knockResistance: 4, itemLuck: 0.92, color: "#3D9BE9" },
  { id: "basalt", name: "Basalt", short: "Basalt", vibe: "Mountain golem", weightClass: "heavy", accel: 4, topSpeed: 9, knockResistance: 9, itemLuck: 0.9, color: "#8C8C9A" },
  { id: "magma", name: "Mama Magma", short: "Magma", vibe: "Lava-bear baker", weightClass: "heavy", accel: 5, topSpeed: 9, knockResistance: 8, itemLuck: 0.95, color: "#FF7F2A" },
  { id: "brine", name: "Captain Brine", short: "Brine", vibe: "Walrus sea-captain", weightClass: "heavy", accel: 4, topSpeed: 10, knockResistance: 8, itemLuck: 0.92, color: "#4A6FA5" },
  { id: "mossback", name: "Old Mossback", short: "Mossback", vibe: "Ancient treant", weightClass: "heavy", accel: 3, topSpeed: 9, knockResistance: 10, itemLuck: 0.98, color: "#6FBF73" },
];

export const TRACKS: SimTrack[] = [
  { id: "prism-parkway", name: "Prism Parkway", laps: 3, hazard: 4, boostPadDensity: 0.9, color: "#B07CFF" },
  { id: "molten-keep", name: "Molten Keep", laps: 4, hazard: 5, boostPadDensity: 0.4, color: "#FF7F2A" },
  { id: "sundae-speedway", name: "Sundae Speedway", laps: 5, hazard: 2, boostPadDensity: 0.7, color: "#FF9EC4" },
  { id: "haunted-manor-loop", name: "Haunted Manor Loop", laps: 4, hazard: 4, boostPadDensity: 0.3, color: "#8FE38F" },
  { id: "cloudline-circuit", name: "Cloudline Circuit", laps: 3, hazard: 3, boostPadDensity: 0.8, color: "#7ED4FF" },
  { id: "jungle-falls", name: "Jungle Falls", laps: 4, hazard: 3, boostPadDensity: 0.5, color: "#35C46B" },
  { id: "neon-harbor", name: "Neon Harbor", laps: 4, hazard: 2, boostPadDensity: 0.6, color: "#35E0C8" },
  { id: "glacier-run", name: "Glacier Run", laps: 3, hazard: 3, boostPadDensity: 0.5, color: "#A9C9FF" },
];

export const ITEMS: SimItem[] = [
  { id: "seeker-orb", name: "Seeker Orb", effect: "Homes in on the race leader and knocks them back several places. A Static Shield eats it.", rarity: "rare", power: 5 },
  { id: "tempest", name: "Tempest", effect: "Summons a storm cell that scrambles the midfield running order.", rarity: "rare", power: 4 },
  { id: "comet-boost", name: "Comet Boost", effect: "A white-hot speed burst worth up to three places.", rarity: "uncommon", power: 3 },
  { id: "static-shield", name: "Static Shield", effect: "A crackling barrier that absorbs the next hit.", rarity: "uncommon", power: 2 },
  { id: "swap-beam", name: "Swap Beam", effect: "Trades places with the kart directly ahead.", rarity: "uncommon", power: 2 },
  { id: "slick-patch", name: "Slick Patch", effect: "Drops a rainbow oil slick that spins out a kart behind.", rarity: "common", power: 2 },
  { id: "magnet-hook", name: "Magnet Hook", effect: "Reels you one place up the road.", rarity: "common", power: 1 },
];

// Rubber-banding: item draw weights per position tier (front / mid / back
// thirds of the 12-kart field). The back pulls the equalisers.
export const ITEM_TIER_WEIGHTS: Record<"front" | "mid" | "back", Record<string, number>> = {
  front: { "seeker-orb": 1, tempest: 1, "comet-boost": 8, "static-shield": 20, "swap-beam": 10, "slick-patch": 30, "magnet-hook": 30 },
  mid: { "seeker-orb": 6, tempest: 6, "comet-boost": 18, "static-shield": 18, "swap-beam": 16, "slick-patch": 18, "magnet-hook": 18 },
  back: { "seeker-orb": 20, tempest: 15, "comet-boost": 25, "static-shield": 12, "swap-beam": 14, "slick-patch": 8, "magnet-hook": 6 },
};

export const RACERS_BY_ID: Record<string, SimRacer> = Object.fromEntries(
  RACERS.map((r) => [r.id, r]),
);
export const TRACKS_BY_ID: Record<string, SimTrack> = Object.fromEntries(
  TRACKS.map((t) => [t.id, t]),
);
export const ITEMS_BY_ID: Record<string, SimItem> = Object.fromEntries(
  ITEMS.map((i) => [i.id, i]),
);
