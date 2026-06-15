#!/usr/bin/env python3
"""Generate the MotorsportVerse / RaceIQ logo system as SVGs.

One generator = one design language. Every series logo shares:
  * common typography      — a geometric uppercase wordmark, fixed weight + tracking
  * common technology motif — a telemetry "tick" baseline under the wordmark
  * common motorsport DNA   — a forward "speed chevron" mark
  * a unique accent color   — per series

Outputs (under website/public/brand/):
  * mark only (square):   sports/<key>.svg          (registry catalog icons)
  * horizontal lockup:    series/raceiq-<key>.svg   (RaceIQ <Series> wordmark)
  * ecosystem lockup:     logo.svg, mark.svg, favicon.svg, ../og/default.svg

Re-run after changing the SERIES table; the SVGs are committed artifacts so the
website + README don't need a build step to show them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "website" / "public" / "brand"
OG = ROOT / "website" / "public" / "og"

FONT = "'Saira Condensed', 'Arial Narrow', system-ui, sans-serif"
INK = "#f4f5f7"
CANVAS = "#0a0b0d"


@dataclass(frozen=True)
class Series:
    key: str          # registry slug-stem / icon filename
    label: str        # series label shown after "RaceIQ"
    accent: str       # unique accent color
    abbr: str         # short mark glyph text


# The 8 named series in the branding brief + the remaining catalog entries,
# all on the same system so every catalog icon is coherent.
SERIES: tuple[Series, ...] = (
    Series("f1", "F1", "#E10600", "F1"),
    Series("f2", "F2", "#1E9BD7", "F2"),
    Series("f3", "F3", "#9AA7B4", "F3"),
    Series("formula-e", "Formula E", "#18C8B6", "FE"),
    Series("indycar", "Indy", "#2E6BE6", "IND"),
    Series("nascar", "NASCAR", "#F2B705", "NAS"),
    Series("wec", "WEC", "#B5179E", "WEC"),
    Series("wrc", "Rally", "#E2571E", "WRC"),
    # remaining catalog entries (same system, for icon coherence)
    Series("lemans", "Le Mans", "#1A8F4C", "LM"),
    Series("imsa", "IMSA", "#3457D5", "IMSA"),
    Series("motogp", "MotoGP", "#CC0033", "MGP"),
)

ECOSYSTEM_ACCENT = "#38e1c6"


def _speed_chevron(x: float, y: float, size: float, color: str) -> str:
    """Forward-leaning double chevron — the shared motorsport DNA mark."""
    s = size
    return (
        f'<g transform="translate({x},{y})" fill="{color}">'
        f'<path d="M0 0 L{0.42*s} 0 L{0.72*s} {0.5*s} L{0.42*s} {s} L0 {s} '
        f'L{0.30*s} {0.5*s} Z"/>'
        f'<path d="M{0.40*s} 0 L{0.82*s} 0 L{1.12*s} {0.5*s} L{0.82*s} {s} '
        f'L{0.40*s} {s} L{0.70*s} {0.5*s} Z" opacity="0.55"/>'
        f"</g>"
    )


def _tick_baseline(x: float, y: float, width: float, color: str) -> str:
    """Telemetry tick row — the shared technology motif."""
    ticks = []
    n = 18
    step = width / n
    for i in range(n + 1):
        h = 6 if i % 3 == 0 else 3
        ticks.append(
            f'<rect x="{x + i*step:.1f}" y="{y - h}" width="1.4" height="{h}" '
            f'fill="{color}" opacity="{0.9 if i % 3 == 0 else 0.4}"/>'
        )
    return "".join(ticks)


def mark_svg(s: Series) -> str:
    """Square mark for catalog icons + favicons."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="RaceIQ {s.label} mark">
  <rect width="64" height="64" rx="14" fill="{CANVAS}"/>
  <rect width="64" height="64" rx="14" fill="none" stroke="{s.accent}" stroke-opacity="0.35" stroke-width="1.5"/>
  {_speed_chevron(16, 16, 32, s.accent)}
  <rect x="14" y="50" width="36" height="2" rx="1" fill="{s.accent}" opacity="0.5"/>
</svg>
"""


def lockup_svg(s: Series) -> str:
    """Horizontal RaceIQ <Series> lockup."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 80" role="img" aria-label="RaceIQ {s.label}">
  <rect width="340" height="80" rx="0" fill="none"/>
  {_speed_chevron(8, 22, 36, s.accent)}
  <g font-family="{FONT}" font-weight="700">
    <text x="64" y="46" font-size="34" letter-spacing="1.5" fill="{INK}">Race<tspan fill="{s.accent}">IQ</tspan></text>
    <text x="66" y="66" font-size="15" letter-spacing="4" fill="{s.accent}">{s.label.upper()}</text>
  </g>
  {_tick_baseline(180, 60, 150, s.accent)}
</svg>
"""


def ecosystem_lockup() -> str:
    a = ECOSYSTEM_ACCENT
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 80" role="img" aria-label="MotorsportVerse">
  {_speed_chevron(8, 22, 36, a)}
  <g font-family="{FONT}" font-weight="700">
    <text x="64" y="50" font-size="34" letter-spacing="1.2" fill="{INK}">Motorsport<tspan fill="{a}">Verse</tspan></text>
    <text x="66" y="68" font-size="13" letter-spacing="5" fill="{a}">OPEN MOTORSPORT AI ECOSYSTEM</text>
  </g>
</svg>
"""


def ecosystem_mark() -> str:
    a = ECOSYSTEM_ACCENT
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="MotorsportVerse mark">
  <rect width="64" height="64" rx="14" fill="{CANVAS}"/>
  <rect width="64" height="64" rx="14" fill="none" stroke="{a}" stroke-opacity="0.4" stroke-width="1.5"/>
  {_speed_chevron(16, 16, 32, a)}
  <rect x="14" y="50" width="36" height="2" rx="1" fill="{a}" opacity="0.5"/>
</svg>
"""


def og_default() -> str:
    a = ECOSYSTEM_ACCENT
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="{CANVAS}"/>
  {_speed_chevron(90, 250, 130, a)}
  <g font-family="{FONT}" font-weight="700">
    <text x="270" y="345" font-size="82" letter-spacing="2" fill="{INK}">Motorsport<tspan fill="{a}">Verse</tspan></text>
    <text x="272" y="400" font-size="30" letter-spacing="6" fill="{a}">OPEN MOTORSPORT AI ECOSYSTEM</text>
  </g>
  {_tick_baseline(270, 470, 600, a)}
</svg>
"""


def main() -> int:
    (BRAND / "sports").mkdir(parents=True, exist_ok=True)
    (BRAND / "series").mkdir(parents=True, exist_ok=True)
    OG.mkdir(parents=True, exist_ok=True)

    named = {"f1", "f2", "f3", "formula-e", "indycar", "nascar", "wec", "wrc"}
    written = 0
    for s in SERIES:
        (BRAND / "sports" / f"{s.key}.svg").write_text(mark_svg(s))
        written += 1
        if s.key in named:
            (BRAND / "series" / f"raceiq-{s.key}.svg").write_text(lockup_svg(s))
            written += 1

    (BRAND / "logo.svg").write_text(ecosystem_lockup())
    (BRAND / "mark.svg").write_text(ecosystem_mark())
    (BRAND / "favicon.svg").write_text(ecosystem_mark())
    (OG / "default.svg").write_text(og_default())
    written += 4

    print(f"Generated {written} brand SVGs under {BRAND.relative_to(ROOT)} + og/")
    print(f"  marks: {len(SERIES)} · lockups: {len(named)} · ecosystem: 4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
