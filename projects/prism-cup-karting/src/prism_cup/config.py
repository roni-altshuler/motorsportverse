"""League configuration for Prism Cup Karting.

Everything here — racers, items, tracks, cups — is invented for this project.
It is a fan-made homage to the arcade kart-racer genre with fully original
names and fully simulated results. Not affiliated with any video game company.

Stat scales
-----------
accel / top_speed / knock_resistance are 1-10. Weight classes trade them off:
light karts launch hard but get flung far by hits; heavies are slow off the
line, huge at top speed, and barely flinch when struck. item_luck is a
multiplier (~0.90-1.12) on the per-lap chance of drawing an item.
"""

from __future__ import annotations

# Deterministic season: the published site data is always this seed.
SEASON_SEED = 7042026

FIELD_SIZE = 12

# Kart-style points for a 12-kart field, P1 -> P12.
POINTS = [15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

WEIGHT_CLASSES = {
    "light": {"label": "Light", "trait": "Razor launch, fragile in traffic"},
    "medium": {"label": "Medium", "trait": "Balanced pace and durability"},
    "heavy": {"label": "Heavy", "trait": "Freight-train top speed, shrugs off hits"},
}

ROSTER = [
    # ── Light class ──────────────────────────────────────────────────
    {
        "id": "fenna",
        "name": "Fenna Blaze",
        "vibe": "Daredevil fox",
        "weight_class": "light",
        "accel": 9,
        "top_speed": 6,
        "knock_resistance": 3,
        "item_luck": 1.00,
        "color": "#FF5A5F",
        "bio": "A stunt-show fox who treats every guardrail as a suggestion and every gap as a dare.",
    },
    {
        "id": "sprocket",
        "name": "Sprocket",
        "vibe": "Caffeinated squirrel",
        "weight_class": "light",
        "accel": 10,
        "top_speed": 5,
        "knock_resistance": 2,
        "item_luck": 1.10,
        "color": "#F2C14E",
        "bio": "A squirrel on her fourth espresso, convinced brakes are for people with spare time.",
    },
    {
        "id": "pip",
        "name": "Pip Nimbus",
        "vibe": "Cloud sprite",
        "weight_class": "light",
        "accel": 9,
        "top_speed": 5,
        "knock_resistance": 3,
        "item_luck": 1.12,
        "color": "#7ED4FF",
        "bio": "A static-charged cloud sprite who drifts through corners it technically never touches.",
    },
    {
        "id": "crumb",
        "name": "Colonel Crumb",
        "vibe": "Gingerbread brigadier",
        "weight_class": "light",
        "accel": 8,
        "top_speed": 6,
        "knock_resistance": 4,
        "item_luck": 0.95,
        "color": "#D9A05B",
        "bio": "A gingerbread officer holding the racing line with a sugar-glaze helmet and zero fear.",
    },
    # ── Medium class ─────────────────────────────────────────────────
    {
        "id": "inkwell",
        "name": "Duke Inkwell",
        "vibe": "Jazz-singing octopus",
        "weight_class": "medium",
        "accel": 7,
        "top_speed": 7,
        "knock_resistance": 5,
        "item_luck": 1.05,
        "color": "#B07CFF",
        "bio": "A jazz-singing octopus who steers with six arms and conducts the pit crew with two.",
    },
    {
        "id": "marina",
        "name": "Marina Volt",
        "vibe": "Electric-eel engineer",
        "weight_class": "medium",
        "accel": 7,
        "top_speed": 8,
        "knock_resistance": 5,
        "item_luck": 1.00,
        "color": "#35E0C8",
        "bio": "An electric-eel sparkwright who wired her own kart — and, allegedly, the competition's.",
    },
    {
        "id": "rusty",
        "name": "Rusty Piston",
        "vibe": "Retired fairground robot",
        "weight_class": "medium",
        "accel": 6,
        "top_speed": 7,
        "knock_resistance": 6,
        "item_luck": 0.98,
        "color": "#9AA7B8",
        "bio": "A fairground robot who has been doing loops since before loops were considered cool.",
    },
    {
        "id": "thistle",
        "name": "Sir Reginald Thistle",
        "vibe": "Pompous peacock aristocrat",
        "weight_class": "medium",
        "accel": 8,
        "top_speed": 7,
        "knock_resistance": 4,
        "item_luck": 0.92,
        "color": "#3D9BE9",
        "bio": "A peacock aristocrat who insists the trophy simply happens to match his plumage.",
    },
    # ── Heavy class ──────────────────────────────────────────────────
    {
        "id": "basalt",
        "name": "Basalt",
        "vibe": "Stoic mountain golem",
        "weight_class": "heavy",
        "accel": 4,
        "top_speed": 9,
        "knock_resistance": 9,
        "item_luck": 0.90,
        "color": "#8C8C9A",
        "bio": "A mountain golem of few words. The mountain, however, is moving at 140 mph.",
    },
    {
        "id": "magma",
        "name": "Mama Magma",
        "vibe": "Lava-bear baker",
        "weight_class": "heavy",
        "accel": 5,
        "top_speed": 9,
        "knock_resistance": 8,
        "item_luck": 0.95,
        "color": "#FF7F2A",
        "bio": "A lava-bear baker whose victory cakes are legally classified as geothermal events.",
    },
    {
        "id": "brine",
        "name": "Captain Brine",
        "vibe": "Barnacled walrus sea-captain",
        "weight_class": "heavy",
        "accel": 4,
        "top_speed": 10,
        "knock_resistance": 8,
        "item_luck": 0.92,
        "color": "#4A6FA5",
        "bio": "A walrus captain who has never once lifted, on land or at sea.",
    },
    {
        "id": "mossback",
        "name": "Old Mossback",
        "vibe": "Ancient treant",
        "weight_class": "heavy",
        "accel": 3,
        "top_speed": 9,
        "knock_resistance": 10,
        "item_luck": 0.98,
        "color": "#6FBF73",
        "bio": "An ancient treant who grew his own kart and refuses to say from what.",
    },
]

# ── Items ────────────────────────────────────────────────────────────
# `power` is a coarse strength score used by the rubber-banding draw table
# (and by the tests to prove back-of-field draws outclass the front's).
ITEMS = [
    {
        "id": "seeker-orb",
        "name": "Seeker Orb",
        "effect": "Homes in on the race leader and knocks them back several places. "
        "A Static Shield eats it.",
        "rarity": "rare",
        "power": 5,
    },
    {
        "id": "tempest",
        "name": "Tempest",
        "effect": "Summons a storm cell that scrambles the midfield running order.",
        "rarity": "rare",
        "power": 4,
    },
    {
        "id": "comet-boost",
        "name": "Comet Boost",
        "effect": "A white-hot speed burst worth up to three places.",
        "rarity": "uncommon",
        "power": 3,
    },
    {
        "id": "static-shield",
        "name": "Static Shield",
        "effect": "A crackling barrier that absorbs the next hit.",
        "rarity": "uncommon",
        "power": 2,
    },
    {
        "id": "swap-beam",
        "name": "Swap Beam",
        "effect": "Trades places with the kart directly ahead.",
        "rarity": "uncommon",
        "power": 2,
    },
    {
        "id": "slick-patch",
        "name": "Slick Patch",
        "effect": "Drops a rainbow oil slick that spins out a kart behind.",
        "rarity": "common",
        "power": 2,
    },
    {
        "id": "magnet-hook",
        "name": "Magnet Hook",
        "effect": "Reels you one place up the road.",
        "rarity": "common",
        "power": 1,
    },
]

# Rubber-banding: draw weights per position tier. The back of the field pulls
# strong equalisers (Seeker Orb, Tempest, Comet Boost); the front mostly gets
# defensive or single-place tools — the genre's classic comeback mechanic.
ITEM_TIER_WEIGHTS = {
    "front": {
        "seeker-orb": 1,
        "tempest": 1,
        "comet-boost": 8,
        "static-shield": 20,
        "swap-beam": 10,
        "slick-patch": 30,
        "magnet-hook": 30,
    },
    "mid": {
        "seeker-orb": 6,
        "tempest": 6,
        "comet-boost": 18,
        "static-shield": 18,
        "swap-beam": 16,
        "slick-patch": 18,
        "magnet-hook": 18,
    },
    "back": {
        "seeker-orb": 20,
        "tempest": 15,
        "comet-boost": 25,
        "static-shield": 12,
        "swap-beam": 14,
        "slick-patch": 8,
        "magnet-hook": 6,
    },
}

# ── Tracks ───────────────────────────────────────────────────────────
# hazard (1-5) scales lap-to-lap chaos; boost_pad_density (0-1) scales the
# chance of catching a boost-pad chain each lap.
TRACKS = [
    {
        "id": "prism-parkway",
        "name": "Prism Parkway",
        "laps": 3,
        "hazard": 4,
        "boost_pad_density": 0.9,
        "color": "#B07CFF",
        "character": "A glass road refracted across the sky — no guardrails, all rainbow.",
    },
    {
        "id": "molten-keep",
        "name": "Molten Keep",
        "laps": 4,
        "hazard": 5,
        "boost_pad_density": 0.4,
        "color": "#FF7F2A",
        "character": "A lava-flooded castle where the drawbridge is optional and so is survival.",
    },
    {
        "id": "sundae-speedway",
        "name": "Sundae Speedway",
        "laps": 5,
        "hazard": 2,
        "boost_pad_density": 0.7,
        "color": "#FF9EC4",
        "character": "A banked oval of fudge and sprinkles. Watch the cherry chicane.",
    },
    {
        "id": "haunted-manor-loop",
        "name": "Haunted Manor Loop",
        "laps": 4,
        "hazard": 4,
        "boost_pad_density": 0.3,
        "color": "#8FE38F",
        "character": "Candle-lit corridors, a ballroom hairpin, and doors that choose sides.",
    },
    {
        "id": "cloudline-circuit",
        "name": "Cloudline Circuit",
        "laps": 3,
        "hazard": 3,
        "boost_pad_density": 0.8,
        "color": "#7ED4FF",
        "character": "Gondola cables and cumulus banking high above the weather.",
    },
    {
        "id": "jungle-falls",
        "name": "Jungle Falls",
        "laps": 4,
        "hazard": 3,
        "boost_pad_density": 0.5,
        "color": "#35C46B",
        "character": "Waterfall switchbacks behind the cascade — grip is a rumour.",
    },
    {
        "id": "neon-harbor",
        "name": "Neon Harbor",
        "laps": 4,
        "hazard": 2,
        "boost_pad_density": 0.6,
        "color": "#35E0C8",
        "character": "A midnight dockside street circuit lit entirely by signage.",
    },
    {
        "id": "glacier-run",
        "name": "Glacier Run",
        "laps": 3,
        "hazard": 3,
        "boost_pad_density": 0.5,
        "color": "#A9C9FF",
        "character": "A bobsled chute carved through blue ice. Braking is theoretical.",
    },
]

# ── Cups ─────────────────────────────────────────────────────────────
# 4 cups x 4 races; each of the 8 circuits hosts twice a season.
CUPS = [
    {
        "id": "aurora",
        "name": "Aurora Cup",
        "tracks": ["prism-parkway", "cloudline-circuit", "glacier-run", "sundae-speedway"],
    },
    {
        "id": "ember",
        "name": "Ember Cup",
        "tracks": ["molten-keep", "jungle-falls", "neon-harbor", "haunted-manor-loop"],
    },
    {
        "id": "tide",
        "name": "Tide Cup",
        "tracks": ["neon-harbor", "jungle-falls", "glacier-run", "prism-parkway"],
    },
    {
        "id": "zephyr",
        "name": "Zephyr Cup",
        "tracks": ["cloudline-circuit", "sundae-speedway", "haunted-manor-loop", "molten-keep"],
    },
]

DISCLAIMER = (
    "A fan-made fictional league. All characters, items, tracks and results are "
    "simulated and original. Not affiliated with any video game company."
)
