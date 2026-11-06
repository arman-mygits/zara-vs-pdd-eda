"""
features.py
===========
STEP B of the pipeline: feature engineering.

Four derived objects, each answering a business question that raw prices cannot:

    1. daily_returns  -> "how risky is each day?"       (comparable across prices)
    2. cum_returns    -> "who won, per euro invested?"  (base 100, scale-free)
    3. BBC_Season     -> "was this a wedding-season day?" (the event mask)
    4. Year / Month   -> "how does it repeat?"            (seasonality grouping)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .audit import log_shape


# =============================================================================
# B1. DAILY RETURNS
# =============================================================================
def compute_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    daily_return_t = (P_t - P_{t-1}) / P_{t-1}

    THE BUSINESS WHY:
        Inditex trades near EUR 50, PDD near USD 150 and the IBEX near 11,000
        points. Absolute price moves are not comparable across them: a EUR 1
        move means something completely different in each series. Percentage
        returns put all three on one scale and are additive in log space,
        which is what every risk statistic in H2 requires.

    THE TECHNICAL WHAT:
        `.pct_change()` on the aligned panel. Row 1 is NaN by construction -
        there is no prior day to compare against - so exactly that one row is
        dropped, by position, and the removal is logged. This is a *targeted*
        boundary removal, not a blanket `.dropna()`.

    A CURRENCY CAVEAT WE STATE OUT LOUD:
        ITX.MC and ^IBEX are quoted in EUR, PDD in USD. These are therefore
        local-currency total returns, exactly as a domestic investor in each
        market experiences them. We do NOT convert to a single currency,
        because doing so would blend EUR/USD exchange-rate volatility into
        PDD's risk profile and we would no longer be measuring the
        supply-chain effect that H2 is about.
    """
    returns = prices.pct_change()
    log_shape("B1a. daily returns (row 1 is NaN by construction)", returns)

    # Drop ONLY the first row: the single unavoidable boundary NaN.
    returns = returns.iloc[1:]
    log_shape(
        "B1b. daily returns after boundary trim",
        returns,
        note="-1 row by design (no t-1 for the first date)",
    )

    if returns.isna().any().any():
        raise ValueError("Unexpected NaNs in the return matrix after the trim.")

    return returns


# =============================================================================
# B2. NORMALISED GROWTH (BASE 100)
# =============================================================================
def compute_cumulative_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """
    cum_return = (1 + daily_returns).cumprod() * 100

    THE BUSINESS WHY:
        A CFO does not ask "what was the price?", they ask "what happened to my
        money?". Rebasing all three series to 100 on day one answers exactly
        that and makes the three lines directly comparable on ONE y-axis -
        which is also why this chart never needs a deceptive dual axis.

    THE TECHNICAL WHAT:
        Geometric (compounded) accumulation, not a cumulative sum. Returns
        compound multiplicatively: +10% then -10% is -1%, not 0%. A row of
        exactly 100 is prepended at the day before the first return so that
        every chart starts visibly from the common baseline.
    """
    cumulative = (1.0 + returns).cumprod() * 100.0

    # Prepend the explicit base-100 anchor row (the first price date).
    anchor_date = returns.index[0] - pd.Timedelta(days=1)
    anchor = pd.DataFrame(
        100.0, index=[anchor_date], columns=returns.columns
    )
    cumulative = pd.concat([anchor, cumulative])
    cumulative.index.name = "Date"

    log_shape(
        "B2. cumulative growth, base 100",
        cumulative,
        note="+1 anchor row at base 100",
    )
    return cumulative


