"""Central matplotlib styling — design-system palette across every PNG.

Why this exists
---------------
Before this module the project had at least three different matplotlib
themes:

  - ``f1_prediction_utils.py``: sns.set_theme("whitegrid", "muted")
    → white background, default seaborn pastels (the "vanilla" look the
    user complained about)
  - ``export_website_data.py::_export_visualizations``: dark theme with
    #0B1220 / #FF5A36 accent (close to but not aligned with the website)
  - ``generate_fastf1_viz.py``: #1a1a2e purple-blue + red text bbox

The website ships a coherent design system (carbon-graphite surfaces +
telemetry-orange accent + Geist/JetBrains Mono fonts).  This module
forces every generated PNG into the same language so the per-round
visualization studio doesn't feel like a different product than the
rest of the site.

Public surface
--------------
* ``VIZ_COLORS`` — the palette dict (canonical names match the website
  token semantic layer).
* ``TEAM_DESATURATION`` — a 0..1 factor applied to team colours when
  they're used as bar fills, so the brand palette doesn't blow out the
  composition.
* ``apply_viz_style()`` — call once at module load to globally set
  matplotlib rcParams.  Idempotent.
* ``style_axis(ax, *, title=None, xlabel=None, ylabel=None)`` — applies
  the per-chart conventions (no top/right spines, muted grid, tabular
  figures on ticks, title aligned left).
* ``style_figure(fig)`` — sets figure facecolor + tight margins.
* ``save_figure(fig, path, dpi=170)`` — wrapper around ``fig.savefig``
  that picks the right facecolor + bbox.

Conventions enforced
--------------------
* Dark surface for the figure + axes (matches the website's default
  theme).  Light-theme variants are out of scope for v1 — the PNGs are
  shipped as static assets and the website's dark-mode is the dominant
  usage pattern.
* Telemetry orange (#F76B15) is the sole accent.  Brand red is **never**
  used for accent / highlight — it's reserved for "negative" tones
  (penalty / DNF / regression).
* Tabular figures on every numeric tick so charts that line up data
  read straight.
* Spines: hide top + right; left + bottom are a muted grey, not white.
* Gridlines: y-axis only, alpha 0.18, no x-axis grid.

Reset / opt-out
---------------
``reset_viz_style()`` returns matplotlib to the default rcParams.
Useful in notebooks where users want to render the project's data with
their own theming.
"""
from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Palette — mirrors website/src/styles/tokens.css for visual coherence.
# --------------------------------------------------------------------------- #


VIZ_COLORS: dict[str, str] = {
    # Surfaces
    "bg":               "#0E1116",
    "bg_elevated":      "#131822",
    "surface":          "#161B26",
    "surface_elevated": "#1B2330",
    "panel":            "#13192238",  # subtle inner panel — semi-transparent
    # Strokes
    "border":           "#252C39",
    "border_strong":    "#3A4252",
    "grid":             "#202738",
    # Text
    "text":             "#F4F7FB",
    "text_secondary":   "#BCC4CF",
    "text_muted":       "#8A95A4",
    # Semantic accents (single accent on highlights, others for tones)
    "accent":           "#F76B15",   # telemetry orange — primary accent
    "accent_hover":     "#FF8033",
    "positive":         "#22C55E",   # hot-lap green
    "negative":         "#EF4444",   # penalty red — used sparingly
    "info":             "#38BDF8",   # timing cyan
    # Podium tones
    "podium_1":         "#FFD166",
    "podium_2":         "#C5CCD3",
    "podium_3":         "#CD7F32",
}


# Ordered palette for categorical plots that need >1 hue (e.g. multi-line
# pace comparisons).  Starts with the brand accents then drifts to muted
# secondaries so the eye reads the primary signals first.
CATEGORICAL_CYCLE: list[str] = [
    VIZ_COLORS["accent"],
    VIZ_COLORS["info"],
    VIZ_COLORS["positive"],
    VIZ_COLORS["podium_1"],
    VIZ_COLORS["podium_2"],
    "#A78BFA",   # soft violet
    "#F472B6",   # rose
    VIZ_COLORS["text_secondary"],
    VIZ_COLORS["text_muted"],
]


