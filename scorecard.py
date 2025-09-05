"""
scorecard.py — Governance metrics + OMOP/FHIR conformity helpers

This module provides:
- DEFAULT_WEIGHTS: canonical weights for the overall governance score
- score(metrics, weights): weighted overall score
- compute_basic_metrics(df, required_fields, ...): completeness/consistency/timeliness/conformity
- plot_scorecard(metrics): quick horizontal bar chart
- omop_conformity(df, source_name=None, extras=None): vocabulary readiness heuristic
- fhir_conformity(df, source_name=None, summary=None): FHIR resource-shape heuristic
- vocabulary_format_score(df): convenience wrapper for OMOP code-format signals
- standards_score(omop, fhir): aggregate “standards” dimension (mean of OMOP+FHIR)
- json_safe(obj): convert numpy types → Python types (for JSON export)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------
# Weights & overall score
# -------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "completeness": 0.30,
    "consistency":  0.20,
    "timeliness":   0.20,
    "conformity":   0.15,
    "standards":    0.15,
}

def score(metrics: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    """
    Weighted overall governance score in [0,1].
    Missing keys default to 0.0. We normalize weights to sum to 1.
    """
    w = (weights or DEFAULT_WEIGHTS).copy()
    s = float(sum(w.values())) or 1.0
    w = {k: v/s for k, v in w.items()}
    return float(sum(w.get(k, 0.0) * float(metrics.get(k, 0.0)) for k in DEFAULT_WEIGHTS))

# -------------------------
# Core governance metrics
# -------------------------

def _infer_date_col(df: pd.DataFrame) -> Optional[str]:
    for cand in ["receiptdate", "receivedate", "StartDate", "CompletionDate", "week_ending_date", "submission_date", "date"]:
        if cand in df.columns:
            return cand
    # heuristic: any column name containing "date" or "week"
    for c in df.columns:
        lc = str(c).lower()
        if "date" in lc or "week" in lc:
            return c
    return None

def _timeliness_score_from_dates(series: pd.Series, window_days: int = 14) -> float:
    """Share of rows whose date is within the last `window_days` from the max date in the series."""
    s = pd.to_datetime(series, errors="coerce").dropna()
    if s.empty:
        return 0.0
    latest = s.max()
    recent = (s >= (latest - pd.Timedelta(days=window_days))).mean()
    try:
        return float(recent)
    except Exception:
        return 0.0

def _consistency_score(df: pd.DataFrame, key_cols: Optional[Iterable[str]] = None) -> float:
    """
    Simple schema/data consistency:
    - Penalize if key columns (if provided) are missing.
    - Penalize if duplicate rows are > 5%.
    Otherwise return ~1.0.
    """
    if df.empty:
        return 0.0
    penalty = 0.0
    if key_cols:
        missing = [c for c in key_cols if c not in df.columns]
        if missing:
            # 10% penalty per missing key col, capped at 0.6
            penalty += min(0.6, 0.1 * len(missing))
    # duplicate rate
    try:
        dup_rate = float(df.duplicated().mean())
    except Exception:
        dup_rate = 0.0
    # 1 - min(dup_rate*2, 0.4) contribution
    penalty += min(0.4, dup_rate * 2.0)
    return max(0.0, 1.0 - penalty)

def _conformity_presence(df: pd.DataFrame, required_fields: Iterable[str]) -> float:
    """
    Basic “conformity” to expected schema: fraction of required fields present.
    If no required_fields found, return 1.0 (assume N/A).
    """
    rf = list(required_fields or [])
    if not rf:
        return 1.0
    present = sum(1 for c in rf if c in df.columns)
    return float(present) / float(len(rf))

def compute_basic_metrics(
    df: pd.DataFrame,
    required_fields: Iterable[str],
    date_col: Optional[str] = None,
    consistency_keys: Optional[Iterable[str]] = None,
    timeliness_window_days: int = 14,
) -> Dict[str, float]:
    """
    Compute baseline governance metrics (0–1) + row count:
    - completeness: mean non-null across required_fields
    - consistency: penalty for missing key cols & duplicates
    - timeliness: share of rows within last N days based on date_col
    - conformity: fraction of required_fields present in df
    """
    out: Dict[str, float] = {"n": int(len(df))}
    if df.empty:
        out.update({k: 0.0 for k in ["completeness", "consistency", "timeliness", "conformity"]})
        return out

    req = [c for c in (required_fields or []) if c in df.columns]
    out["completeness"] = float(df[req].notna().mean().mean()) if req else 1.0
    out["consistency"]  = _consistency_score(df, key_cols=consistency_keys or req)
    dc = date_col or _infer_date_col(df)
    out["timeliness"]   = _timeliness_score_from_dates(df[dc]) if (dc and dc in df.columns) else 0.5
    out["conformity"]   = _conformity_presence(df, required_fields)
    return out

# -------------------------
# Plotting
# -------------------------

def plot_scorecard(metrics: Dict[str, float], title: str = "Governance Scorecard"):
    """
    Horizontal bar chart for a single metrics dict. Returns the Matplotlib figure.
    """
    keys = [k for k in ["completeness","consistency","timeliness","conformity","standards"] if k in metrics]
    vals = [float(metrics[k]) for k in keys]
    fig, ax = plt.subplots(figsize=(6, 3 + 0.3*len(keys)))
    ax.barh(keys, vals)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Score (0–1)")
    ax.set_title(title)
    for i, v in enumerate(vals):
        ax.text(v + 0.02, i, f"{v:.2f}", va="center")
    fig.tight_layout()
    return fig

# -------------------------
# OMOP vocab heuristics
# -------------------------

ISO2 = set("""US GB DE FR IT ES CA AU BR IN CN JP KR NL SE CH DK NO FI PL PT IE AT BE CZ HU RO GR IL MX ZA AR CL CO NZ SG AE SA QA KW BH""".split())
ICD10_RE = re.compile(r"^[A-TV-Z][0-9]{2}(\.[0-9A-Za-z]{1,4})?$")

def _share_iso_countries(s: Optional[pd.Series]) -> float:
    if s is None or s.empty: return 0.0
    vals = s.astype(str).str.upper().str.strip()
    return float((vals.isin(ISO2)).mean())

def _icd10_share(series: Optional[pd.Series]) -> float:
    if series is None or series.empty: return 0.0
    vals = series.astype(str).str.strip()
    return float(vals.apply(lambda x: bool(ICD10_RE.match(x))).mean())

def vocabulary_format_score(df: pd.DataFrame) -> float:
    """
    Convenience: quick score reflecting code-like columns (ICD-10 & ISO country presence).
    Not a replacement for a full OMOP mapping, but a useful readiness signal.
    """
    # Try common columns
    icd_share = 0.0
    for col in ("Condition", "diagnosis", "icd10", "icd_10", "icd_code"):
        if col in df.columns:
            # split semicolon lists if present
            ser = df[col].astype(str).str.split(";").explode().str.strip()
            icd_share = max(icd_share, _icd10_share(ser))
    iso_share = _share_iso_countries(df["occurcountry"]) if "occurcountry" in df.columns else 0.0
    return float(min(1.0, 0.7 * icd_share + 0.3 * iso_share))

def omop_conformity(
    df: pd.DataFrame,
    source_name: Optional[str] = None,
    extras: Optional[Dict[str, pd.DataFrame]] = None
) -> float:
    """
    Returns OMOP vocabulary readiness in [0,1].
    Heuristics:
    - OpenFDA: MedDRA PT presence (reactions), ISO country codes, (optional RxNorm-like names if available)
    - CT.gov: ICD10-like strings in Condition; Phase present
    - Else: falls back to vocabulary_format_score(df)
    """
    extras = extras or {}
    if df.empty:
        return 0.0

    if (source_name or "").lower() == "openfda":
        # MedDRA PT presence via reactions long
        rx = extras.get("reactions_df")
        if rx is None:
            # try to load lazily if caller forgot
            try:
                rx = pd.read_csv("data/openfda_reactions_long.csv")
            except Exception:
                rx = pd.DataFrame()
        meddra_present = bool((not rx.empty) and ("reactionmeddrapt" in rx.columns) and rx["reactionmeddrapt"].notna().any())
        iso_share = _share_iso_countries(df["occurcountry"]) if "occurcountry" in df.columns else 0.0
        rx_like = 0.0  # leave 0.0 unless you wire RxNav mapping
        voc = min(1.0, 0.5*float(meddra_present) + 0.3*iso_share + 0.2*rx_like)
        return float(voc)

    if (source_name or "").lower() in ("ctgov", "clinicaltrials", "clinicaltrials.gov"):
        cond_share = 0.0
        if "Condition" in df.columns:
            ser = df["Condition"].astype(str).str.split(";").explode().str.strip()
            cond_share = _icd10_share(ser)  # often 0.0 (free text)
        phase_present = "Phase" in df.columns
        voc = min(1.0, 0.7*cond_share + 0.3*float(phase_present))
        return float(voc)

    # Generic
    return vocabulary_format_score(df)

# -------------------------
# FHIR structure heuristics
# -------------------------

def fhir_conformity(
    df: pd.DataFrame,
    source_name: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None
) -> float:
    """
    FHIR resource “shape” completeness in [0,1], by source:
    - OpenFDA → AdverseEvent-like (id, date, seriousness)
    - CT.gov → ResearchStudy-like (NCTId, OverallStatus, Phase, Dates)
    - CDC → Observation-like (date, geo, numeric) from summary dict
    """
    src = (source_name or "").lower()
    if src == "openfda":
        if df.empty: return 0.0
        has_id   = "safetyreportid" in df.columns
        has_date = ("receiptdate" in df.columns) or ("receivedate" in df.columns)
        has_ser  = "serious" in df.columns
        return float(min(1.0, 0.4*float(has_id) + 0.3*float(has_date) + 0.3*float(has_ser)))

    if src in ("ctgov", "clinicaltrials", "clinicaltrials.gov"):
        if df.empty: return 0.0
        has_nct  = "NCTId" in df.columns
        has_stat = "OverallStatus" in df.columns
        has_ph   = "Phase" in df.columns
        has_date = ("StartDate" in df.columns) or ("CompletionDate" in df.columns)
        return float(min(1.0, 0.3*float(has_nct) + 0.25*float(has_stat) + 0.25*float(has_ph) + 0.20*float(has_date)))

    if src == "cdc":
        # Use summary because CDC cell often stores pre-aggregated metrics
        if not summary:
            return 0.0
        has_date = bool(summary.get("date_col"))
        has_geo  = bool(summary.get("geo_col"))
        has_num  = bool(summary.get("num_cols"))
        return float(min(1.0, 0.4*float(has_date) + 0.3*float(has_geo) + 0.3*float(has_num)))

    # Unknown source → neutral
    return 0.5

# -------------------------
# Standards aggregation
# -------------------------

def standards_score(omop: float, fhir: float) -> float:
    """
    Aggregate “standards” dimension as the mean of OMOP vocab & FHIR shape.
    """
    try:
        return float(np.mean([float(omop), float(fhir)]))
    except Exception:
        return 0.0

# -------------------------
# JSON-safe util
# -------------------------

def json_safe(obj: Any) -> Any:
    """Recursively convert numpy types to built-in Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)): return bool(obj)
    if isinstance(obj, (np.integer,)):    return int(obj)
    if isinstance(obj, (np.floating,)):   return float(obj)
    return obj
