"""
utils
=====
Reusable building blocks of the Zara vs Temu EDA.

    config      parameters, paths, palette      (every knob lives here)
    audit       shape ledger and NaN guards     (data-hygiene evidence)
    ingestion   download, cache, calendar align (STEP A)
    features    returns, base-100, event mask   (STEP B)
    analysis    H1/H2/H3 tables and tests       (STEP C)
    viz         the four 300-DPI charts         (STEP D)

The package deliberately contains NO analysis logic of its own: `main.py`
orchestrates, these modules do the work, and the notebook imports the exact
same functions, so the memoria can never drift away from the executed code.
"""

from . import analysis, audit, config, features, ingestion, viz  # noqa: F401

__all__ = ["config", "audit", "ingestion", "features", "analysis", "viz"]
