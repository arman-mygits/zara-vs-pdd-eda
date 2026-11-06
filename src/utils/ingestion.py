"""
ingestion.py
============
STEP A of the pipeline: download, cache, extract and calendar-align.

This module owns the two hardest *real* problems of a cross-border equity study:

    1. yfinance's column layout is not stable across versions (the MultiIndex
       order flips, and since v0.2.51 `auto_adjust=True` is the DEFAULT, which
       removes the 'Adj Close' column entirely). The extractor below is
       defensive about both cases.

    2. Madrid (BME) and New York (Nasdaq) do not share a holiday calendar.
       Semana Santa, 1 May, 15 August and 12 October close Madrid while Nasdaq
       trades; Thanksgiving, 4 July and Labor Day do the opposite. A naive
       `.dropna()` would delete every one of those sessions from BOTH markets -
       and would bias precisely the spring window this study is about, because
       Semana Santa always falls in March/April.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

from . import config as cfg
from .audit import log_shape, missing_report

# Cache file names (raw, untouched API payload - the "src/data/raw" contract).
RAW_PRICES_CSV: Path = cfg.RAW_DIR / "adj_close_raw.csv"
RAW_VOLUME_CSV: Path = cfg.RAW_DIR / "volume_raw.csv"
RAW_FULL_CSV: Path = cfg.RAW_DIR / "yfinance_full_payload.csv"


# =============================================================================
# 1. DOWNLOAD
# =============================================================================
def download_raw(
    tickers: list[str] | None = None,
    start: str = cfg.START_DATE,
    end: str = cfg.END_DATE,
) -> pd.DataFrame:
    """
    Pull daily OHLCV from Yahoo Finance for the whole universe in one request.

    Two non-obvious arguments, both deliberate:

    * `auto_adjust=False` keeps the 'Adj Close' column alive. We need the
      *adjusted* close because Inditex pays a large ordinary plus extraordinary
      dividend every year; on the raw close those ex-dividend dates print as
      fake -3% "crashes", which would mechanically inflate Inditex's measured
      downside risk and hand us a false negative on Hypothesis 2.

    * `threads=False` serialises the three requests. yfinance caches timezone
      metadata in a local SQLite file, and concurrent workers routinely raise
      `OperationalError: database is locked`, which yfinance swallows into a
      silently empty column for one ticker. Three tickers do not need
      parallelism; a silently missing competitor would invalidate the study.
    """
    tickers = tickers or cfg.TICKERS
    print(f"  Requesting {tickers} from {start} to {end} (auto_adjust=False) ...")

    with warnings.catch_warnings():
        # yfinance emits a FutureWarning about the auto_adjust default. Our
        # choice is explicit, so the noise is suppressed rather than ignored.
        warnings.simplefilter("ignore", FutureWarning)
        raw = yf.download(
            tickers=tickers,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=False,   # -> keeps 'Adj Close'
            actions=False,
            group_by="column",
            progress=False,
            threads=False,       # -> avoids the SQLite cache lock
        )

    if raw is None or raw.empty:
        raise RuntimeError(
            "yfinance returned an empty payload. Check the network connection, "
            "or re-run with --offline to use the cached CSVs in src/data/raw/."
        )

    # Persist the untouched payload: the study must stay reproducible even if
    # Yahoo restates history, or the laptop is offline before the presentation.
    raw.to_csv(RAW_FULL_CSV)
    print(f"  Raw payload cached -> {RAW_FULL_CSV.name}")
    return raw


# =============================================================================
# 2. FIELD EXTRACTION (version-proof)
# =============================================================================
def _extract_field(raw: pd.DataFrame, field: str, tickers: list[str]) -> pd.DataFrame:
    """
    Slice one price field (e.g. 'Adj Close') out of a yfinance payload,
    whatever MultiIndex orientation the installed version produced.

    Handles the three layouts seen in the wild:
        (field, ticker)  - group_by='column'  (what we request)
        (ticker, field)  - group_by='ticker'
        flat columns     - single-ticker download
    """
    if isinstance(raw.columns, pd.MultiIndex):
        level_zero = set(raw.columns.get_level_values(0))
        level_one = set(raw.columns.get_level_values(1))

        if field in level_zero:
            frame = raw.xs(field, axis=1, level=0)
        elif field in level_one:
            frame = raw.xs(field, axis=1, level=1)
        else:
            raise KeyError(f"Field '{field}' is not present in the payload.")
    else:
        if field not in raw.columns:
            raise KeyError(f"Field '{field}' is not present in the payload.")
        frame = raw[[field]].copy()
        frame.columns = [tickers[0]]

    # Reorder to the configured ticker order so that every table and every
    # chart downstream lists the universe in the same, intentional order.
    available = [t for t in tickers if t in frame.columns]
    missing = sorted(set(tickers) - set(available))
    if missing:
        raise RuntimeError(
            f"No '{field}' data returned for {missing}. This is usually the "
            "yfinance SQLite cache lock (see download_raw) or a delisted "
            "symbol - do NOT continue with a partial universe."
        )

    frame = frame[available].copy()
    frame.columns = list(frame.columns)  # drop the 'Ticker' columns index name
    return frame


def extract_prices_and_volume(
    raw: pd.DataFrame, tickers: list[str] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return (adjusted_close, volume): date-indexed frames, one column per ticker.

    DIVIDEND SAFETY NET: if the installed yfinance has dropped 'Adj Close'
    (because a future version forces auto_adjust=True), we fall back to
    'Close' - which in that case is ALREADY dividend- and split-adjusted - and
    we announce it instead of pretending nothing happened.
    """
    tickers = tickers or cfg.TICKERS

    try:
        prices = _extract_field(raw, "Adj Close", tickers)
        price_source = "Adj Close (dividend + split adjusted)"
    except KeyError:
        prices = _extract_field(raw, "Close", tickers)
        price_source = "Close (already auto-adjusted by this yfinance version)"
        print(
            "  [WARN] 'Adj Close' is absent from the payload. Falling back to "
            "'Close', which this yfinance version adjusts for dividends and "
            "splits. Total-return semantics are preserved."
        )

    volume = _extract_field(raw, "Volume", tickers)

    prices.index = pd.to_datetime(prices.index)
    volume.index = pd.to_datetime(volume.index)
    prices.index.name = "Date"
    volume.index.name = "Date"

    print(f"  Price series built from: {price_source}")
    log_shape("A1. raw Adj Close (union calendar)", prices)
    log_shape("A2. raw Volume (union calendar)", volume)

    prices.to_csv(RAW_PRICES_CSV)
    volume.to_csv(RAW_VOLUME_CSV)
    return prices, volume