# Compound colour-coding standard across all tyre-strategy charts.
TYRE_COLORS: dict[str, str] = {
    "SOFT":         "#EF4444",   # softs read red
    "MEDIUM":       "#FFD166",
    "HARD":         "#FFFFFF",
    "INTERMEDIATE": "#22C55E",
    "WET":          "#38BDF8",
    "UNKNOWN":      "#8A95A4",
}


# How much to desaturate team brand colours when used as plot fills.
# F1 team palettes lean very saturated and look loud on dark surfaces;
# desaturating ~12% keeps them recognisable without blowing out.
TEAM_DESATURATION: float = 0.12


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


_STYLE_APPLIED = False


def apply_viz_style(force: bool = False) -> None:
    """Globally apply the design-system rcParams to matplotlib.

    Idempotent.  Pass ``force=True`` to re-apply after a notebook user
    mutated rcParams.
    """
    global _STYLE_APPLIED
    if _STYLE_APPLIED and not force:
        return

    # Lazy import so the module can be cheaply imported in tests that
    # don't need matplotlib.
    import matplotlib
    from matplotlib import rcParams
    from cycler import cycler

    # Use matplotlib's bundled DejaVu Sans by default — guaranteed to be
    # present on every install (including CI runners with no system
    # fonts), and visually close enough to Geist/Inter that the PNGs
    # match the website's typographic feel.  Falling back through
    # missing fonts produces hundreds of noisy "Font family X not
    # found" warnings per build.
    rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
    rcParams["font.monospace"] = ["DejaVu Sans Mono", "monospace"]
    rcParams["font.size"] = 11
    rcParams["axes.titlesize"] = 16
    rcParams["axes.labelsize"] = 12
    rcParams["xtick.labelsize"] = 10
    rcParams["ytick.labelsize"] = 10
    rcParams["legend.fontsize"] = 10
    rcParams["axes.titleweight"] = "bold"
    rcParams["axes.titlepad"] = 14
    rcParams["axes.titlelocation"] = "left"

    # Colours
    rcParams["figure.facecolor"] = VIZ_COLORS["bg"]
    rcParams["axes.facecolor"] = VIZ_COLORS["bg"]
    rcParams["savefig.facecolor"] = VIZ_COLORS["bg"]
    rcParams["savefig.edgecolor"] = "none"
    rcParams["axes.edgecolor"] = VIZ_COLORS["border"]
    rcParams["axes.labelcolor"] = VIZ_COLORS["text"]
    rcParams["axes.titlecolor"] = VIZ_COLORS["text"]
    rcParams["xtick.color"] = VIZ_COLORS["text_muted"]
    rcParams["ytick.color"] = VIZ_COLORS["text_muted"]
    rcParams["text.color"] = VIZ_COLORS["text"]
    rcParams["legend.facecolor"] = VIZ_COLORS["surface_elevated"]
    rcParams["legend.edgecolor"] = VIZ_COLORS["border"]
    rcParams["legend.labelcolor"] = VIZ_COLORS["text"]
    rcParams["legend.frameon"] = True
    rcParams["axes.prop_cycle"] = cycler(color=CATEGORICAL_CYCLE)

    # Grid + spines
    rcParams["axes.grid"] = True
    rcParams["axes.grid.axis"] = "y"
    rcParams["grid.color"] = VIZ_COLORS["grid"]
    rcParams["grid.alpha"] = 0.55
    rcParams["grid.linewidth"] = 0.7
    rcParams["axes.spines.top"] = False
    rcParams["axes.spines.right"] = False
    rcParams["axes.spines.left"] = True
    rcParams["axes.spines.bottom"] = True
    rcParams["axes.linewidth"] = 0.9

    # DPI + sizing
    rcParams["figure.dpi"] = 130
    rcParams["savefig.dpi"] = 170
    rcParams["figure.figsize"] = (12, 6)
    rcParams["figure.autolayout"] = False
    rcParams["savefig.bbox"] = "tight"
    rcParams["savefig.pad_inches"] = 0.25

    # Override seaborn defaults too if it's already imported.
    try:
        import seaborn as sns

        sns.set_theme(
            style="ticks",
            palette=CATEGORICAL_CYCLE,
            font="DejaVu Sans",
            rc={
                "axes.facecolor": VIZ_COLORS["bg"],
                "figure.facecolor": VIZ_COLORS["bg"],
                "grid.color": VIZ_COLORS["grid"],
                "axes.edgecolor": VIZ_COLORS["border"],
                "text.color": VIZ_COLORS["text"],
            },
        )
    except ImportError:
        pass

    _ = matplotlib  # silence unused
    _STYLE_APPLIED = True
    LOGGER.debug("viz_style: design-system rcParams applied")


