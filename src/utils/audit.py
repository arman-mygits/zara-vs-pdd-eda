"""
audit.py
========
Data-hygiene instrumentation.

THE BUSINESS WHY:
    The single most common way a data project dies in front of a stakeholder is
    the question "how many rows did you lose on the way?" - and the analyst not
    knowing. Every transformation in this pipeline is wrapped in an audit line
    that prints the shape before and after, so sample attrition is *declared*
    instead of discovered.

THE TECHNICAL WHAT:
    A tiny ledger (list of dicts) records step name, rows, columns and the row
    delta versus the previous step. At the end of the run the ledger is printed
    as a markdown table and written to disk as part of the deliverable.

THE STRATEGIC SO WHAT:
    A reviewer can verify in ten seconds that no observation was silently
    dropped, which is exactly the trust that lets the conclusions stand.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Module-level ledger of every shape change in the pipeline.
_LEDGER: list[dict[str, Any]] = []


def banner(title: str, char: str = "=", width: int = 78) -> None:
    """Print a visually unambiguous section header in the console log."""
    print(f"\n{char * width}\n{title}\n{char * width}")


def log_shape(step: str, df: pd.DataFrame, note: str = "") -> pd.DataFrame:
    """
    Record and print the shape of `df` after the transformation named `step`.

    Returns `df` unchanged so the call can be chained inline:
        df = log_shape("after ffill", df.ffill())
    """
    rows, cols = df.shape
    previous_rows = _LEDGER[-1]["rows"] if _LEDGER else None
    delta = None if previous_rows is None else rows - previous_rows

    _LEDGER.append(
        {"step": step, "rows": rows, "cols": cols, "row_delta": delta, "note": note}
    )

    delta_txt = "     -" if delta is None else f"{delta:+6d}"
    print(f"  [AUDIT] {step:<46s} shape={str((rows, cols)):>14s}  d_rows={delta_txt}  {note}")
    return df


def assert_no_nans(df: pd.DataFrame, context: str) -> None:
    """
    Fail loudly if NaNs survive where the pipeline guarantees none.

    Defensive programming beats a silent NaN that propagates into a mean and
    quietly biases a headline number on a presentation slide.
    """
    total = int(df.isna().sum().sum())
    if total:
        per_column = df.isna().sum()
        raise ValueError(
            f"{context}: {total} NaN(s) survived cleaning.\n"
            f"Per column:\n{per_column[per_column > 0]}"
        )
    print(f"  [CHECK] {context}: 0 NaNs remaining  (OK)")


def missing_report(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Per-column missing-value report: absolute count and percentage.

    This is the evidence base for choosing *targeted* imputation over a blanket
    `.dropna()`: it shows that the gaps are calendar artefacts (a handful of
    national holidays), not broken data.
    """
    report = pd.DataFrame(
        {
            "n_missing": df.isna().sum(),
            "pct_missing": (df.isna().mean() * 100).round(2),
            "first_valid": [df[c].first_valid_index() for c in df.columns],
            "last_valid": [df[c].last_valid_index() for c in df.columns],
        }
    )
    print(f"\n  Missing-value report - {name}:")
    print(report.to_string())
    return report


def ledger_frame() -> pd.DataFrame:
    """Return the full audit ledger as a DataFrame (for the memoria / report)."""
    return pd.DataFrame(_LEDGER)


def reset_ledger() -> None:
    """Clear the ledger (used when the pipeline is re-run inside a notebook)."""
    _LEDGER.clear()
