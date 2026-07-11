"""League configuration — the roster, the venues, the season.

Everything in this file is invented for the Chrome Valley Racing League.
The characters are genre archetypes (the cocky rookie, the retired champion
turned mentor, the tow truck everybody loves...) with original names, towns
and liveries. Personality traits are 0-100 and drive the simulator:

* ``grit``        — resilience on rough, chaotic surfaces; shrugs off contact.
* ``showboat``    — plays to the crowd; fast hands, terrible judgement while
                    leading late in a race.
* ``consistency`` — lap-to-lap repeatability and clean pit work.
* ``heart``       — finds something extra in the final laps.

``base_pace`` (0-100) is raw one-lap speed before personality gets involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LEAGUE_NAME = "Chrome Valley Racing League"
TROPHY_NAME = "The Copper Canyon Cup"
SEASON_NAME = "Copper Canyon Cup — Season One"
TAGLINE = "Twelve racers. Ten towns. One cup nobody in the valley will stop talking about."
DISCLAIMER = (
    "A fan-made fictional league. All characters, venues and results are "
    "simulated and original. Not affiliated with any film studio."
)

DEFAULT_SEED = 7

# Classification points, P1 -> P12. Everyone who starts is classified.
POINTS = (30, 24, 20, 17, 14, 12, 10, 8, 6, 4, 2, 1)


@dataclass(frozen=True)
class Character:
    slug: str
    name: str
    number: int
    car: str
    hometown: str
    role: str
    bio: str
    color: str
    grit: int
    showboat: int
    consistency: int
    heart: int
    base_pace: float
    # Venue-tag pace bonuses, e.g. {"night": 4.0} — home-turf specialists.
    affinity: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Venue:
    slug: str
    name: str
    kind: str
    tags: tuple[str, ...]
    laps: int
    chaos: float  # 0-1: how rough/unpredictable the surface and traffic are
    pit_drama: float  # 0-1: how easily a pit stop goes sideways here
    night: bool
    blurb: str


CHARACTERS: tuple[Character, ...] = (
    Character(
        slug="dash-calloway",
        name="Dash Calloway",
        number=7,
        car="flame-orange stock car",
        hometown="Ember Flats",
        role="Rookie hotshot",
        bio="Fastest thing the valley has seen in years, and he will absolutely tell you so.",
        color="#E8792B",
        grit=55,
        showboat=92,
        consistency=40,
        heart=60,
        base_pace=93.0,
    ),
    Character(
        slug="silas-merriweather",
        name="Silas Merriweather",
        number=3,
        car="midnight-blue '51 fastback",
        hometown="Chrome Valley",
        role="Retired champion, mentor",
        bio="Three-time cup winner who came back to teach, not to prove anything. Mostly.",
        color="#2C4E9E",
        grit=90,
        showboat=10,
        consistency=92,
        heart=85,
        base_pace=78.0,
    ),
    Character(
        slug="hitch-barlow",
        name="Hitch Barlow",
        number=88,
        car="sun-bleached tow truck",
        hometown="Chrome Valley",
        role="Tow-truck sidekick",
        bio="Has never won a race. Has towed everyone who has. The valley's favorite by a mile.",
        color="#A9713B",
        grit=80,
        showboat=25,
        consistency=70,
        heart=98,
        base_pace=55.0,
    ),
    Character(
        slug="sterling-voss",
        name="Sterling Voss",
        number=1,
        car="champagne-silver grand tourer",
        hometown="Marquee City",
        role="Smooth veteran rival",
        bio="Reigning number one. Wins quietly, smiles for the cameras, remembers everything.",
        color="#C0C6CE",
        grit=70,
        showboat=45,
        consistency=88,
        heart=35,
        base_pace=91.0,
    ),
    Character(
        slug="june-alvarado",
        name="June Alvarado",
        number=22,
        car="sky-blue roadster",
        hometown="Chrome Valley",
        role="Small-town sweetheart",
        bio="Runs the valley diner on weekdays and the fastest final stint in town on Sundays.",
        color="#6FB7E8",
        grit=75,
        showboat=20,
        consistency=80,
        heart=90,
        base_pace=84.0,
    ),
    Character(
        slug="bianca-torelli",
        name="Bianca Torelli",
        number=96,
        car="scarlet hillclimb exotic",
        hometown="Lido Piccolo",
        role="Glamorous showstopper",
        bio="Flew in from the coast with three trophies and a lighting crew. The crowd adores her.",
        color="#C22E3D",
        grit=50,
        showboat=85,
        consistency=55,
        heart=45,
        base_pace=88.0,
    ),
    Character(
        slug="otis-boone",
        name="Otis Boone",
        number=54,
        car="coal-black diesel pickup",
        hometown="Gravel Notch",
        role="Grizzled workhorse",
        bio="Slow in a straight line, unstoppable when the track tries to eat everyone else.",
        color="#4A4A4A",
        grit=95,
        showboat=15,
        consistency=75,
        heart=70,
        base_pace=74.0,
        affinity={"dirt": 1.5},
    ),
    Character(
        slug="marisol-fuentes",
        name="Marisol Fuentes",
        number=17,
        car="turquoise canyon coupe",
        hometown="Vista del Cobre",
        role="Canyon carver",
        bio="Learned to drive on switchbacks with no guardrails. Canyons feel like home.",
        color="#22A093",
        grit=80,
        showboat=35,
        consistency=72,
        heart=88,
        base_pace=86.0,
        affinity={"canyon": 3.0},
    ),
    Character(
        slug="percy-beaumont",
        name="Percy Beaumont III",
        number=100,
        car="pearl-white luxury sedan",
        hometown="Marquee City",
        role="Pampered heir",
        bio="Entered the league on a dare. Keeps entering because losing to farm trucks stings.",
        color="#E7E3D6",
        grit=30,
        showboat=70,
        consistency=60,
        heart=25,
        base_pace=82.0,
    ),
    Character(
        slug="cactus-jack-prewitt",
        name="Cactus Jack Prewitt",
        number=41,
        car="sand-scarred baja rig",
        hometown="Rattlebox",
        role="Desert wildman",
        bio="Half racer, half rumor. Nobody knows where he sleeps; everybody knows his dust cloud.",
        color="#C9A227",
        grit=88,
        showboat=60,
        consistency=50,
        heart=65,
        base_pace=80.0,
        affinity={"dirt": 2.5},
    ),
    Character(
        slug="nova-okafor",
        name="Nova Okafor",
        number=9,
        car="violet electric coupe",
        hometown="Neon Mesa",
        role="Night-race specialist",
        bio="Silent as a shadow and twice as quick once the sun goes down and the neon comes on.",
        color="#8A5CF6",
        grit=60,
        showboat=55,
        consistency=78,
        heart=72,
        base_pace=87.0,
        affinity={"night": 4.0},
    ),
    Character(
        slug="ferris-dunlap",
        name="Ferris Dunlap",
        number=63,
        car="mint-green delivery wagon",
        hometown="Old Route Junction",
        role="Steady journeyman",
        bio="Delivered parcels on these roads for twenty years. Knows every pothole personally.",
        color="#7BC47F",
        grit=65,
        showboat=30,
        consistency=85,
        heart=58,
        base_pace=76.0,
    ),
)

VENUES: tuple[Venue, ...] = (
    Venue(
        slug="chrome-valley-speedbowl",
        name="Chrome Valley Speedbowl",
        kind="Dusty oval",
        tags=("oval", "dust"),
        laps=60,
        chaos=0.35,
        pit_drama=0.40,
        night=False,
        blurb="The league's front porch — a red-dirt bowl where the whole valley fits in the bleachers.",
    ),
    Venue(
        slug="rattlebox-rim",
        name="Rattlebox Rim",
        kind="Canyon road course",
        tags=("canyon", "road"),
        laps=34,
        chaos=0.55,
        pit_drama=0.35,
        night=False,
        blurb="Fourteen switchbacks carved into sandstone, with a drop you try not to look at.",
    ),
    Venue(
        slug="sandpiper-shores",
        name="Sandpiper Shores Beach Sprint",
        kind="Beach sprint",
        tags=("beach", "dust"),
        laps=24,
        chaos=0.70,
        pit_drama=0.50,
        night=False,
        blurb="Low tide, soft sand, seagulls with no respect for the racing line.",
    ),
    Venue(
        slug="copper-canyon-cutoff",
        name="Copper Canyon Cutoff",
        kind="Canyon road course",
        tags=("canyon", "road"),
        laps=30,
        chaos=0.60,
        pit_drama=0.35,
        night=False,
        blurb="The old mining shortcut that gave the cup its name. Narrow, copper-red and mean.",
    ),
    Venue(
        slug="marquee-city-grand-loop",
        name="Marquee City Grand Loop",
        kind="Street circuit",
        tags=("street", "road"),
        laps=45,
        chaos=0.50,
        pit_drama=0.45,
        night=False,
        blurb="Big-city lights and manhole covers. The valley folk call it 'enemy territory'.",
    ),
    Venue(
        slug="gravel-notch-grind",
        name="Gravel Notch Grind",
        kind="Dirt oval",
        tags=("oval", "dirt", "dust"),
        laps=55,
        chaos=0.65,
        pit_drama=0.40,
        night=False,
        blurb="Otis Boone's backyard. Half racetrack, half quarry, all elbows.",
    ),
    Venue(
        slug="salt-pan-superoval",
        name="Salt Pan Superoval",
        kind="Salt-flat superspeedway",
        tags=("oval", "flatout"),
        laps=70,
        chaos=0.30,
        pit_drama=0.35,
        night=False,
        blurb="White horizon, foot flat, mirrors full. The fastest place in three counties.",
    ),
    Venue(
        slug="ponderosa-pass",
        name="Ponderosa Pass Hillclimb Loop",
        kind="Mountain road course",
        tags=("canyon", "road", "mountain"),
        laps=28,
        chaos=0.60,
        pit_drama=0.35,
        night=False,
        blurb="Pine shade, thin air and a summit hairpin that has humbled every champion since.",
    ),
    Venue(
        slug="neon-mesa-nights",
        name="Neon Mesa Nights",
        kind="Night oval under neon",
        tags=("oval", "night"),
        laps=50,
        chaos=0.45,
        pit_drama=0.40,
        night=True,
        blurb="Every diner sign in the mesa points at turn one. Racing after dark, valley style.",
    ),
    Venue(
        slug="thunderhead-basin",
        name="Thunderhead Basin Finale",
        kind="Dusty oval",
        tags=("oval", "dust", "storm"),
        laps=65,
        chaos=0.50,
        pit_drama=0.45,
        night=False,
        blurb="Storm country. The season ends where the lightning starts.",
    ),
)

# The season calendar is one visit to each venue, in order.
ROUNDS: tuple[str, ...] = tuple(v.slug for v in VENUES)

# Mentorships: rookie slug -> mentor slug. The mentor's coaching raises the
# rookie's pace (and settles their showboating a little) as the season goes on.
MENTORSHIPS: dict[str, str] = {
    "dash-calloway": "silas-merriweather",
}

# Rivalries: whoever finishes ahead carries momentum into the next round.
RIVALRIES: tuple[tuple[str, str], ...] = (
    ("dash-calloway", "sterling-voss"),
    ("bianca-torelli", "nova-okafor"),
)


def character_by_slug(slug: str) -> Character:
    for character in CHARACTERS:
        if character.slug == slug:
            return character
    raise KeyError(slug)


def venue_by_slug(slug: str) -> Venue:
    for venue in VENUES:
        if venue.slug == slug:
            return venue
    raise KeyError(slug)