# =============================================================================
# B3 + B4. EVENT MASK AND CALENDAR FEATURES
# =============================================================================
def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Attach `Year`, `Month`, `Quarter`, the binary `BBC_Season` flag and a
    human-readable `Season` label to a date-indexed frame.

    THE BUSINESS WHY:
        The hypotheses are not about "spring" in the abstract, they are about a
        specific, recurring, culturally fixed commercial window: Bodas,
        Bautizos y Comuniones, April to June. Encoding that window as a column
        turns a cultural claim into something a `groupby` can falsify.

    THE TECHNICAL WHAT:
        `BBC_Season = 1` for calendar months 4, 5 and 6; `0` otherwise. A
        binary integer flag (not a string) so it can be used directly as a
        mask, a filter and a groupby key. `Season` carries the same
        information as a readable label for chart legends.

    THE STRATEGIC SO WHAT:
        Any stakeholder can now ask "show me only wedding season" and get an
        answer in one line of code - the analysis becomes self-service.
    """
    out = frame.copy()
    idx = pd.DatetimeIndex(out.index)

    out["Year"] = idx.year
    out["Month"] = idx.month
    out["Quarter"] = idx.quarter
    out["BBC_Season"] = idx.month.isin(cfg.BBC_MONTHS).astype(int)
    out["Season"] = np.where(out["BBC_Season"] == 1, cfg.BBC_LABEL, cfg.OFF_LABEL)

    n_season = int(out["BBC_Season"].sum())
    n_total = len(out)
    log_shape(
        "B3/B4. calendar + BBC_Season event mask",
        out,
        note=f"{n_season}/{n_total} rows flagged as BBC season "
             f"({100 * n_season / n_total:.1f}%)",
    )
    return out


# =============================================================================
# B5. THE HONESTY MASK (robustness support for H2)
# =============================================================================
def genuine_trading_mask(
    returns: pd.DataFrame, synthetic: pd.DataFrame
) -> pd.DataFrame:
    """
    Boolean frame, True where a return reflects a REAL trading session.

    THE BUSINESS WHY:
        Forward-filling across foreign holidays is the right way to align two
        calendars, but it has a side effect we must not hide: every filled day
        produces a 0.00% return. Zeros pull a standard deviation down. Since
        H2 claims Inditex is *less* volatile than PDD, and the two have
        different numbers of holidays, we must prove the result is not an
        artefact of our own imputation.

    THE TECHNICAL WHAT:
        A return at date t is genuine when neither t nor t-1 was forward-filled
        for that ticker. The mask is reindexed onto the return index, and H2 is
        then computed twice - on the full aligned panel and on genuine sessions
        only - so the reviewer can see both.
    """
    was_filled = synthetic.reindex(returns.index).fillna(False)
    previous_filled = synthetic.reindex(synthetic.index).shift(1).fillna(False)
    previous_filled = previous_filled.reindex(returns.index).fillna(False)

    genuine = (~was_filled.astype(bool)) & (~previous_filled.astype(bool))
    genuine = genuine[returns.columns]

    print("\n  Genuine (non-forward-filled) return observations per ticker:")
    for ticker in genuine.columns:
        kept = int(genuine[ticker].sum())
        print(
            f"    {ticker:<8s} {kept:>5d} / {len(genuine)} "
            f"({100 * kept / len(genuine):5.1f}%)"
        )
    return genuine


# =============================================================================
# B6. ASSEMBLE THE ANALYSIS-READY LONG TABLE
# =============================================================================
def build_tidy_panel(
    returns: pd.DataFrame,
    volume: pd.DataFrame,
    genuine: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reshape the wide matrices into one tidy (long) panel:
    one row per ticker-date, columns = Return, Volume, calendar features.

    THE TECHNICAL WHAT:
        Seaborn's categorical API (boxplot, barplot) expects long format, and
        a single tidy table is also the easiest artefact to hand to a
        colleague or to re-load into a BI tool. Built with `.melt()`, which
        cannot silently drop observations.
    """
    long_returns = (
        returns.reset_index()
        .melt(id_vars="Date", var_name="Ticker", value_name="Return")
    )
    long_volume = (
        volume.reset_index()
        .melt(id_vars="Date", var_name="Ticker", value_name="Volume")
    )
    long_genuine = (
        genuine.reset_index()
        .melt(id_vars="Date", var_name="Ticker", value_name="GenuineSession")
    )

    panel = long_returns.merge(long_volume, on=["Date", "Ticker"], how="left")
    panel = panel.merge(long_genuine, on=["Date", "Ticker"], how="left")

    panel["Year"] = panel["Date"].dt.year
    panel["Month"] = panel["Date"].dt.month
    panel["Quarter"] = panel["Date"].dt.quarter
    panel["BBC_Season"] = panel["Month"].isin(cfg.BBC_MONTHS).astype(int)
    panel["Season"] = np.where(
        panel["BBC_Season"] == 1, cfg.BBC_LABEL, cfg.OFF_LABEL
    )
    panel["Company"] = panel["Ticker"].map(cfg.LABELS)

    expected_rows = returns.shape[0] * returns.shape[1]
    log_shape(
        "B6. tidy long panel (ticker x date)",
        panel,
        note=f"expected {expected_rows} rows -> "
             f"{'OK' if len(panel) == expected_rows else 'MISMATCH'}",
    )
    if len(panel) != expected_rows:
        raise ValueError(
            f"Tidy reshape lost or duplicated rows: {len(panel)} != {expected_rows}"
        )
    return panel
