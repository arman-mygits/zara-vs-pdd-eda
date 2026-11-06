"""
viz.py
======
STEP D of the pipeline: the four presentation-ready charts (300 DPI).

DESIGN RULES APPLIED THROUGHOUT (these are deliberate, not decoration):

    * Colour follows the ENTITY, never its rank. Inditex is blue in every
      chart, PDD is orange in every chart, the IBEX benchmark is recessive
      grey because it is context rather than a protagonist. A reader who
      learns "blue = Zara" on slide 1 is never re-taught on slide 4.
    * Gold/amber means exactly one thing anywhere in the deck: BBC season.
    * ONE y-axis per chart, always. Never a dual axis - two arbitrary scales
      invent a correlation that is not in the data. Comparability across
      different price levels is achieved by indexing to base 100 instead.
    * Bar charts start at zero (`ylim(bottom=0)`): a truncated bar baseline
      exaggerates a 5% difference into a visual 50% one, which is the single
      most common way a chart lies.
    * Thin marks, solid hairline gridlines (never dashed - dashing reads as
      "forecast"), no chartjunk, selective direct labels instead of a number
      on every point.
    * A legend is always present when there are two or more series, so
      identity is never carried by colour alone.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from . import config as cfg

C = cfg.COLORS


# =============================================================================
# GLOBAL STYLE
# =============================================================================
def apply_style() -> None:
    """Install the house style once, so no chart has to restate it."""
    sns.set_theme(style="white", context="talk")
    mpl.rcParams.update(
        {
            "figure.dpi": 110,              # on-screen while developing
            "savefig.dpi": cfg.FIG_DPI,     # 300 DPI on disk, for print/slides
            "savefig.bbox": "tight",
            "figure.facecolor": C["surface"],
            "axes.facecolor": C["surface"],
            "savefig.facecolor": C["surface"],
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
            "text.color": C["ink"],
            "axes.labelcolor": C["ink_soft"],
            "axes.edgecolor": C["axis"],
            "axes.linewidth": 0.8,
            "axes.titleweight": "bold",
            "axes.titlesize": 17,
            "axes.labelsize": 12.5,
            "axes.labelweight": "bold",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": C["grid"],
            "grid.linewidth": 0.7,
            "grid.linestyle": "-",          # solid hairline, never dashed
            "xtick.color": C["ink_muted"],
            "ytick.color": C["ink_muted"],
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.frameon": False,
            "legend.fontsize": 11,
            "lines.linewidth": 2.0,
        }
    )


def _despine(ax: plt.Axes, left: bool = False) -> None:
    """Remove the non-informative spines; keep the baseline readable."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if left:
        ax.spines["left"].set_visible(False)


def _headline(fig: plt.Figure, ax: plt.Axes, title: str, subtitle: str) -> None:
    """
    Place a bold headline above a lighter subtitle, both left-aligned to the
    plot area.

    Why not `ax.set_title()`: matplotlib anchors the axes title immediately
    above the axes, so a figure-level subtitle ends up ABOVE the title and the
    reading order inverts. Writing both in figure coordinates, anchored to the
    final axes position, keeps title-then-subtitle order guaranteed.

    Must be called AFTER the final `subplots_adjust`, so the axes position it
    reads is the one that will actually be rendered.
    """
    left = ax.get_position().x0
    fig.text(left, 0.975, title, fontsize=17.5, fontweight="bold",
             color=C["ink"], ha="left", va="top")
    fig.text(left, 0.915, subtitle, fontsize=11.5, color=C["ink_soft"],
             ha="left", va="top", linespacing=1.4)


def _save(fig: plt.Figure, filename: str) -> Path:
    """
    Persist a figure at presentation resolution and report the path.

    Deliberately does NOT close the figure: every chart function returns its
    Figure so that an interactive front-end (src/app.py) can render the very
    same object on filtered data. Closing is the caller's job - `main.py`
    closes immediately after saving, Streamlit closes after rendering.
    """
    path = cfg.FIGURES_DIR / filename
    fig.savefig(path, dpi=cfg.FIG_DPI, format=cfg.FIG_FORMAT)
    print(f"  Chart saved -> reports/figures/{filename}")
    return path