def load_cached() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Offline path: rebuild the raw frames from the cached CSVs."""
    if not (RAW_PRICES_CSV.exists() and RAW_VOLUME_CSV.exists()):
        raise FileNotFoundError(
            "No cache in src/data/raw/. Run the pipeline online at least once."
        )
    prices = pd.read_csv(RAW_PRICES_CSV, index_col="Date", parse_dates=True)
    volume = pd.read_csv(RAW_VOLUME_CSV, index_col="Date", parse_dates=True)
    print(f"  Loaded cache: prices {prices.shape}, volume {volume.shape}")
    log_shape("A1. cached Adj Close (union calendar)", prices)
    log_shape("A2. cached Volume (union calendar)", volume)
    return prices, volume


# =============================================================================
# 3. CALENDAR ALIGNMENT  (the data-hygiene centrepiece)
# =============================================================================
def align_calendar(
    prices: pd.DataFrame, name: str = "Adj Close"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Align three tickers that live on two national trading calendars.

    THE RULE WE APPLY - and the one we refuse to apply:

    * REFUSED: `prices.dropna()`. It deletes every date on which EITHER Madrid
      or New York was shut, destroying valid observations for the market that
      was actually open, and biasing the April window we are studying.

    * APPLIED: forward-fill. A closed market has published no new information,
      so its last traded price is its best available estimate for that date.
      The daily return on a filled day is then exactly 0.0, which is the honest
      economic statement "that market did not trade, so nothing changed".

    * Only the LEADING and TRAILING boundary NaNs are dropped - before the
      latest common listing date there is no prior observation to carry
      forward, so filling there would fabricate data rather than align it.

    Returns
    -------
    aligned : DataFrame
        Gap-free price panel on the union calendar.
    synthetic : DataFrame
        Boolean mask, True where a value was forward-filled (that market was
        closed). This matters: filled days inject artificial zero-return
        observations that mechanically shrink a standard deviation, so H2 is
        reported both with and without them (see analysis.py).
    """
    print(f"\n  Aligning calendars for {name} ...")

    # --- 3a. Where does every series actually have data? ---------------------
    first_valid = max(prices[c].first_valid_index() for c in prices.columns)
    last_valid = min(prices[c].last_valid_index() for c in prices.columns)
    print(f"  Latest common start date  : {first_valid.date()}")
    print(f"  Earliest common end date  : {last_valid.date()}")

    trimmed = prices.loc[first_valid:last_valid]
    log_shape(
        "A3. trimmed to common listing window",
        trimmed,
        note="leading/trailing boundary NaNs only",
    )

    # --- 3b. Diagnose the gaps BEFORE touching them --------------------------
    missing_report(trimmed, f"{name} inside the common window")

    synthetic = trimmed.isna()                       # True = that market closed
    closed_days = synthetic.sum()
    print(
        "\n  Non-trading days per ticker inside the window "
        "(national holidays, to be forward-filled):"
    )
    for ticker, count in closed_days.items():
        pct = 100 * count / len(trimmed)
        print(f"    {ticker:<8s} {int(count):>4d} days  ({pct:4.1f}% of the window)")

    dropna_cost = len(trimmed) - len(trimmed.dropna())
    print(
        f"\n  >>> A blanket .dropna() would have destroyed {dropna_cost} rows "
        f"({100 * dropna_cost / len(trimmed):.1f}% of the sample). "
        f"We forward-fill instead and keep all {len(trimmed)}."
    )

    # --- 3c. Forward-fill, then prove the result is clean --------------------
    aligned = trimmed.ffill()
    log_shape(
        "A4. forward-filled (holiday alignment)",
        aligned,
        note=f"{int(closed_days.sum())} cells imputed, 0 rows lost",
    )

    if aligned.isna().any().any():
        residual = int(aligned.isna().sum().sum())
        raise ValueError(
            f"{residual} NaN(s) survived the forward-fill - inspect the window."
        )

    return aligned, synthetic


def align_volume(volume: pd.DataFrame, price_index: pd.Index) -> pd.DataFrame:
    """
    Align volume onto the SAME index as the price panel.

    Volume is deliberately NOT forward-filled. A closed exchange traded zero
    shares, and carrying yesterday's 8-million-share session into a bank
    holiday would invent liquidity that never existed - which is exactly the
    quantity Hypothesis 3 measures. Closed sessions stay NaN so that monthly
    averages are computed over real sessions only (pandas `.mean()` skips NaN).
    """
    aligned = volume.reindex(price_index)
    log_shape(
        "A5. volume reindexed onto the price calendar",
        aligned,
        note="closed sessions kept as NaN - never ffilled",
    )
    non_trading = aligned.isna().sum()
    print("  Volume cells left as NaN (exchange genuinely closed):")
    for ticker, count in non_trading.items():
        print(f"    {ticker:<8s} {int(count):>4d}")
    return aligned
