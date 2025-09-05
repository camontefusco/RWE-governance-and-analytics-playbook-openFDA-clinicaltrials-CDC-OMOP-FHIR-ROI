"""
roi.py — Simple ROI model for RWE-enabled programs

Exports:
- TrialScenario dataclass: inputs for a trial/program scenario
- roi_summary(ts, months_saved_with_rwe): returns dict with 'savings', 'discounted_benefit', 'ev_uplift', 'total_roi'
- npv_cashflows(cashflows, annual_rate, freq): generic NPV helper
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
import math

@dataclass
class TrialScenario:
    # Program/Trial characteristics
    baseline_duration_months: float
    patients_treatment: int
    patients_control: int
    cost_per_patient_usd: float

    # Evidence acceptance probabilities
    prob_reg_accept_rwe: float    # probability that regulator accepts evidence with RWE augmentation
    prob_reg_accept_trad: float   # baseline probability without RWE

    # Financials
    discount_rate_annual: float   # e.g., 0.10 for 10% WACC
    monthly_benefit_usd: float    # expected monthly net benefit once on market

def npv_cashflows(cashflows: Iterable[float], annual_rate: float, freq: int = 12) -> float:
    """
    Net present value of a series of cashflows at period t=1..n with rate compounded at `freq` per year.
    cashflows: list of amounts, one per period (e.g., monthly).
    """
    r = max(0.0, float(annual_rate))
    if r == 0.0:
        return float(sum(cashflows))
    pr = r / float(freq)
    return float(sum(cf / ((1 + pr) ** t) for t, cf in enumerate(cashflows, start=1)))

def roi_summary(ts: TrialScenario, months_saved_with_rwe: int = 6) -> Dict[str, float]:
    """
    Compute simple ROI components for using RWE:
    - Direct Savings: % reduction of per-patient operational cost (proxy for RWE-enabled efficiencies)
    - Discounted Time Benefit: bringing revenue forward by `months_saved_with_rwe`
    - EV Uplift: increase in expected value from higher probability of acceptance
    - Total ROI: sum of the above (illustrative)

    Notes:
    - This is an executive-friendly, conservative model; calibrate to your portfolio if needed.
    """
    # Guards
    m_saved = max(0, int(months_saved_with_rwe))
    n_patients = int(ts.patients_treatment + ts.patients_control)
    cost_pp = float(ts.cost_per_patient_usd)

    # 1) Direct savings (illustrative: 15% cut of patient-related costs)
    savings = n_patients * cost_pp * 0.15

    # 2) Discounted time benefit (bring forward m_saved months of benefit)
    # Build a monthly cashflow vector with m_saved periods of benefit
    monthly = float(ts.monthly_benefit_usd)
    cash = [monthly] * m_saved
    time_benefit = npv_cashflows(cashflows=cash, annual_rate=float(ts.discount_rate_annual), freq=12)

    # 3) EV uplift from higher acceptance probability (proxy: $1M per 10% uplift)
    uplift_prob = max(0.0, float(ts.prob_reg_accept_rwe) - float(ts.prob_reg_accept_trad))
    ev_uplift = uplift_prob * 10_000_000  # tune to your program scale

    total = float(savings + time_benefit + ev_uplift)

    return {
        "savings": float(savings),
        "discounted_benefit": float(time_benefit),
        "ev_uplift": float(ev_uplift),
        "total_roi": float(total),
    }