def _finish(fig: plt.Figure, filename: str | None) -> plt.Figure:
    """
    Save the figure when a filename is given, and always return it.

    This is what lets ONE implementation serve two consumers:
        main.py  -> filename given  -> writes the 300-DPI PNG for the slides
        app.py   -> filename=None   -> gets a live Figure built from whatever
                                       subset the user filtered to
    Without it, the Streamlit app would need its own copy of the plotting
    code, and the dashboard could silently drift from the deck.
    """
    if filename is not None:
        _save(fig, filename)
    return fig


def _bbc_windows(index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Every 1 April - 30 June window inside the sample, clipped to the data range.

    Clipping matters: an unclipped axvspan would stretch the x-axis beyond the
    data and silently add empty months to the chart.
    """
    windows = []
    for year in sorted(set(index.year)):
        start = max(pd.Timestamp(year=year, month=4, day=1), index.min())
        end = min(pd.Timestamp(year=year, month=6, day=30), index.max())
        if start < end:
            windows.append((start, end))
    return windows


# =============================================================================
# CHART 1 - H1: cumulative growth with the BBC season shaded
# =============================================================================
def chart1_cumulative_returns(
    cumulative: pd.DataFrame,
    filename: str | None = "01_H1_cumulative_returns.png",
) -> plt.Figure:
    """
    Normalised growth of EUR/USD 100 invested, with every BBC season shaded.

    THE BUSINESS WHY: "If I had put 100 in each of these on day one, what would
    I have today - and did the gap open during wedding season?"

    THE TECHNICAL WHAT: all three series rebased to 100 so a single y-axis
    serves all of them; the recurring event window is drawn as a background
    band rather than as a fourth line, because it is context, not a series.
    Endpoints are direct-labelled - selective labelling, not a number on
    every point.
    """
    fig, ax = plt.subplots(figsize=(14, 7.5))
    index = pd.DatetimeIndex(cumulative.index)

    # --- the recurring event window, drawn first so it sits behind the data --
    for start, end in _bbc_windows(index):
        ax.axvspan(start, end, color=C["season_band"], alpha=0.16, lw=0, zorder=0)

    # --- the three series (benchmark first, so it ends up visually behind) ---
    draw_order = [cfg.BENCHMARK, cfg.COMPETITOR, cfg.TARGET]
    for ticker in draw_order:
        if ticker not in cumulative.columns:
            continue
        is_hero = ticker == cfg.TARGET
        ax.plot(
            index,
            cumulative[ticker],
            color=cfg.TICKER_COLORS[ticker],
            linewidth=2.6 if is_hero else 1.8,
            alpha=1.0 if ticker != cfg.BENCHMARK else 0.9,
            label=f"{cfg.LABELS[ticker]}  [{ticker}]",
            zorder=4 if is_hero else 3,
            solid_capstyle="round",
        )
        # Selective direct label at the endpoint.
        final = float(cumulative[ticker].iloc[-1])
        ax.annotate(
            f"{final:,.0f}",
            xy=(index[-1], final),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=12,
            fontweight="bold",
            color=cfg.TICKER_COLORS[ticker],
        )

    # --- the base-100 reference line ----------------------------------------
    ax.axhline(100, color=C["axis"], linewidth=1.0, zorder=1)

    ax.set_xlabel("")
    ax.set_ylabel("Index level (base 100)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _despine(ax)

    # Legend: the three series plus the meaning of the gold band.
    handles, labels = ax.get_legend_handles_labels()
    handles.append(Patch(facecolor=C["season_band"], alpha=0.16, lw=0))
    labels.append(cfg.BBC_LABEL)
    # Restore the configured universe order for the reader.
    order = {f"{cfg.LABELS[t]}  [{t}]": i for i, t in enumerate(cfg.TICKERS)}
    pairs = sorted(
        zip(handles, labels), key=lambda hl: order.get(hl[1], 99)
    )
    ax.legend(
        [h for h, _ in pairs],
        [l for _, l in pairs],
        loc="upper left",
        ncol=2,
        handlelength=1.8,
    )

    fig.subplots_adjust(top=0.85, right=0.93)

    # Headline built FROM the data, so it can never drift away from the chart.
    final_levels = {t: float(cumulative[t].iloc[-1]) for t in cumulative.columns}
    _headline(
        fig,
        ax,
        f"100 invested in Zara became {final_levels[cfg.TARGET]:,.0f}; "
        f"in Temu, {final_levels[cfg.COMPETITOR]:,.0f}",
        "Growth of 100 invested on day one (total return, dividends "
        f"reinvested) | {index.min():%b %Y} - {index.max():%b %Y} | "
        "gold bands = BBC season (1 Apr - 30 Jun)",
    )
    return _finish(fig, filename)


# =============================================================================
# CHART 2 - H2: return distributions with the crash days exposed
# =============================================================================
def chart2_return_distributions(
    panel: pd.DataFrame,
    filename: str | None = "02_H2_return_distributions.png",
) -> plt.Figure:
    """
    Boxplot of daily returns by regime and company, with the extreme downside
    days drawn on top as individual points.

    THE BUSINESS WHY: a volatility number is abstract; a column of orange dots
    at -15% is not. The dots ARE the tariff and logistics shocks, one per
    session, and they are what a risk committee reacts to.

    THE TECHNICAL WHAT: x = regime, hue = company, so the colour keeps meaning
    identity exactly as in the other charts. Seaborn's own flier markers are
    switched off (`showfliers=False`) and replaced by an explicit scatter of
    the sub-5th-percentile days, each with a thin surface-coloured ring so
    overlapping points stay countable. A horizontal line marks the -5%
    "reputational shock" threshold.
    """
    subset = panel[panel["Ticker"].isin([cfg.TARGET, cfg.COMPETITOR])].copy()
    subset["Return_pct"] = 100 * subset["Return"]
    order = [cfg.BBC_LABEL, cfg.OFF_LABEL]
    hue_order = [cfg.TARGET, cfg.COMPETITOR]
    palette = {cfg.TARGET: C["itx"], cfg.COMPETITOR: C["pdd"]}

    fig, ax = plt.subplots(figsize=(13, 7.5))

    # Gold wash behind the BBC-season group: same colour language as chart 1.
    ax.axvspan(-0.5, 0.5, color=C["season_band"], alpha=0.12, lw=0, zorder=0)

    sns.boxplot(
        data=subset,
        x="Season",
        y="Return_pct",
        hue="Ticker",
        order=order,
        hue_order=hue_order,
        palette=palette,
        showfliers=False,          # fliers are re-drawn below, deliberately
        width=0.58,
        gap=0.12,                  # 2px-equivalent surface gap between fills
        linewidth=1.3,
        linecolor=C["ink_soft"],
        ax=ax,
        zorder=3,
        legend=True,
    )

    # --- overlay ONLY the extreme downside days ------------------------------
    # Threshold = each ticker's own 5th percentile over the full sample, i.e.
    # the historical VaR level already reported in the H2 table.
    thresholds = {
        t: subset.loc[subset["Ticker"] == t, "Return_pct"].quantile(0.05)
        for t in hue_order
    }
    crash = subset[
        subset.apply(
            lambda r: r["Return_pct"] <= thresholds[r["Ticker"]], axis=1
        )
    ]
    sns.stripplot(
        data=crash,
        x="Season",
        y="Return_pct",
        hue="Ticker",
        order=order,
        hue_order=hue_order,
        palette=palette,
        dodge=True,
        jitter=0.17,
        size=5.5,
        alpha=0.85,
        linewidth=0.6,
        edgecolor=C["surface"],    # surface ring keeps overlaps countable
        ax=ax,
        zorder=5,
        legend=False,
    )

    # --- reference lines -----------------------------------------------------
    ax.axhline(0, color=C["axis"], linewidth=1.0, zorder=2)
    ax.axhline(
        100 * cfg.CRASH_THRESHOLD,
        color=C["neg"],
        linewidth=1.2,
        alpha=0.75,
        zorder=2,
    )
    ax.annotate(
        f"{100 * cfg.CRASH_THRESHOLD:.0f}% day  (reputational shock threshold)",
        xy=(1.48, 100 * cfg.CRASH_THRESHOLD),
        xytext=(0, 9),
        textcoords="offset points",
        ha="right",
        fontsize=10.5,
        color=C["neg"],
        fontweight="bold",
    )

    # --- turn the empty lower half into narrative ---------------------------
    # The vertical gap between the two worst days IS the finding, so it is
    # labelled rather than left as white space.
    worst_itx_bbc = subset.loc[
        (subset["Ticker"] == cfg.TARGET) & (subset["BBC_Season"] == 1),
        "Return_pct",
    ].min()
    worst_pdd = subset.loc[subset["Ticker"] == cfg.COMPETITOR, "Return_pct"].min()

    ax.annotate(
        f"Zara's worst\nBBC-season day\n{worst_itx_bbc:.1f}%",
        xy=(-0.19, worst_itx_bbc),
        xytext=(-30, -8),
        textcoords="offset points",
        ha="right",
        va="top",
        linespacing=1.35,
        fontsize=10.5,
        fontweight="bold",
        color=C["itx"],
        arrowprops=dict(arrowstyle="-", color=C["itx"], lw=1.0, alpha=0.7),
    )
    ax.annotate(
        f"Temu's worst session: {worst_pdd:.1f}%",
        xy=(1.15, worst_pdd),
        xytext=(-16, 16),
        textcoords="offset points",
        ha="right",
        fontsize=10.5,
        fontweight="bold",
        color=C["pdd"],
        arrowprops=dict(arrowstyle="-", color=C["pdd"], lw=1.0, alpha=0.7),
    )

    ax.set_xlabel("")
    ax.set_ylabel("Daily return (%)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    _despine(ax)

    handles = [
        Patch(facecolor=palette[t], label=f"{cfg.LABELS[t]}  [{t}]")
        for t in hue_order
    ]
    handles.append(
        Line2D(
            [], [], marker="o", linestyle="none", markersize=6,
            markerfacecolor=C["ink_muted"], markeredgecolor=C["surface"],
            label="Worst-5% session (VaR tail)",
        )
    )
    ax.legend(handles=handles, loc="lower left", ncol=3)

    fig.subplots_adjust(top=0.85)

    # Volatility ratio computed here so the headline is always the truth.
    std_itx = subset.loc[subset["Ticker"] == cfg.TARGET, "Return_pct"].std(ddof=1)
    std_pdd = subset.loc[subset["Ticker"] == cfg.COMPETITOR, "Return_pct"].std(ddof=1)
    annualiser = np.sqrt(cfg.TRADING_DAYS_PER_YEAR)
    _headline(
        fig,
        ax,
        "Near-shoring compresses the downside tail; cross-border logistics does not",
        "Daily total returns by regime. Dots = each ticker's worst 5% of "
        "sessions (historical VaR tail), drawn individually.\n"
        f"Annualised volatility: Inditex {std_itx * annualiser:.1f}% vs "
        f"PDD {std_pdd * annualiser:.1f}%  ({std_pdd / std_itx:.1f}x).",
    )
    return _finish(fig, filename)


# =============================================================================
# CHART 3 - H3: monthly liquidity profile with Q2 highlighted
# =============================================================================
def chart3_volume_seasonality(
    monthly: pd.DataFrame,
    filename: str | None = "03_H3_volume_seasonality.png",
) -> plt.Figure:
    """
    Average daily traded volume of Inditex by calendar month, BBC months
    highlighted, zero baseline enforced.

    THE BUSINESS WHY: when does institutional money actually show up? That is
    the window for a placement, a buyback tranche or an investor day.

    THE TECHNICAL WHAT: a single-series bar chart using EMPHASIS, not a value
    ramp - the three BBC months carry the gold accent, every other month is
    recessive grey. Darker-where-bigger would double-encode bar length as hue
    and waste the only free channel. `ylim(bottom=0)` is explicit: with a
    truncated baseline a 10% liquidity difference would look like 60%.
    Direct labels sit on the highlighted bars only (the gold accent is
    deliberately low-contrast, so the labels carry the reading).
    """
    column = f"{cfg.TARGET}_avg_volume"
    values = monthly[column].astype(float)
    overall_mean = float(values.mean())
    colors = [
        C["season"] if is_bbc else C["neutral_bar"]
        for is_bbc in monthly["Is_BBC_month"]
    ]

    fig, ax = plt.subplots(figsize=(13, 7.2))
    bars = ax.bar(
        monthly["Month_name"],
        values / 1e6,
        color=colors,
        width=0.74,
        zorder=3,
        linewidth=0,
    )

    # Annual average reference, so each bar is readable as "above/below normal".
    ax.axhline(
        overall_mean / 1e6,
        color=C["ink_muted"],
        linewidth=1.2,
        zorder=4,
    )
    ax.annotate(
        f"Annual average: {overall_mean / 1e6:.2f}M shares/day",
        xy=(11.4, overall_mean / 1e6),
        xytext=(0, 7),
        textcoords="offset points",
        ha="right",
        fontsize=10.5,
        color=C["ink_soft"],
        fontweight="bold",
    )

    # Selective direct labels: the BBC months only.
    for bar, (_, row) in zip(bars, monthly.iterrows()):
        if not row["Is_BBC_month"]:
            continue
        # Seasonal index of 1.08 means "8% above the annual average".
        vs_average = float(row[f"{cfg.TARGET}_seasonal_index"]) - 1.0
        ax.annotate(
            f"{bar.get_height():.2f}M\n({vs_average:+.0%} vs avg)",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10.5,
            fontweight="bold",
            color=C["ink"],
            linespacing=1.3,
            # Surface-coloured backing, drawn ABOVE the annual-average rule
            # (zorder 6 > the line's 4) so a label that lands on the rule
            # masks it instead of being struck through by it.
            zorder=6,
            bbox=dict(facecolor=C["surface"], edgecolor="none", pad=2.0),
        )

    ax.set_xlabel("")
    ax.set_ylabel("Average daily volume (million shares)")
    # MANDATORY zero baseline, plus headroom so the direct labels on the
    # tallest bar do not collide with the legend.
    ax.set_ylim(bottom=0, top=float(values.max() / 1e6) * 1.30)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.1f}M"))
    ax.grid(axis="x", visible=False)
    _despine(ax)

    ax.legend(
        handles=[
            Patch(facecolor=C["season"], label=f"{cfg.BBC_LABEL} - Apr/May/Jun"),
            Patch(facecolor=C["neutral_bar"], label=cfg.OFF_LABEL),
        ],
        loc="upper right",
        ncol=1,
    )

    fig.subplots_adjust(top=0.84)

    # The honest headline: the uplift is real but FRONT-LOADED. April is the
    # peak, May is above average, and June is actually below it - so the
    # chart must not be captioned as a flat "Q2 is busier" claim.
    full_month_names = {
        "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
        "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
        "Sep": "September", "Oct": "October", "Nov": "November",
        "Dec": "December",
    }
    peak_month = full_month_names[str(monthly.loc[values.idxmax(), "Month_name"])]
    peak_index = float(monthly.loc[values.idxmax(), f"{cfg.TARGET}_seasonal_index"])
    bbc_rows = monthly[monthly["Is_BBC_month"] == 1]
    below_average = [
        full_month_names[str(row["Month_name"])]
        for _, row in bbc_rows.iterrows()
        if float(row[f"{cfg.TARGET}_seasonal_index"]) < 1.0
    ]
    caveat = (
        f" The uplift is front-loaded: {', '.join(below_average)} sits BELOW "
        "the annual average."
        if below_average
        else " All three BBC months sit above the annual average."
    )
    _headline(
        fig,
        ax,
        f"{peak_month} is Inditex's busiest trading month of the year "
        f"({peak_index - 1:+.0%} vs average)",
        f"Average daily traded volume by calendar month | {cfg.TARGET} | "
        f"{cfg.START_DATE[:4]}-{cfg.END_DATE[:4]} | real sessions only, never "
        f"forward-filled.\n{caveat.strip()}",
    )
    return _finish(fig, filename)


# =============================================================================
# CHART 4 - SYNTHESIS: correlation regimes
# =============================================================================
def chart4_correlation_heatmaps(
    corr_season: pd.DataFrame,
    corr_off: pd.DataFrame,
    delta: pd.DataFrame,
    filename: str | None = "04_SYNTHESIS_correlation_regimes.png",
) -> plt.Figure:
    """
    Three correlation matrices side by side: BBC season, off-season, and the
    difference between them.

    THE BUSINESS WHY: correlation is the diversification question - do Zara and
    Temu move as one animal or as two? If the cultural thesis holds, they
    should decouple precisely inside the April-June window.

    THE TECHNICAL WHAT: a diverging colour scale with a NEUTRAL GREY midpoint
    at zero and two opposing poles (blue = moves together, red = moves
    opposite). A rainbow ramp here would be unreadable, and a hue at the
    midpoint would hide the "no relationship" case. All three panels share one
    symmetric scale (-1 to +1) so the eye can compare panels honestly; the
    difference panel is annotated in percentage points.
    """
    diverging = LinearSegmentedColormap.from_list(
        "bbc_diverging", [C["neg"], C["mid"], C["pos"]], N=256
    )

    short_labels = [t.replace("^", "") for t in corr_season.columns]
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 6.8))

    # Panels 1 and 2 measure the SAME quantity, so they share one scale and one
    # colour bar - that is what makes them comparable by eye.
    # Panel 3 measures a DIFFERENT quantity (a change in correlation, range
    # about +/-0.1), so forcing it onto the +/-1 scale would wash every cell to
    # grey and hide the finding. It gets its own, explicitly labelled scale.
    delta_limit = 0.25
    panels = [
        (corr_season, "BBC SEASON\n(Apr - Jun)", diverging, 1.0),
        (corr_off, "OFF-SEASON\n(Jul - Mar)", diverging, 1.0),
        (delta, "CHANGE\n(BBC minus Off-Season)", diverging, delta_limit),
    ]

    for ax, (matrix, title, cmap, limit) in zip(axes, panels):
        # A correlation matrix is symmetric and its diagonal is 1.00 by
        # definition, so six of nine cells carry no information. Dropping the
        # first row and last column removes the resulting empty strips too,
        # leaving only the three real pairwise numbers.
        block = matrix.iloc[1:, :-1]
        mask = np.triu(np.ones_like(block, dtype=bool), k=1)
        ax.grid(False)
        sns.heatmap(
            block,
            mask=mask,
            cmap=cmap,
            vmin=-limit,
            vmax=limit,
            center=0,
            annot=True,
            fmt="+.2f",
            annot_kws={"fontsize": 15, "fontweight": "bold"},
            linewidths=2,                 # surface gap between cells
            linecolor=C["surface"],
            cbar=False,
            square=True,
            xticklabels=short_labels[:-1],
            yticklabels=short_labels[1:],
            ax=ax,
        )
        ax.set_title(title, fontsize=13.5, pad=14, color=C["ink"],
                     fontweight="bold")
        ax.tick_params(length=0)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontsize=11.5)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=11.5)

    fig.subplots_adjust(top=0.72, bottom=0.22, wspace=0.30)

    def _add_colorbar(axes_subset, limit: float, label: str, x0: float,
                      width: float) -> None:
        """Draw an explicitly labelled horizontal scale under given panels."""
        cax = fig.add_axes([x0, 0.10, width, 0.035])
        mappable = plt.cm.ScalarMappable(
            cmap=diverging, norm=plt.Normalize(-limit, limit)
        )
        cbar = fig.colorbar(mappable, cax=cax, orientation="horizontal")
        cbar.set_label(label, fontsize=10.5, color=C["ink_soft"], labelpad=8)
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(length=0, labelsize=9.5, colors=C["ink_muted"])

    _add_colorbar(
        axes[:2], 1.0,
        "Pearson correlation of daily returns   "
        "(red = move opposite | grey = unrelated | blue = move together)",
        0.09, 0.50,
    )
    _add_colorbar(
        axes[2:], delta_limit,
        f"Change in correlation - NOTE: different scale (+/-{delta_limit:.2f})",
        0.68, 0.25,
    )

    # Headline derived from the matrices themselves: the chart's claim and its
    # numbers can never disagree.
    d_pdd = float(delta.loc[cfg.TARGET, cfg.COMPETITOR])
    d_ibex = float(delta.loc[cfg.TARGET, cfg.BENCHMARK])
    if d_ibex < 0 and d_pdd >= 0:
        claim = ("In wedding season Zara decouples from its own market - "
                 "but not from Temu")
    elif d_pdd < 0 and d_ibex >= 0:
        claim = "In wedding season Zara decouples from Temu"
    elif d_pdd < 0 and d_ibex < 0:
        claim = "In wedding season Zara decouples from both Temu and the IBEX"
    else:
        claim = "Wedding season does not loosen Zara's market linkages"

    fig.text(0.09, 0.965, claim, fontsize=17.5, fontweight="bold",
             color=C["ink"], ha="left", va="top")
    fig.text(
        0.09, 0.90,
        f"Correlation with the IBEX 35 moves {d_ibex:+.2f} inside the season; "
        f"with PDD it moves {d_pdd:+.2f}. Lower triangle only (the matrix is "
        "symmetric; the 1.00 diagonal is omitted).\n"
        "Cross-listing caveat: Madrid and New York sessions overlap only "
        "partially, which damps same-day correlation - equally in both "
        "regimes, so the comparison still holds.",
        fontsize=11, color=C["ink_soft"], ha="left", va="top", linespacing=1.4,
    )
    return _finish(fig, filename)
