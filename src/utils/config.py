"""
config.py
=========
Single source of truth for every parameter of the EDA pipeline.

WHY A CONFIG MODULE AT ALL (bootcamp defence):
    An EDA is only credible if it is reproducible. Hard-coding tickers, dates or
    colours inside the analysis functions makes the study impossible to re-run
    with a different window ("what happens if we exclude the 2022 bear market?").
    Every knob a reviewer might want to turn lives here and nowhere else.
"""

from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------------- 
# 1. PATHS  (resolved relative to this file, so the pipeline runs from anywhere)
# -----------------------------------------------------------------------------
UTILS_DIR: Path = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR: Path = UTILS_DIR.parent                       # .../src
PROJECT_DIR: Path = SRC_DIR.parent                     # .../my-eda-project

DATA_DIR: Path = SRC_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"                       # untouched API payloads
PROCESSED_DIR: Path = DATA_DIR / "processed"           # analysis-ready tables
REPORTS_DIR: Path = PROJECT_DIR / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"            # 300-DPI presentation PNGs
TABLES_DIR: Path = REPORTS_DIR / "tables"              # markdown summary tables

for _directory in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 2. UNIVERSE UNDER STUDY
# -----------------------------------------------------------------------------
TARGET: str = "ITX.MC"        # Inditex (Zara) - agile near-shoring, BME Madrid
COMPETITOR: str = "PDD"       # PDD Holdings (Temu) - listed proxy for the
                              # privately held Shein ultra-fast model, Nasdaq
BENCHMARK: str = "^IBEX"      # IBEX 35 - Spanish market baseline, BME Madrid

TICKERS: list[str] = [TARGET, COMPETITOR, BENCHMARK]

# Human-readable labels used in every chart title and summary table.
LABELS: dict[str, str] = {
    TARGET: "Inditex (Zara)",
    COMPETITOR: "PDD Holdings (Temu)",
    BENCHMARK: "IBEX 35 (benchmark)",
}

# Tickers that carry a meaningful traded-share volume.
# An *index* such as ^IBEX reports either 0 or a synthetic aggregate, so it is
# deliberately excluded from the liquidity hypothesis (H3).
VOLUME_TICKERS: list[str] = [TARGET, COMPETITOR]

# -----------------------------------------------------------------------------
# 3. STUDY WINDOW
# -----------------------------------------------------------------------------
START_DATE: str = "2021-01-01"
END_DATE: str = "2024-11-01"

# -----------------------------------------------------------------------------
# 4. THE CULTURAL EVENT WINDOW  ("La Temporada de BBC")
# -----------------------------------------------------------------------------
# Bodas, Bautizos y Comuniones: the Spanish spring social season. April to June
# is when the "coleccion de invitada" (guest-outfit) demand peaks, in-store
# fitting and 24h click-and-collect matter most, and cheap see-through
# cross-border polyester is socially unacceptable.
BBC_MONTHS: tuple[int, int, int] = (4, 5, 6)
BBC_LABEL: str = "BBC Season (Weddings/Communions)"
OFF_LABEL: str = "Off-Season"

TRADING_DAYS_PER_YEAR: int = 252   # annualisation constant for vol and returns

# Threshold used to count "extreme negative-return days" in H2.
CRASH_THRESHOLD: float = -0.05     # a -5% day = a one-session reputational shock

# -----------------------------------------------------------------------------
# 5. VISUAL DESIGN SYSTEM
# -----------------------------------------------------------------------------
# Colours are taken from a pre-validated categorical palette (colour-blind-safe
# adjacent pairs). Rules applied throughout:
#   * colour follows the ENTITY, never its rank -> Inditex is always blue,
#     PDD is always orange, in every single chart.
#   * the benchmark is deliberately recessive (muted grey): it is context,
#     not a protagonist.
#   * gold/amber is reserved for ONE meaning only: "this is BBC season".
COLORS: dict[str, str] = {
    "itx": "#2a78d6",          # categorical slot 1 - blue   (Inditex)
    "pdd": "#eb6834",          # categorical slot 2 - orange (PDD / Temu)
    "ibex": "#898781",         # muted ink            - grey  (benchmark)
    "season": "#eda100",       # categorical slot 4 - gold   (BBC season)
    "season_band": "#eda100",  # same gold, drawn at low alpha as a background
    "neutral_bar": "#c3c2b7",  # recessive bar fill for non-BBC months
    "surface": "#fcfcfb",      # chart surface
    "ink": "#0b0b0b",          # primary text
    "ink_soft": "#52514e",     # secondary text
    "ink_muted": "#898781",    # axis labels / captions
    "grid": "#e1e0d9",         # hairline gridlines (solid, never dashed)
    "axis": "#c3c2b7",         # baseline / spine
    "pos": "#2a78d6",          # diverging pole: positive correlation
    "neg": "#e34948",          # diverging pole: negative correlation
    "mid": "#f0efec",          # diverging neutral midpoint (grey, not a hue)
}

TICKER_COLORS: dict[str, str] = {
    TARGET: COLORS["itx"],
    COMPETITOR: COLORS["pdd"],
    BENCHMARK: COLORS["ibex"],
}

FIG_DPI: int = 300             # presentation / print quality
FIG_FORMAT: str = "png"
