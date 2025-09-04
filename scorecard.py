from __future__ import annotations
import math, re
from typing import Dict, Any, List, Iterable
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- Existing basic metrics ----------------
def compute_basic_metrics(df: pd.DataFrame, fields_required: list[str]) -> Dict[str, Any]:
    n = len(df)
    metrics = {}
    if n == 0:
        return {k: 0.0 for k in ["completeness","consistency","timeliness","conformity"]} | {"n": 0}

    # Completeness: fraction of required fields that are non-null across rows
    complete_counts = []
    for col in fields_required:
        if col in df.columns:
            complete_counts.append(df[col].notna().mean())
        else:
            complete_counts.append(0.0)
    completeness = float(np.mean(complete_counts))

    # Consistency (very simple proxy): share of rows with unique primary keys (if present)
    pk = "safetyreportid" if "safetyreportid" in df.columns else None
    if pk:
        consistency = df[pk].nunique() / n
    else:
        consistency = max(0.3, completeness * 0.8)  # heuristic fallback

    # Timeliness: proxy using presence of 'receiptdate' and distribution recency
    if "receiptdate" in df.columns:
        try:
            dt = pd.to_datetime(df["receiptdate"], format="%Y%m%d", errors="coerce")
            recent = dt >= (pd.Timestamp.utcnow() - pd.Timedelta(days=365))
            timeliness = float(recent.mean())
        except Exception:
            timeliness = 0.5
    else:
        timeliness = 0.5

    # Conformity: fraction of columns matching expected naming (very naive)
    expected_cols = set(fields_required)
    present_cols = set(df.columns)
    conformity = len(expected_cols & present_cols) / max(1, len(expected_cols))

    return {
        "n": int(n),
        "completeness": float(completeness),
        "consistency": float(consistency),
        "timeliness": float(timeliness),
        "conformity": float(conformity),
    }

def score(metrics: Dict[str, float], weights: Dict[str, float] | None = None) -> float:
    weights = weights or {"completeness":0.30,"consistency":0.20,"timeliness":0.20,"conformity":0.15,"standards":0.15}
    total = 0.0
    for k, w in weights.items():
        total += w * float(metrics.get(k, 0.0))
    return float(total)

def plot_scorecard(metrics: Dict[str, float]) -> None:
    labels = ["Completeness","Consistency","Timeliness","Conformity","Standards"]
    vals = [metrics.get("completeness",0), metrics.get("consistency",0), metrics.get("timeliness",0), metrics.get("conformity",0), metrics.get("standards",0)]
    fig, ax = plt.subplots(figsize=(7,4))
    ax.bar(labels, vals)
    ax.set_ylim(0,1)
    ax.set_title("RWD Governance Scorecard")
    for i, v in enumerate(vals):
        ax.text(i, min(0.98, v + 0.02), f"{v:.2f}", ha="center", va="bottom", rotation=0)
    plt.tight_layout()

# ---------------- New: OMOP / FHIR conformity helpers ----------------

OMOP_MINIMUMS: Dict[str, List[str]] = {
    # Minimal, illustrative subsets of columns for common tables
    "person": ["person_id","gender_concept_id","year_of_birth"],
    "condition_occurrence": ["condition_occurrence_id","person_id","condition_concept_id","condition_start_date"],
    "drug_exposure": ["drug_exposure_id","person_id","drug_concept_id","drug_exposure_start_date"],
}

FHIR_MINIMUMS: Dict[str, List[str]] = {
    # Minimal, illustrative required elements for demonstration
    "Patient": ["resourceType","id","gender","birthDate"],
    "Observation": ["resourceType","id","status","code","subject"],
    "AdverseEvent": ["resourceType","id","subject","dateRecorded"],
}

def omop_conformity(df: pd.DataFrame, table: str) -> float:
    """Return fraction of required OMOP columns present and non-null above a threshold."""
    req = OMOP_MINIMUMS.get(table, [])
    if not req:
        return 0.0
    if df is None or df.empty:
        return 0.0
    present = [c for c in req if c in df.columns]
    if not present:
        return 0.0
    nonnull_fraction = np.mean([df[c].notna().mean() if c in df.columns else 0.0 for c in req])
    name_coverage = len(present) / len(req)
    return float(0.5 * name_coverage + 0.5 * nonnull_fraction)

def fhir_conformity(resources: Iterable[dict], resource_type: str) -> float:
    """Return fraction of required FHIR fields present across resources."""
    req = FHIR_MINIMUMS.get(resource_type, [])
    if not req:
        return 0.0
    resources = list(resources) if resources is not None else []
    if len(resources) == 0:
        return 0.0
    # share of resources that have all required fields
    has_all = []
    for r in resources:
        if not isinstance(r, dict):
            has_all.append(0.0)
            continue
        ok = all(k in r and r[k] is not None for k in req)
        has_all.append(1.0 if ok else 0.0)
    return float(np.mean(has_all))

def vocabulary_format_score(df: pd.DataFrame, col: str, pattern: str) -> float:
    """Very lightweight proxy for vocabulary conformity using regex patterns (e.g., ICD-10, RxNorm IDs)."""
    if df is None or df.empty or col not in df.columns:
        return 0.0
    series = df[col].astype(str).str.upper()
    ok = series.str.match(pattern, na=False).mean()
    return float(ok)

def standards_score(components: Dict[str, float], weights: Dict[str, float] | None = None) -> float:
    """Aggregate OMOP/FHIR/vocab components into a single standards score."""
    weights = weights or {"omop":0.5,"fhir":0.3,"vocab":0.2}
    return float(sum(weights[k]*components.get(k,0.0) for k in weights))

