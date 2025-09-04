from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict

@dataclass
class TrialScenario:
    baseline_duration_months: float
    patients_treatment: int
    patients_control: int
    cost_per_patient_usd: float
    prob_reg_accept_rwe: float  # 0..1
    prob_reg_accept_trad: float  # 0..1
    discount_rate_annual: float = 0.1  # for time value
    monthly_benefit_usd: float = 0.0   # value of getting to market earlier per month

def cost(trial: TrialScenario) -> Dict[str, float]:
    """Compute direct patient costs for traditional vs synthetic/external control."""
    trad_cost = (trial.patients_treatment + trial.patients_control) * trial.cost_per_patient_usd
    rwe_cost = (trial.patients_treatment) * trial.cost_per_patient_usd  # assumes external control arm from RWD
    return {"traditional_cost": trad_cost, "rwe_cost": rwe_cost, "savings": trad_cost - rwe_cost}

def time_savings(trial: TrialScenario, months_saved_with_rwe: float) -> Dict[str, float]:
    """Compute time-to-market acceleration and discounted benefit."""
    dr = trial.discount_rate_annual
    monthly_rate = (1 + dr) ** (1/12) - 1
    # Sum of discounted monthly benefits over months saved
    benefit = 0.0
    for m in range(1, int(max(0, months_saved_with_rwe)) + 1):
        benefit += trial.monthly_benefit_usd / ((1 + monthly_rate) ** m)
    return {"months_saved": months_saved_with_rwe, "discounted_benefit": benefit}

def value_of_success(trial: TrialScenario) -> Dict[str, float]:
    """Expected value uplift if RWE increases regulatory/payer acceptance probability."""
    uplift = max(0.0, trial.prob_reg_accept_rwe - trial.prob_reg_accept_trad)
    # EV uplift as % * an arbitrary 'launch value' proxy via monthly_benefit over a year (12 months)
    launch_value_proxy = 12 * trial.monthly_benefit_usd
    return {"acceptance_uplift": uplift, "ev_uplift": uplift * launch_value_proxy}

def roi_summary(trial: TrialScenario, months_saved_with_rwe: float) -> Dict[str, float]:
    c = cost(trial)
    t = time_savings(trial, months_saved_with_rwe)
    v = value_of_success(trial)
    total_benefit = c["savings"] + t["discounted_benefit"] + v["ev_uplift"]
    total_investment = 0.1 * c["rwe_cost"]  # placeholder for data acquisition/governance/tooling (10% of RWE cost)
    roi = (total_benefit - total_investment) / max(1.0, total_investment)
    return {
        **c, **t, **v,
        "total_benefit": total_benefit,
        "total_investment": total_investment,
        "roi_multiple": roi
    }
