"""
analysis.py
===========
STEP C of the pipeline: quantitative hypothesis testing and summary tables.

Three pre-stated, falsifiable hypotheses - declared BEFORE looking at the data,
which is what separates an analysis from a story told after the fact:

    H1  PERFORMANCE / DECOUPLING
        During the Spanish BBC season (1 Apr - 30 Jun) Inditex generates
        positive excess return (alpha) over BOTH the IBEX 35 and PDD.

    H2  DOWNSIDE RISK / VOLATILITY SUPPRESSION
        Inditex shows lower daily volatility and fewer extreme negative
        outlier days than PDD, because near-shoring removes the cross-border
        tariff and logistics shock channel.

    H3  SEASONAL LIQUIDITY / MARKET CONVICTION
        Inditex trading volume builds up consistently in Q2 (Apr-Jun) ahead of
        full-price seasonal sell-through.

Every table returned here is also written to reports/tables/ as markdown.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config as cfg

ANNUALISE = cfg.TRADING_DAYS_PER_YEAR


# =============================================================================
# SHARED HELPERS
# =============================================================================
def _compound(series: pd.Series) -> float:
    """Geometric total return of a set of daily returns: prod(1+r) - 1."""
    return float((1.0 + series).prod() - 1.0)


def _annualise_from_subset(series: pd.Series) -> float:
    """
    Scale a subset's compounded return to an annual rate.

    Honest reading: this is the return an investor would earn if they were
    exposed ONLY on these days, repeated for a full trading year. It is a
    comparable rate, not a tradable forecast.
    """
    n = len(series)
    if n == 0:
        return np.nan
    total = _compound(series)
    return float((1.0 + total) ** (ANNUALISE / n) - 1.0)


def _annualised_vol(series: pd.Series) -> float:
    """Daily standard deviation scaled by sqrt(252) - the market convention."""
    return float(series.std(ddof=1) * np.sqrt(ANNUALISE))


def _stars(p_value: float) -> str:
    """Conventional significance markers, so a slide can show them directly."""
    if np.isnan(p_value):
        return "n/a"
    if p_value < 0.01:
        return "*** (p<0.01)"
    if p_value < 0.05:
        return "**  (p<0.05)"
    if p_value < 0.10:
        return "*   (p<0.10)"
    return "    (n.s.)"


def to_markdown(frame: pd.DataFrame, filename: str, title: str) -> None:
    """Write a summary table to reports/tables/ as markdown for the memoria."""
    path = cfg.TABLES_DIR / filename
    body = frame.to_markdown(index=True, floatfmt=",.4f")
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    print(f"  Table saved -> reports/tables/{filename}")


# =============================================================================
# H1. PERFORMANCE AND SEASONAL DECOUPLING
# =============================================================================
def h1_season_performance(
    returns: pd.DataFrame, prices: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compare compounded and annualised performance inside vs outside BBC season,
    for all three tickers, plus whole-period CAGR.

    THE BUSINESS WHY:
        If the cultural thesis is right - Spanish women need a guest outfit
        they can try on and collect within 24h, and will pay full price for it
        - then the April-June window should be visible in Inditex's return
        series and should NOT be visible in a Chinese cross-border e-commerce
        name that has no stake in a Spanish communion.

    THE TECHNICAL WHAT:
        Group the daily returns by the binary BBC_Season mask and compound
        within each group. Annualise with the 252-day convention so the two
        groups (different day counts) are directly comparable. CAGR is computed
        separately on the full adjusted-price series, start to end.

    THE STRATEGIC SO WHAT:
        It converts "weddings matter to Zara" into a number a CFO can act on -
        and, crucially, it can come out negative, in which case we report that.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
        name="BBC_Season",
    )

    rows = []
    for ticker in returns.columns:
        for label, mask in (
            (cfg.BBC_LABEL, season_flag),
            (cfg.OFF_LABEL, ~season_flag),
        ):
            subset = returns.loc[mask, ticker]
            rows.append(
                {
                    "Ticker": ticker,
                    "Company": cfg.LABELS[ticker],
                    "Regime": label,
                    "N_days": len(subset),
                    "Mean_daily_%": 100 * subset.mean(),
                    "Median_daily_%": 100 * subset.median(),
                    "Compounded_return_%": 100 * _compound(subset),
                    "Annualised_return_%": 100 * _annualise_from_subset(subset),
                    "Hit_rate_%": 100 * float((subset > 0).mean()),
                }
            )

    performance = pd.DataFrame(rows).set_index(["Ticker", "Regime"])

    # --- Whole-period CAGR on the adjusted price series ----------------------
    span_years = (prices.index[-1] - prices.index[0]).days / 365.25
    cagr_rows = []
    for ticker in prices.columns:
        first, last = float(prices[ticker].iloc[0]), float(prices[ticker].iloc[-1])
        cagr_rows.append(
            {
                "Ticker": ticker,
                "Company": cfg.LABELS[ticker],
                "Start_price": first,
                "End_price": last,
                "Total_return_%": 100 * (last / first - 1.0),
                "Years": span_years,
                "CAGR_%": 100 * ((last / first) ** (1.0 / span_years) - 1.0),
            }
        )
    cagr = pd.DataFrame(cagr_rows).set_index("Ticker")
    return performance, cagr


def h1_alpha_tests(returns: pd.DataFrame) -> pd.DataFrame:
    """
    The actual statistical test of H1: is Inditex's EXCESS return over each
    rival positive during BBC season?

    THE TECHNICAL WHAT:
        Build the daily spread series  r_ITX - r_rival  and run a one-sided
        one-sample t-test of H0: mean spread = 0 against H1: mean spread > 0,
        restricted to BBC-season days. The paired/spread construction is the
        correct design here: both legs are observed on the same dates, so
        market-wide shocks cancel out instead of inflating the variance.
        A Wilcoxon signed-rank test is reported alongside, because daily
        equity returns are fat-tailed and the t-test leans on a normality
        assumption that returns routinely violate.

    Also reported: the same test on off-season days. If the alpha is really a
    BBC-season effect it should be materially weaker there; if it is equally
    strong year-round, then what we have found is a general Inditex premium,
    NOT a wedding-season effect - and we would have to say so.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
    )

    rows = []
    for rival in (cfg.BENCHMARK, cfg.COMPETITOR):
        spread = returns[cfg.TARGET] - returns[rival]
        for label, mask in (
            (cfg.BBC_LABEL, season_flag),
            (cfg.OFF_LABEL, ~season_flag),
        ):
            sample = spread.loc[mask].dropna()

            t_stat, p_two_sided = stats.ttest_1samp(sample, popmean=0.0)
            # One-sided (greater) p-value derived from the two-sided result.
            p_one_sided = (
                p_two_sided / 2 if t_stat > 0 else 1.0 - p_two_sided / 2
            )
            try:
                _, p_wilcoxon = stats.wilcoxon(
                    sample, alternative="greater", zero_method="zsplit"
                )
            except ValueError:
                p_wilcoxon = np.nan

            rows.append(
                {
                    "Spread": f"{cfg.TARGET} - {rival}",
                    "Regime": label,
                    "N_days": len(sample),
                    "Mean_daily_excess_bps": 1e4 * sample.mean(),
                    "Compounded_excess_%": 100 * _compound(sample),
                    "t_stat": float(t_stat),
                    "p_one_sided": float(p_one_sided),
                    "Wilcoxon_p": float(p_wilcoxon),
                    "Verdict": _stars(p_one_sided),
                }
            )

    return pd.DataFrame(rows).set_index(["Spread", "Regime"])