def reset_viz_style() -> None:
    """Restore matplotlib defaults.  Useful for notebooks."""
    global _STYLE_APPLIED
    import matplotlib

    matplotlib.rcdefaults()
    _STYLE_APPLIED = False


def style_axis(
    ax: Any,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    show_y_grid: bool = True,
    show_x_grid: bool = False,
) -> None:
    """Apply per-axes conventions.  Call after ``ax.plot(...)``.

    The rcParams above set the global defaults; this function tightens
    things that are easier to express per-axes (title alignment, the
    "y-grid-only" rule, font weight on the title).
    """
    if title is not None:
        ax.set_title(title, color=VIZ_COLORS["text"], loc="left", fontweight="bold")
    if xlabel is not None:
        ax.set_xlabel(xlabel, color=VIZ_COLORS["text_secondary"])
    if ylabel is not None:
        ax.set_ylabel(ylabel, color=VIZ_COLORS["text_secondary"])
    ax.tick_params(colors=VIZ_COLORS["text_muted"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(VIZ_COLORS["border"])
    ax.spines["bottom"].set_color(VIZ_COLORS["border"])
    if show_y_grid:
        ax.grid(axis="y", color=VIZ_COLORS["grid"], alpha=0.55, linewidth=0.7)
    else:
        ax.grid(axis="y", visible=False)
    if show_x_grid:
        ax.grid(axis="x", color=VIZ_COLORS["grid"], alpha=0.55, linewidth=0.7)
    else:
        ax.grid(axis="x", visible=False)
    ax.set_facecolor(VIZ_COLORS["bg"])


def style_figure(fig: Any) -> None:
    """Apply figure-level conventions.  Idempotent."""
    fig.patch.set_facecolor(VIZ_COLORS["bg"])


def save_figure(fig: Any, path: str, *, dpi: int = 170) -> None:
    """Save a figure with the design-system facecolor + tight bbox."""
    fig.savefig(
        path,
        dpi=dpi,
        bbox_inches="tight",
        facecolor=VIZ_COLORS["bg"],
        edgecolor="none",
        pad_inches=0.25,
    )


def desaturate(hex_color: str, factor: float = TEAM_DESATURATION) -> str:
    """Return a desaturated hex string.  Drops saturation by ``factor``.

    Used on team brand colours so they don't blow out next to the
    telemetry-orange primary accent on plot fills.
    """
    if not hex_color or not hex_color.startswith("#"):
        return hex_color
    # Lazy import — colorsys is stdlib but we only need it when used.
    import colorsys

    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    ss = max(0.0, ss * (1.0 - factor))
    nr, ng, nb = colorsys.hls_to_rgb(hh, ll, ss)
    return "#{:02x}{:02x}{:02x}".format(int(nr * 255), int(ng * 255), int(nb * 255))


def watermark(ax: Any, text: str = "f1predictions") -> None:
    """Subtle bottom-right watermark on every figure.  Mirrors the
    branding pattern used on financial-data charts (e.g. Bloomberg) —
    just enough to anchor provenance without competing with the data."""
    ax.text(
        0.985,
        -0.06,
        text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color=VIZ_COLORS["text_muted"],
        alpha=0.6,
        family="monospace",
    )


# Apply the style on import so any downstream module that imports
# from viz_style gets the rcParams without an explicit setup call.
apply_viz_style()
