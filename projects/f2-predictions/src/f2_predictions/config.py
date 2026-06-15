"""F2-specific configuration: calendar, roster, teams, and points systems.

F2 runs on F1 weekends at shared circuits with a two-race format (Saturday
sprint + Sunday feature). This module is the only F2-domain knowledge the
project carries; everything else is reused from motorsport-core / motorsport-data.

Results data: F2 is not served by Jolpica/Ergast and FastF1's F2 coverage is
partial, so until a live feed is wired (see ``datasource.py``) the project runs
on a **reproducible latent-pace model** (`_TRUTH_PACE`) that generates
deterministic, realistic results. This keeps the full pipeline functional and
testable end-to-end; the predictor never sees `_TRUTH_PACE` — it estimates pace
from prior results only (leakage-safe).
"""
from __future__ import annotations

from motorsport_data.schema import Team, Venue

SPORT = "Formula 2"
SEASON = 2026

# --------------------------------------------------------------------------- #
# Calendar — shared F1 circuits used as F2 support rounds.
# --------------------------------------------------------------------------- #
CALENDAR: list[Venue] = [
    Venue(key="sakhir", name="Bahrain", country="Bahrain"),
    Venue(key="jeddah", name="Saudi Arabia", country="Saudi Arabia"),
    Venue(key="melbourne", name="Australia", country="Australia"),
    Venue(key="imola", name="Emilia-Romagna", country="Italy"),
    Venue(key="monaco", name="Monaco", country="Monaco"),
    Venue(key="catalunya", name="Spain", country="Spain"),
    Venue(key="spielberg", name="Austria", country="Austria"),
    Venue(key="silverstone", name="Great Britain", country="United Kingdom"),
    Venue(key="hungaroring", name="Hungary", country="Hungary"),
    Venue(key="spa", name="Belgium", country="Belgium"),
    Venue(key="monza", name="Italy", country="Italy"),
    Venue(key="baku", name="Azerbaijan", country="Azerbaijan"),
    Venue(key="yas-marina", name="Abu Dhabi", country="UAE"),
]

# How many rounds are "in the books" — the rest are upcoming (predicted).
COMPLETED_ROUNDS = 7

# --------------------------------------------------------------------------- #
# Teams (constructor-equivalent).
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="ART Grand Prix", color="#3B3B3B"),
    Team(name="Prema Racing", color="#E2001A"),
    Team(name="MP Motorsport", color="#F47C20"),
    Team(name="DAMS", color="#0090D0"),
    Team(name="Campos Racing", color="#1F3A93"),
    Team(name="Invicta Racing", color="#8E44AD"),
    Team(name="Hitech", color="#101820"),
    Team(name="Rodin Motorsport", color="#00A19A"),
    Team(name="Van Amersfoort Racing", color="#FF5A00"),
    Team(name="Trident", color="#0050A0"),
    Team(name="AIX Racing", color="#C0392B"),
]

# --------------------------------------------------------------------------- #
# Driver roster — code, full name, team. Two per team (22-car grid).
# --------------------------------------------------------------------------- #
# (code, name, team, latent_pace)  — lower latent_pace = faster (seconds proxy).
_ROSTER: list[tuple[str, str, str, float]] = [
    ("MAR", "Andrea Kimi Antonelli", "Prema Racing", 89.20),
    ("HAD", "Isack Hadjar", "Campos Racing", 89.35),
    ("BOR", "Gabriel Bortoleto", "Invicta Racing", 89.28),
    ("MAI", "Zane Maloney", "Rodin Motorsport", 89.55),
    ("CRA", "Jak Crawford", "DAMS", 89.60),
    ("ARO", "Paul Aron", "Hitech", 89.62),
    ("VES", "Richard Verschoor", "Trident", 89.70),
    ("HAU", "Roman Stanek", "Trident", 89.95),
    ("FOR", "Oliver Goethe", "MP Motorsport", 89.75),
    ("VID", "Dennis Hauger", "MP Motorsport", 89.50),
    ("COR", "Joshua Duerksen", "AIX Racing", 90.10),
    ("BEN", "Amaury Cordeel", "Hitech", 90.20),
    ("MAS", "Pepe Marti", "Campos Racing", 89.85),
    ("FIT", "Kush Maini", "DAMS", 89.90),
    ("LEC", "Enzo Fittipaldi", "Van Amersfoort Racing", 90.05),
    ("BRO", "Taylor Barnard", "AIX Racing", 89.80),
    ("STA", "Victor Martins", "ART Grand Prix", 89.45),
    ("NAK", "Sami Meguetounif", "ART Grand Prix", 90.15),
    ("VAR", "Ritomo Miyata", "Rodin Motorsport", 90.25),
    ("COL", "Franco Colapinto", "Van Amersfoort Racing", 89.65),
    ("IWA", "Rafael Villagomez", "Invicta Racing", 90.30),
    ("DUR", "John Bennett", "Prema Racing", 90.00),
]

DRIVERS: list[dict[str, str]] = [
    {"code": c, "name": n, "team": t} for (c, n, t, _) in _ROSTER
]
TEAM_OF: dict[str, str] = {c: t for (c, _, t, _) in _ROSTER}
DRIVER_NAME: dict[str, str] = {c: n for (c, n, _, _) in _ROSTER}

# Latent pace — used ONLY by the synthetic results generator, never the predictor.
_TRUTH_PACE: dict[str, float] = {c: p for (c, _, _, p) in _ROSTER}

# --------------------------------------------------------------------------- #
# Points systems (standard F2).
# --------------------------------------------------------------------------- #
FEATURE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
SPRINT_POINTS = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
POLE_POINTS = 2          # feature-race pole
FASTEST_LAP_POINTS = 1   # if classified in the top 10
