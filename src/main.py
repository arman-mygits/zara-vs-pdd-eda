"""
main.py
=======
ZARA vs TEMU - "La Temporada de BBC"
End-to-end EDA pipeline: ingestion -> hygiene audit -> calendar alignment ->
feature engineering -> hypothesis testing -> four presentation charts.

BUSINESS QUESTION
-----------------
Western agile near-shoring (Inditex/Zara: design-to-rack in ~15 days from
Spain, Portugal, Morocco and Turkey) versus ultra-fast Chinese direct-to-
consumer e-commerce (PDD Holdings/Temu, the listed proxy for the privately
held Shein model: air-freight, cross-border, no local inventory).

The test bed is a cultural window that cannot be air-freighted: "La Temporada
de BBC" - Bodas, Bautizos y Comuniones - the Spanish April-to-June season of
weddings, christenings and first communions. The social stakes leave zero
tolerance for a late delivery, a wrong size or a see-through polyester dress,
so Spanish shoppers go to a physical Zara for the "coleccion de invitada",
try the outfit on, and collect within 24 hours - at full price.

HYPOTHESES (pre-stated, falsifiable)
------------------------------------
H1  Inditex earns positive excess return over BOTH ^IBEX and PDD during
    1 April - 30 June.
H2  Inditex shows lower daily volatility and fewer extreme negative outlier
    days than PDD.
H3  Inditex trading volume builds up consistently in Q2 (Apr-Jun).

USAGE
-----
    python src/main.py                 # download fresh data from Yahoo Finance
    python src/main.py --offline       # re-run from the cached CSVs in src/data/raw
    python src/main.py --no-charts     # tables only (fast iteration)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Make `src/utils` importable whether this file is run as a script, as a
# module, or imported from a notebook in src/notebooks/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import analysis, audit, config as cfg, features, ingestion, viz  # noqa: E402


# =============================================================================
# CONSOLE FORMATTING
# =============================================================================
def configure_display() -> None:
    """Make wide summary tables legible in a terminal and in a notebook."""
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.float_format", lambda v: f"{v:,.4f}")


def show(frame: pd.DataFrame, title: str) -> None:
    """Print a summary table under a clear heading."""
    print(f"\n--- {title} " + "-" * max(0, 72 - len(title)))
    print(frame.to_string())


# =============================================================================
# THE PIPELINE
# =============================================================================
def run(offline: bool = False, charts: bool = True) -> dict[str, object]:
    """
    Execute the whole study and return every artefact in a dict, so a notebook
    can call `run()` once and then inspect any intermediate object.
    """
    configure_display()
    audit.reset_ledger()

    # =========================================================================
    # STEP A - INGESTION AND CALENDAR ALIGNMENT
    # =========================================================================
    audit.banner("STEP A | INGESTION, DATA HYGIENE AUDIT AND CALENDAR ALIGNMENT")

    if offline:
        raw_prices, raw_volume = ingestion.load_cached()
    else:
        payload = ingestion.download_raw()
        raw_prices, raw_volume = ingestion.extract_prices_and_volume(payload)

    prices, synthetic = ingestion.align_calendar(raw_prices, name="Adj Close")
    audit.assert_no_nans(prices, "Aligned Adj Close panel")

    volume = ingestion.align_volume(raw_volume, prices.index)

    # =========================================================================
    # STEP B - FEATURE ENGINEERING
    # =========================================================================
    audit.banner("STEP B | FEATURE ENGINEERING")

    returns = features.compute_daily_returns(prices)
    cumulative = features.compute_cumulative_returns(returns)
    returns_featured = features.add_calendar_features(returns)
    genuine = features.genuine_trading_mask(returns, synthetic)
    panel = features.build_tidy_panel(returns, volume, genuine)

    # Persist the analysis-ready tables: a reviewer can reproduce every number
    # below from these three files alone, with no network access.
    prices.to_csv(cfg.PROCESSED_DIR / "prices_aligned.csv")
    returns_featured.to_csv(cfg.PROCESSED_DIR / "daily_returns_featured.csv")
    cumulative.to_csv(cfg.PROCESSED_DIR / "cumulative_base100.csv")
    panel.to_csv(cfg.PROCESSED_DIR / "tidy_panel.csv", index=False)
    print(f"\n  Processed datasets written to {cfg.PROCESSED_DIR.name}/ "
          f"({len(list(cfg.PROCESSED_DIR.glob('*.csv')))} files)")

    # =========================================================================
    # STEP C - HYPOTHESIS TESTING
    # =========================================================================
    audit.banner("STEP C | QUANTITATIVE HYPOTHESIS TESTING")

    # ---------------------------------------------------------------- H1 -----
    print("\n### H1 | PERFORMANCE AND SEASONAL DECOUPLING "
          "(does Zara out-earn the IBEX and Temu in Apr-Jun?)")
    h1_performance, h1_cagr = analysis.h1_season_performance(returns, prices)
    h1_alpha = analysis.h1_alpha_tests(returns)
    h1_within = analysis.h1_within_ticker_tests(returns)

    show(h1_performance, "H1.1 Compounded and annualised return by regime")
    show(h1_cagr, "H1.2 Whole-period total return and CAGR")
    show(h1_alpha, "H1.3 Excess-return (alpha) tests vs each rival")
    show(h1_within, "H1.4 BBC season vs off-season, within each ticker")

    analysis.to_markdown(h1_performance, "h1_performance_by_regime.md",
                         "H1 - Performance by regime")
    analysis.to_markdown(h1_cagr, "h1_cagr.md", "H1 - Whole-period CAGR")
    analysis.to_markdown(h1_alpha, "h1_alpha_tests.md", "H1 - Alpha tests")
    analysis.to_markdown(h1_within, "h1_within_ticker_tests.md",
                         "H1 - Season vs off-season per ticker")

    # ---------------------------------------------------------------- H2 -----
    print("\n### H2 | DOWNSIDE RISK AND VOLATILITY SUPPRESSION "
          "(is near-shoring visible in the tails?)")
    h2_risk = analysis.h2_risk_profile(returns)
    h2_risk_genuine = analysis.h2_risk_profile(returns, genuine=genuine)
    h2_tests = analysis.h2_variance_tests(returns)
    h2_tests_genuine = analysis.h2_variance_tests(returns, genuine=genuine)

    show(h2_risk, "H2.1 Risk fingerprint (full aligned panel)")
    show(h2_risk_genuine,
         "H2.2 Risk fingerprint - ROBUSTNESS: real sessions only, "
         "forward-filled zeros excluded")
    show(h2_tests, "H2.3 Variance equality tests, Inditex vs PDD")
    show(h2_tests_genuine, "H2.4 Variance tests - ROBUSTNESS: real sessions only")

    analysis.to_markdown(h2_risk, "h2_risk_profile.md", "H2 - Risk fingerprint")
    analysis.to_markdown(h2_risk_genuine, "h2_risk_profile_genuine.md",
                         "H2 - Risk fingerprint (real sessions only)")
    analysis.to_markdown(h2_tests, "h2_variance_tests.md",
                         "H2 - Variance equality tests")

    # ---------------------------------------------------------------- H3 -----
    print("\n### H3 | SEASONAL LIQUIDITY AND MARKET CONVICTION "
          "(does institutional money show up for the season?)")
    h3_monthly, h3_yearly = analysis.h3_volume_seasonality(volume)
    h3_tests = analysis.h3_volume_tests(volume)

    show(h3_monthly, "H3.1 Average daily volume by calendar month (months 1-12)")
    show(h3_yearly, "H3.2 Inditex average daily volume, year x month "
                    "(is the pattern repeatable?)")
    show(h3_tests, "H3.3 Q2 vs rest-of-year volume tests")

    analysis.to_markdown(h3_monthly, "h3_volume_by_month.md",
                         "H3 - Average daily volume by calendar month")
    analysis.to_markdown(h3_yearly, "h3_volume_year_by_month.md",
                         "H3 - Inditex volume, year x month")
    analysis.to_markdown(h3_tests, "h3_volume_tests.md", "H3 - Q2 volume tests")

    # --------------------------------------------------------- SYNTHESIS -----
    print("\n### SYNTHESIS | CORRELATION REGIMES")
    corr_season, corr_off, corr_delta = analysis.correlation_by_regime(returns)
    show(corr_season, "S.1 Correlation of daily returns - BBC season")
    show(corr_off, "S.2 Correlation of daily returns - off-season")
    show(corr_delta, "S.3 Difference (BBC minus off-season)")

    analysis.to_markdown(corr_season, "synthesis_corr_bbc.md",
                         "Correlation - BBC season")
    analysis.to_markdown(corr_off, "synthesis_corr_off.md",
                         "Correlation - off-season")
    analysis.to_markdown(corr_delta, "synthesis_corr_delta.md",
                         "Correlation difference")

    # =========================================================================
    # STEP D - VISUALISATION
    # =========================================================================
    figures: list[Path] = []
    if charts:
        audit.banner("STEP D | PRESENTATION-READY VISUALISATIONS (300 DPI)")
        viz.apply_style()

        # Each chart function saves its PNG and RETURNS the Figure (the same
        # object src/app.py renders live on filtered data). Batch jobs must
        # close what they open, or matplotlib leaks one figure per chart.
        for build in (
            lambda: viz.chart1_cumulative_returns(cumulative),
            lambda: viz.chart2_return_distributions(panel),
            lambda: viz.chart3_volume_seasonality(h3_monthly),
            lambda: viz.chart4_correlation_heatmaps(
                corr_season, corr_off, corr_delta
            ),
        ):
            figure = build()
            plt.close(figure)

        figures = sorted(cfg.FIGURES_DIR.glob(f"*.{cfg.FIG_FORMAT}"))

    # =========================================================================
    # VERDICTS AND AUDIT TRAIL
    # =========================================================================
    audit.banner("VERDICTS | WHAT THE DATA SAYS ABOUT EACH PRE-STATED HYPOTHESIS")
    verdicts = build_verdicts(h1_alpha, h1_performance, h2_tests, h2_risk, h3_tests)
    show(verdicts, "Hypothesis scorecard")
    analysis.to_markdown(verdicts, "verdicts.md", "Hypothesis scorecard")

    audit.banner("DATA HYGIENE | FULL SHAPE AUDIT LEDGER")
    ledger = audit.ledger_frame()
    show(ledger, "Row/column count at every transformation")
    ledger.to_csv(cfg.TABLES_DIR / "audit_ledger.csv", index=False)
    analysis.to_markdown(ledger.set_index("step"), "audit_ledger.md",
                         "Data hygiene - shape audit ledger")

    print("\nDone. Artefacts:")
    print(f"  raw data        : src/data/raw/        "
          f"({len(list(cfg.RAW_DIR.glob('*.csv')))} files)")
    print(f"  processed data  : src/data/processed/  "
          f"({len(list(cfg.PROCESSED_DIR.glob('*.csv')))} files)")
    print(f"  summary tables  : reports/tables/      "
          f"({len(list(cfg.TABLES_DIR.glob('*')))} files)")
    print(f"  charts (300 DPI): reports/figures/     "
          f"({len(list(cfg.FIGURES_DIR.glob('*.png')))} files)")

    return {
        "prices": prices,
        "synthetic": synthetic,
        "volume": volume,
        "returns": returns,
        "returns_featured": returns_featured,
        "cumulative": cumulative,
        "genuine": genuine,
        "panel": panel,
        "h1_performance": h1_performance,
        "h1_cagr": h1_cagr,
        "h1_alpha": h1_alpha,
        "h1_within": h1_within,
        "h2_risk": h2_risk,
        "h2_risk_genuine": h2_risk_genuine,
        "h2_tests": h2_tests,
        "h2_tests_genuine": h2_tests_genuine,
        "h3_monthly": h3_monthly,
        "h3_yearly": h3_yearly,
        "h3_tests": h3_tests,
        "corr_season": corr_season,
        "corr_off": corr_off,
        "corr_delta": corr_delta,
        "verdicts": verdicts,
        "ledger": ledger,
        "figures": figures,
    }


def build_verdicts(
    h1_alpha: pd.DataFrame,
    h1_performance: pd.DataFrame,
    h2_tests: pd.DataFrame,
    h2_risk: pd.DataFrame,
    h3_tests: pd.DataFrame,
) -> pd.DataFrame:
    """
    Turn the test output into an explicit SUPPORTED / NOT SUPPORTED scorecard.

    This is the part a bootcamp panel marks hardest: a hypothesis that is
    stated up front must be answered in the same words it was asked, including
    when the answer is "no". A rejected hypothesis is a finding, not a failure
    - it means the data was allowed to speak.
    """
    alpha_vs_ibex = h1_alpha.loc[(f"{cfg.TARGET} - {cfg.BENCHMARK}", cfg.BBC_LABEL)]
    alpha_vs_pdd = h1_alpha.loc[(f"{cfg.TARGET} - {cfg.COMPETITOR}", cfg.BBC_LABEL)]

    # H1 needs BOTH legs positive to be supported, as it was stated.
    h1_ok = bool(
        alpha_vs_ibex["Mean_daily_excess_bps"] > 0
        and alpha_vs_pdd["Mean_daily_excess_bps"] > 0
    )
    h1_significant = bool(
        alpha_vs_ibex["p_one_sided"] < 0.05 and alpha_vs_pdd["p_one_sided"] < 0.05
    )

    full = h2_tests.loc["Full period"]
    itx_full = h2_risk.loc[(cfg.TARGET, "Full period")]
    pdd_full = h2_risk.loc[(cfg.COMPETITOR, "Full period")]
    h2_vol_ok = bool(full["Ann_vol_ITX_%"] < full["Ann_vol_PDD_%"])
    h2_tail_ok = bool(
        itx_full["Downside_outliers_per_100d"] < pdd_full["Downside_outliers_per_100d"]
    )

    h3_row = h3_tests.loc[cfg.TARGET]
    h3_ok = bool(h3_row["Uplift_%"] > 0)
    h3_consistent = h3_row["Years_Q2_higher"]

    def label(direction_ok: bool, significant: bool) -> str:
        if direction_ok and significant:
            return "SUPPORTED (direction + statistically significant)"
        if direction_ok:
            return "PARTIALLY SUPPORTED (right direction, not significant at 5%)"
        return "NOT SUPPORTED (data points the other way)"

    rows = [
        {
            "Hypothesis": "H1 - Seasonal alpha vs IBEX and PDD",
            "Key evidence": (
                f"BBC-season excess vs {cfg.BENCHMARK}: "
                f"{alpha_vs_ibex['Mean_daily_excess_bps']:+.2f} bps/day "
                f"(p={alpha_vs_ibex['p_one_sided']:.3f}); "
                f"vs {cfg.COMPETITOR}: "
                f"{alpha_vs_pdd['Mean_daily_excess_bps']:+.2f} bps/day "
                f"(p={alpha_vs_pdd['p_one_sided']:.3f})"
            ),
            "Verdict": label(h1_ok, h1_significant),
        },
        {
            "Hypothesis": "H2 - Lower volatility and fewer crash days than PDD",
            "Key evidence": (
                f"Annualised vol {full['Ann_vol_ITX_%']:.1f}% vs "
                f"{full['Ann_vol_PDD_%']:.1f}% "
                f"(ratio {full['Vol_ratio_PDD_over_ITX']:.2f}x, "
                f"Levene p={full['Levene_p']:.2e}); downside outliers per 100 "
                f"sessions {itx_full['Downside_outliers_per_100d']:.2f} vs "
                f"{pdd_full['Downside_outliers_per_100d']:.2f}"
            ),
            "Verdict": label(
                h2_vol_ok and h2_tail_ok, bool(full["Levene_p"] < 0.05)
            ),
        },
        {
            "Hypothesis": "H3 - Consistent Q2 volume buildup for Inditex",
            "Key evidence": (
                f"Q2 vs rest-of-year volume {h3_row['Uplift_%']:+.1f}% "
                f"(Welch p={h3_row['Welch_p']:.3f}, "
                f"Mann-Whitney p={h3_row['MannWhitney_p']:.3f}); "
                f"years in which Q2 was higher: {h3_consistent}"
            ),
            "Verdict": label(h3_ok, bool(h3_row["Welch_p"] < 0.05)),
        },
    ]
    return pd.DataFrame(rows).set_index("Hypothesis")


# =============================================================================
# CLI
# =============================================================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zara vs Temu EDA - BBC season study."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Re-run from the cached CSVs in src/data/raw instead of calling Yahoo.",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip chart rendering (tables only).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    run(offline=args.offline, charts=not args.no_charts)