def h1_within_ticker_tests(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Secondary H1 test: for each ticker separately, are BBC-season daily returns
    drawn from a different distribution than off-season ones?

    Welch's t-test (unequal variances - the right default, because H2 claims
    the variances are in fact different) plus Mann-Whitney U as the
    distribution-free cross-check.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
    )

    rows = []
    for ticker in returns.columns:
        in_season = returns.loc[season_flag, ticker].dropna()
        off_season = returns.loc[~season_flag, ticker].dropna()

        t_stat, p_t = stats.ttest_ind(in_season, off_season, equal_var=False)
        u_stat, p_u = stats.mannwhitneyu(
            in_season, off_season, alternative="two-sided"
        )

        rows.append(
            {
                "Ticker": ticker,
                "Company": cfg.LABELS[ticker],
                "Mean_BBC_bps": 1e4 * in_season.mean(),
                "Mean_Off_bps": 1e4 * off_season.mean(),
                "Difference_bps": 1e4 * (in_season.mean() - off_season.mean()),
                "Welch_t": float(t_stat),
                "Welch_p": float(p_t),
                "MannWhitney_p": float(p_u),
                "Verdict": _stars(float(p_t)),
            }
        )
    return pd.DataFrame(rows).set_index("Ticker")


# =============================================================================
# H2. DOWNSIDE RISK AND VOLATILITY SUPPRESSION
# =============================================================================
def h2_risk_profile(
    returns: pd.DataFrame, genuine: pd.DataFrame | None = None
) -> pd.DataFrame:
    """
    Full risk fingerprint per ticker and regime.

    THE BUSINESS WHY:
        A supply chain is a risk-transmission channel. Inditex can redesign,
        cut and ship from Spain, Portugal, Morocco and Turkey in about fifteen
        days; PDD air-freights from Chinese factories across a border that
        tariffs, customs rules (de minimis), freight rates and geopolitics can
        reprice overnight. The claim is that this difference is *visible in the
        return distribution*, not just in a consultant's slide.

    THE TECHNICAL WHAT - four complementary statistics, because volatility
    alone hides the part that actually hurts:
        * Annualised volatility (std x sqrt(252)) - the headline risk number.
        * Skewness - sign asymmetry. Negative skew = the big moves are crashes.
        * Excess kurtosis (Fisher) - tail fatness. 0 = Gaussian; >3 means
          "fat tails", i.e. extreme days happen far more often than a normal
          distribution would allow.
        * 5th-percentile daily return - a historical Value-at-Risk proxy:
          "on the worst 1 day in 20, I lose at least this much".
        * Count of days below -5% and of lower-IQR-fence outliers - the
          literal "extreme negative outlier days" of the hypothesis.

    THE ROBUSTNESS POINT:
        If `genuine` is supplied, the statistics are computed only on real
        trading sessions, excluding the zero-returns created by our own
        forward-fill. Reporting both proves the conclusion is a property of
        the companies, not of the cleaning step.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
    )

    rows = []
    for ticker in returns.columns:
        column = returns[ticker]
        if genuine is not None:
            column = column.where(genuine[ticker])

        # Lower IQR fence is defined on the ticker's FULL sample, so that the
        # same yardstick is applied to both regimes.
        full = column.dropna()
        q1, q3 = full.quantile(0.25), full.quantile(0.75)
        lower_fence = q1 - 1.5 * (q3 - q1)

        for label, mask in (
            ("Full period", pd.Series(True, index=returns.index)),
            (cfg.BBC_LABEL, season_flag),
            (cfg.OFF_LABEL, ~season_flag),
        ):
            sample = column.loc[mask].dropna()
            if sample.empty:
                continue
            rows.append(
                {
                    "Ticker": ticker,
                    "Company": cfg.LABELS[ticker],
                    "Regime": label,
                    "N_days": len(sample),
                    "Ann_volatility_%": 100 * _annualised_vol(sample),
                    "Daily_std_%": 100 * sample.std(ddof=1),
                    "Skewness": float(stats.skew(sample, bias=False)),
                    "Excess_kurtosis": float(stats.kurtosis(sample, bias=False)),
                    "VaR_5pct_daily_%": 100 * float(sample.quantile(0.05)),
                    "Worst_day_%": 100 * float(sample.min()),
                    "Best_day_%": 100 * float(sample.max()),
                    f"Days_below_{int(100 * cfg.CRASH_THRESHOLD)}pct": int(
                        (sample < cfg.CRASH_THRESHOLD).sum()
                    ),
                    "Downside_outliers": int((sample < lower_fence).sum()),
                    "Downside_outliers_per_100d": round(
                        100 * float((sample < lower_fence).mean()), 2
                    ),
                }
            )
    return pd.DataFrame(rows).set_index(["Ticker", "Regime"])


def h2_variance_tests(
    returns: pd.DataFrame, genuine: pd.DataFrame | None = None
) -> pd.DataFrame:
    """
    Is Inditex's volatility advantage over PDD statistically real?

    THE TECHNICAL WHAT:
        * Levene's test (centred on the median = the Brown-Forsythe variant)
          for equality of variance. The median centring is what makes it
          robust to the fat tails of daily equity returns, unlike Bartlett's
          test, which would be badly mis-sized here.
        * The raw variance ratio (PDD / ITX) as the effect size, so the result
          is reported as a magnitude and not only as a p-value.
        * An F-test p-value for the variance ratio, shown for completeness and
          explicitly flagged as normality-dependent.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
    )

    def _series(ticker: str) -> pd.Series:
        column = returns[ticker]
        if genuine is not None:
            column = column.where(genuine[ticker])
        return column

    rows = []
    for label, mask in (
        ("Full period", pd.Series(True, index=returns.index)),
        (cfg.BBC_LABEL, season_flag),
        (cfg.OFF_LABEL, ~season_flag),
    ):
        itx = _series(cfg.TARGET).loc[mask].dropna()
        pdd = _series(cfg.COMPETITOR).loc[mask].dropna()

        levene_stat, levene_p = stats.levene(itx, pdd, center="median")

        var_itx = float(itx.var(ddof=1))
        var_pdd = float(pdd.var(ddof=1))
        f_stat = var_pdd / var_itx
        # One-sided F-test: is PDD's variance GREATER than Inditex's?
        f_p = float(stats.f.sf(f_stat, len(pdd) - 1, len(itx) - 1))

        rows.append(
            {
                "Regime": label,
                "N_ITX": len(itx),
                "N_PDD": len(pdd),
                "Ann_vol_ITX_%": 100 * _annualised_vol(itx),
                "Ann_vol_PDD_%": 100 * _annualised_vol(pdd),
                "Vol_ratio_PDD_over_ITX": float(
                    _annualised_vol(pdd) / _annualised_vol(itx)
                ),
                "Variance_ratio": f_stat,
                "Levene_stat": float(levene_stat),
                "Levene_p": float(levene_p),
                "F_test_p_one_sided": f_p,
                "Verdict": _stars(float(levene_p)),
            }
        )
    return pd.DataFrame(rows).set_index("Regime")


