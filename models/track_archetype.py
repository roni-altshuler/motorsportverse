"""Track archetype classifier for F1 circuits.

Every circuit on the modern calendar is classified along five dimensions
relevant to race-outcome modelling:

* ``overtaking_difficulty``  0 (easy, e.g. Bahrain) → 1 (near-impossible, Monaco)
* ``qualifying_importance``  0 (race-pace dominant) → 1 (quali-locked, Monaco)
* ``tire_deg_sensitivity``   0 (low, cool-night Bahrain) → 1 (high, Spain/Barcelona)
* ``safety_car_probability`` empirical historical rate
* ``street_circuit``         boolean
* ``high_speed``             boolean (avg corner speed proxy)

The combined fingerprint maps onto one of five canonical archetypes:

* ``street_quali_locked`` — Monaco, Singapore (Marina Bay), Baku
* ``power``               — Monza, Spa, Las Vegas (long straights)
* ``balanced``            — Silverstone, COTA, Suzuka
* ``high_deg``            — Spain (Barcelona-Catalunya), Hungary, Qatar
* ``high_variance``       — Bahrain, Saudi, Miami, Canada, Brazil

``get_archetype(name)`` is tolerant to a range of name variants — long form
("Singapore Grand Prix"), short form ("Singapore"), the circuit name ("Marina
Bay"), or the ``gp_key`` used internally by :mod:`f1_prediction_utils`.

Numbers are honest priors drawn from publicly-known circuit characteristics
(track layout reviews, historical Pirelli tyre allocation, FIA safety-car
records). They are NOT fitted — they're the starting point for the
benchmark in :mod:`benchmark_models`. Once enough forward-eval data
accumulates, they can be refined via a small per-circuit hierarchical
model.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Optional


ARCHETYPES: tuple[str, ...] = (
    "street_quali_locked",
    "power",
    "balanced",
    "high_deg",
    "high_variance",
)


@dataclass(frozen=True)
class TrackArchetype:
    """Per-circuit characteristic vector + archetype label."""

    circuit_id: str
    overtaking_difficulty: float
    qualifying_importance: float
    tire_deg_sensitivity: float
    safety_car_probability: float
    street_circuit: bool
    high_speed: bool
    archetype: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:  # pragma: no cover - dataclass internals
        for name in (
            "overtaking_difficulty",
            "qualifying_importance",
            "tire_deg_sensitivity",
            "safety_car_probability",
        ):
            v = getattr(self, name)
            if not 0.0 <= float(v) <= 1.0:
                raise ValueError(
                    f"{name} must be in [0,1]; got {v!r} for {self.circuit_id}"
                )
        if self.archetype not in ARCHETYPES:
            raise ValueError(
                f"archetype {self.archetype!r} not in known list {ARCHETYPES}"
            )


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_RAW: tuple[TrackArchetype, ...] = (
    TrackArchetype(
        circuit_id="monaco",
        overtaking_difficulty=0.98,
        qualifying_importance=0.95,
        tire_deg_sensitivity=0.25,
        safety_car_probability=0.75,
        street_circuit=True,
        high_speed=False,
        archetype="street_quali_locked",
        aliases=("monaco grand prix", "circuit de monaco", "monte carlo"),
    ),
    TrackArchetype(
        circuit_id="singapore",
        overtaking_difficulty=0.80,
        qualifying_importance=0.85,
        tire_deg_sensitivity=0.45,
        safety_car_probability=0.80,
        street_circuit=True,
        high_speed=False,
        archetype="street_quali_locked",
        aliases=("marina bay", "marina bay street circuit", "singapore grand prix"),
    ),
    TrackArchetype(
        circuit_id="baku",
        overtaking_difficulty=0.45,
        qualifying_importance=0.65,
        tire_deg_sensitivity=0.40,
        safety_car_probability=0.75,
        street_circuit=True,
        high_speed=True,
        archetype="street_quali_locked",
        aliases=("azerbaijan", "baku city circuit", "azerbaijan grand prix"),
    ),
    TrackArchetype(
        circuit_id="hungary",
        overtaking_difficulty=0.85,
        qualifying_importance=0.80,
        tire_deg_sensitivity=0.65,
        safety_car_probability=0.30,
        street_circuit=False,
        high_speed=False,
        archetype="high_deg",
        aliases=("hungaroring", "hungarian grand prix", "budapest"),
    ),
    TrackArchetype(
        circuit_id="spain",
        overtaking_difficulty=0.65,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.85,
        safety_car_probability=0.30,
        street_circuit=False,
        high_speed=False,
        archetype="high_deg",
        aliases=(
            "barcelona",
            "barcelona-catalunya",
            "circuit de barcelona-catalunya",
            "catalunya",
            "spanish grand prix",
        ),
    ),
    TrackArchetype(
        circuit_id="qatar",
        overtaking_difficulty=0.55,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.80,
        safety_car_probability=0.25,
        street_circuit=False,
        high_speed=True,
        archetype="high_deg",
        aliases=("losail", "lusail", "qatar grand prix"),
    ),
    TrackArchetype(
        circuit_id="monza",
        overtaking_difficulty=0.20,
        qualifying_importance=0.35,
        tire_deg_sensitivity=0.40,
        safety_car_probability=0.25,
        street_circuit=False,
        high_speed=True,
        archetype="power",
        aliases=("italy", "italian grand prix", "autodromo nazionale monza"),
    ),
    TrackArchetype(
        circuit_id="spa",
        overtaking_difficulty=0.30,
        qualifying_importance=0.40,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.40,
        street_circuit=False,
        high_speed=True,
        archetype="power",
        aliases=("belgium", "belgian grand prix", "spa-francorchamps", "spa francorchamps"),
    ),
    TrackArchetype(
        circuit_id="las_vegas",
        overtaking_difficulty=0.40,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.35,
        safety_car_probability=0.50,
        street_circuit=True,
        high_speed=True,
        archetype="power",
        aliases=("las vegas grand prix", "vegas", "las vegas strip circuit"),
    ),
    TrackArchetype(
        circuit_id="silverstone",
        overtaking_difficulty=0.40,
        qualifying_importance=0.50,
        tire_deg_sensitivity=0.60,
        safety_car_probability=0.30,
        street_circuit=False,
        high_speed=True,
        archetype="balanced",
        aliases=("great britain", "british grand prix", "british gp"),
    ),
    TrackArchetype(
        circuit_id="cota",
        overtaking_difficulty=0.40,
        qualifying_importance=0.50,
        tire_deg_sensitivity=0.60,
        safety_car_probability=0.35,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=(
            "united states",
            "united states grand prix",
            "us grand prix",
            "circuit of the americas",
            "austin",
        ),
    ),
    TrackArchetype(
        circuit_id="suzuka",
        overtaking_difficulty=0.55,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.65,
        safety_car_probability=0.35,
        street_circuit=False,
        high_speed=True,
        archetype="balanced",
        aliases=("japan", "japanese grand prix", "suzuka international racing course"),
    ),
    TrackArchetype(
        circuit_id="zandvoort",
        overtaking_difficulty=0.70,
        qualifying_importance=0.65,
        tire_deg_sensitivity=0.45,
        safety_car_probability=0.35,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=("netherlands", "dutch grand prix", "circuit zandvoort"),
    ),
    TrackArchetype(
        circuit_id="imola",
        overtaking_difficulty=0.70,
        qualifying_importance=0.65,
        tire_deg_sensitivity=0.50,
        safety_car_probability=0.40,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=(
            "emilia romagna",
            "emilia-romagna",
            "emiliaromagna",
            "emilia romagna grand prix",
            "autodromo enzo e dino ferrari",
        ),
    ),
    TrackArchetype(
        circuit_id="bahrain",
        overtaking_difficulty=0.25,
        qualifying_importance=0.40,
        tire_deg_sensitivity=0.70,
        safety_car_probability=0.40,
        street_circuit=False,
        high_speed=False,
        archetype="high_variance",
        aliases=("bahrain grand prix", "bahrain international circuit", "sakhir"),
    ),
    TrackArchetype(
        circuit_id="saudi",
        overtaking_difficulty=0.45,
        qualifying_importance=0.60,
        tire_deg_sensitivity=0.45,
        safety_car_probability=0.70,
        street_circuit=True,
        high_speed=True,
        archetype="high_variance",
        aliases=(
            "saudi arabia",
            "saudiarabia",
            "saudi arabian grand prix",
            "jeddah",
            "jeddah corniche circuit",
        ),
    ),
    TrackArchetype(
        circuit_id="miami",
        overtaking_difficulty=0.40,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.55,
        street_circuit=True,
        high_speed=False,
        archetype="high_variance",
        aliases=("miami grand prix", "miami international autodrome"),
    ),
    TrackArchetype(
        circuit_id="canada",
        overtaking_difficulty=0.30,
        qualifying_importance=0.50,
        tire_deg_sensitivity=0.50,
        safety_car_probability=0.70,
        street_circuit=False,
        high_speed=True,
        archetype="high_variance",
        aliases=("canadian grand prix", "circuit gilles villeneuve", "montreal"),
    ),
    TrackArchetype(
        circuit_id="brazil",
        overtaking_difficulty=0.30,
        qualifying_importance=0.45,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.55,
        street_circuit=False,
        high_speed=False,
        archetype="high_variance",
        aliases=(
            "sao paulo",
            "são paulo",
            "sao paulo grand prix",
            "são paulo grand prix",
            "brazilian grand prix",
            "interlagos",
            "autodromo jose carlos pace",
        ),
    ),
    TrackArchetype(
        circuit_id="australia",
        overtaking_difficulty=0.50,
        qualifying_importance=0.60,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.65,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=("australian grand prix", "albert park", "melbourne"),
    ),
    TrackArchetype(
        circuit_id="china",
        overtaking_difficulty=0.45,
        qualifying_importance=0.50,
        tire_deg_sensitivity=0.60,
        safety_car_probability=0.45,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=(
            "chinese grand prix",
            "shanghai",
            "shanghai international circuit",
            "shanghai international",
        ),
    ),
    TrackArchetype(
        circuit_id="austria",
        overtaking_difficulty=0.30,
        qualifying_importance=0.45,
        tire_deg_sensitivity=0.65,
        safety_car_probability=0.35,
        street_circuit=False,
        high_speed=True,
        archetype="high_variance",
        aliases=("austrian grand prix", "red bull ring", "spielberg"),
    ),
    TrackArchetype(
        circuit_id="mexico",
        overtaking_difficulty=0.45,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.40,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=(
            "mexico city",
            "mexicocity",
            "mexican grand prix",
            "mexico city grand prix",
            "autodromo hermanos rodriguez",
        ),
    ),
    TrackArchetype(
        circuit_id="abu_dhabi",
        overtaking_difficulty=0.55,
        qualifying_importance=0.65,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.35,
        street_circuit=False,
        high_speed=False,
        archetype="balanced",
        aliases=(
            "abu dhabi grand prix",
            "abudhabi",
            "yas marina",
            "yas marina circuit",
        ),
    ),
    TrackArchetype(
        circuit_id="madrid",
        overtaking_difficulty=0.50,
        qualifying_importance=0.60,
        tire_deg_sensitivity=0.55,
        safety_car_probability=0.55,
        street_circuit=True,
        high_speed=False,
        archetype="street_quali_locked",
        aliases=("madring", "madrid grand prix", "madrid spanish gp"),
    ),
    # Older calendar circuits surfaced by 2023-only entries in history.duckdb
    TrackArchetype(
        circuit_id="paul_ricard",
        overtaking_difficulty=0.55,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.65,
        safety_car_probability=0.20,
        street_circuit=False,
        high_speed=True,
        archetype="balanced",
        aliases=("french grand prix", "france", "paul ricard"),
    ),
    TrackArchetype(
        circuit_id="portimao",
        overtaking_difficulty=0.50,
        qualifying_importance=0.55,
        tire_deg_sensitivity=0.65,
        safety_car_probability=0.25,
        street_circuit=False,
        high_speed=False,
        archetype="high_deg",
        aliases=("portuguese grand prix", "portugal", "algarve"),
    ),
)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _normalise(name: str) -> str:
    s = _strip_accents(name or "")
    return (
        s.strip()
        .lower()
        .replace("grand prix", "")
        .replace("gp", "")
        .replace("'", "")
        .replace(",", "")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def _build_lookup() -> dict[str, TrackArchetype]:
    out: dict[str, TrackArchetype] = {}
    for a in _RAW:
        out[_normalise(a.circuit_id)] = a
        out[_normalise(a.circuit_id.replace("_", " "))] = a
        for alias in a.aliases:
            out[_normalise(alias)] = a
    return out


_LOOKUP: dict[str, TrackArchetype] = _build_lookup()


def get_archetype(name: str) -> Optional[TrackArchetype]:
    """Return the archetype for the given circuit identifier or None.

    Tolerant to common variants: long-form name ("Singapore Grand Prix"),
    short form ("Singapore"), circuit name ("Marina Bay"), or the
    ``gp_key`` field used by ``f1_prediction_utils``. Case-insensitive.
    """
    if name is None:
        return None
    key = _normalise(str(name))
    if not key:
        return None
    # Exact match
    if key in _LOOKUP:
        return _LOOKUP[key]
    # Try collapsing to first significant token (e.g. "monaco grand prix
    # circuit" → "monaco")
    for variant_key, archetype in _LOOKUP.items():
        if variant_key and (key.startswith(variant_key) or variant_key.startswith(key)):
            return archetype
    # Last-chance substring contains check
    for variant_key, archetype in _LOOKUP.items():
        if variant_key and variant_key in key:
            return archetype
    return None


def all_archetypes() -> tuple[TrackArchetype, ...]:
    """Return every seeded archetype (stable order)."""
    return _RAW