# =============================================================================
# H3. SEASONAL LIQUIDITY AND MARKET CONVICTION
# =============================================================================
def h3_volume_seasonality(volume: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Average daily traded volume by calendar month, for Inditex and PDD.

    THE BUSINESS WHY:
        Volume is the market's conviction, not its opinion. Price says what
        people think; volume says how much money moved on the thought. If
        institutional desks really do position ahead of the full-price spring
        sell-through, April-June should carry a visible liquidity premium in
        Inditex and no equivalent pattern in PDD, whose calendar is driven by
        Singles' Day and Black Friday instead.

    THE TECHNICAL WHAT:
        Group real (non-imputed) sessions by calendar month and average. A
        seasonal index is added - the month's mean divided by the ticker's
        overall mean - so the two companies, which differ by an order of
        magnitude in absolute share count, can be compared on one scale.
        ^IBEX is excluded by design: an index's reported "volume" is a
        synthetic aggregate, not traded shares.

    THE STRATEGIC SO WHAT:
        A reliable liquidity window is actionable: it is when to time an
        equity placement, a buyback tranche or an investor-day announcement.
    """
    tickers = [t for t in cfg.VOLUME_TICKERS if t in volume.columns]
    frame = volume[tickers].copy()
    frame["Month"] = pd.DatetimeIndex(frame.index).month
    frame["Year"] = pd.DatetimeIndex(frame.index).year

    monthly = frame.groupby("Month")[tickers].mean()
    monthly = monthly.reindex(range(1, 13))

    summary = pd.DataFrame(index=monthly.index)
    summary.index.name = "Month"
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    summary["Month_name"] = month_names
    summary["Is_BBC_month"] = [
        int(m in cfg.BBC_MONTHS) for m in summary.index
    ]
    for ticker in tickers:
        overall = float(frame[ticker].mean())
        summary[f"{ticker}_avg_volume"] = monthly[ticker]
        summary[f"{ticker}_seasonal_index"] = monthly[ticker] / overall
        summary[f"{ticker}_sessions"] = (
            frame.groupby("Month")[ticker].count().reindex(range(1, 13))
        )

    # Year x month matrix for Inditex: does the pattern REPEAT, or is it one
    # lucky year? "Consistent" is part of the hypothesis, so it gets tested.
    yearly = (
        frame.pivot_table(
            index="Year", columns="Month", values=cfg.TARGET, aggfunc="mean"
        )
        .reindex(columns=range(1, 13))
    )
    return summary, yearly


def h3_volume_tests(volume: pd.DataFrame) -> pd.DataFrame:
    """
    Formal test of H3: is Q2 (Apr-Jun) average volume higher than the rest of
    the year, and does it hold in every single year?

    Welch's t-test on raw daily volume plus a Mann-Whitney U, because volume is
    strongly right-skewed (a handful of index-rebalancing and results days are
    enormous) and the mean alone is a fragile statistic there. The per-year
    consistency count is reported next to the p-value: a pattern that holds in
    4 of 4 years is a different business claim than one driven by a single year.
    """
    tickers = [t for t in cfg.VOLUME_TICKERS if t in volume.columns]
    frame = volume[tickers].copy()
    frame["Month"] = pd.DatetimeIndex(frame.index).month
    frame["Year"] = pd.DatetimeIndex(frame.index).year
    is_bbc = frame["Month"].isin(cfg.BBC_MONTHS)

    rows = []
    for ticker in tickers:
        inside = frame.loc[is_bbc, ticker].dropna()
        outside = frame.loc[~is_bbc, ticker].dropna()

        t_stat, p_t = stats.ttest_ind(inside, outside, equal_var=False)
        _, p_u = stats.mannwhitneyu(inside, outside, alternative="two-sided")

        # Year-by-year consistency check.
        years, wins = [], 0
        for year, chunk in frame.groupby("Year"):
            in_y = chunk.loc[chunk["Month"].isin(cfg.BBC_MONTHS), ticker].dropna()
            out_y = chunk.loc[~chunk["Month"].isin(cfg.BBC_MONTHS), ticker].dropna()
            if in_y.empty or out_y.empty:
                continue
            years.append(year)
            wins += int(in_y.mean() > out_y.mean())

        rows.append(
            {
                "Ticker": ticker,
                "Company": cfg.LABELS[ticker],
                "Avg_volume_BBC": float(inside.mean()),
                "Avg_volume_Off": float(outside.mean()),
                "Uplift_%": 100 * (inside.mean() / outside.mean() - 1.0),
                "Welch_t": float(t_stat),
                "Welch_p": float(p_t),
                "MannWhitney_p": float(p_u),
                "Years_Q2_higher": f"{wins}/{len(years)}",
                "Verdict": _stars(float(p_t)),
            }
        )
    return pd.DataFrame(rows).set_index("Ticker")


# =============================================================================
# SYNTHESIS. CORRELATION REGIMES
# =============================================================================
def correlation_by_regime(
    returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Correlation matrix of daily returns, inside vs outside BBC season.

    THE BUSINESS WHY:
        Correlation is the diversification question: do these three move as one
        animal, or as three? If Inditex decouples from PDD precisely during the
        BBC window, the correlation between them should fall there - which is
        the portfolio-level signature of the whole thesis.

    THE TECHNICAL WHAT:
        Pearson correlation computed separately on the two regimes, plus the
        difference matrix (BBC minus Off). The difference is where the story
        is: a level of 0.3 means little on its own, a DROP from 0.5 to 0.2
        inside a known window means something.

    A CAVEAT WE KEEP VISIBLE:
        ITX.MC/^IBEX trade in Madrid and PDD in New York, with a six-hour
        offset. Same-day correlation across those sessions is therefore
        mechanically understated, since part of the US reaction to European
        news lands on OUR day t and part on day t+1. The BBC-vs-Off comparison
        is still valid because this bias applies equally to both regimes.
    """
    season_flag = pd.Series(
        pd.DatetimeIndex(returns.index).month.isin(cfg.BBC_MONTHS),
        index=returns.index,
    )
    corr_season = returns.loc[season_flag].corr()
    corr_off = returns.loc[~season_flag].corr()
    delta = corr_season - corr_off
    return corr_season, corr_off, delta
