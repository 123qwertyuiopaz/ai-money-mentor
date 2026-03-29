"""
Financial calculator — pure Python math for Indian personal finance.
No LLM needed here; these are deterministic functions that the agents
use to pre-compute numbers before passing them to NIM for narrative.
"""
from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Any


# ── Constants ──────────────────────────────────────────────────────────────────

INFLATION_RATE = 0.06          # 6% long-term CPI inflation (India)
POST_RETIRE_RETURN = 0.08      # conservative corpus return post-retirement
FD_RATE = 0.07                 # benchmark FD rate
EPF_RATE = 0.085               # EPF interest 2024-25


# ── SIP / Lumpsum projections ─────────────────────────────────────────────────

def sip_future_value(monthly_sip: float, annual_return: float, years: int) -> float:
    """
    Future value of a monthly SIP using compound interest formula.
    FV = P × [(1+r)^n - 1] / r × (1+r)
    """
    if monthly_sip <= 0 or years <= 0:
        return 0.0
    r = annual_return / 12          # monthly rate
    n = years * 12                  # total months
    return monthly_sip * ((math.pow(1 + r, n) - 1) / r) * (1 + r)


def lumpsum_future_value(amount: float, annual_return: float, years: int) -> float:
    """FV = P × (1+r)^n"""
    return amount * math.pow(1 + annual_return, years)


def required_sip(target: float, annual_return: float, years: int) -> float:
    """Reverse SIP — how much must I invest monthly to reach target?"""
    if years <= 0 or annual_return <= 0:
        return target / (years * 12) if years > 0 else 0.0
    r = annual_return / 12
    n = years * 12
    denom = ((math.pow(1 + r, n) - 1) / r) * (1 + r)
    return target / denom if denom else 0.0


def inflation_adjusted(amount: float, years: int) -> float:
    """How much will `amount` of today's rupees be worth in `years` years?"""
    return amount * math.pow(1 + INFLATION_RATE, years)


# ── Retirement corpus ─────────────────────────────────────────────────────────

def retirement_corpus_needed(
    monthly_expenses_today: float,
    current_age: int,
    retirement_age: int,
    life_expectancy: int = 85,
) -> dict[str, float]:
    """
    Calculate the corpus needed at retirement to fund inflation-adjusted expenses.
    Returns corpus at retirement, monthly SIP required, and other key numbers.
    """
    years_to_retire = retirement_age - current_age
    retirement_years = life_expectancy - retirement_age

    # Inflate today's expenses to retirement day
    monthly_at_retire = inflation_adjusted(monthly_expenses_today, years_to_retire)
    annual_at_retire = monthly_at_retire * 12

    # Present value of annuity: corpus = annual_expense / (r - g) × [1 - ((1+g)/(1+r))^n]
    r = POST_RETIRE_RETURN
    g = INFLATION_RATE
    if abs(r - g) < 1e-9:
        corpus = annual_at_retire * retirement_years
    else:
        corpus = annual_at_retire * (1 - math.pow((1 + g) / (1 + r), retirement_years)) / (r - g)

    # SIP needed at 12% CAGR (equity) to build this corpus
    sip_at_12 = required_sip(corpus, 0.12, years_to_retire)
    sip_at_10 = required_sip(corpus, 0.10, years_to_retire)

    return {
        "corpus_needed": round(corpus),
        "monthly_expenses_at_retire": round(monthly_at_retire),
        "years_to_retire": years_to_retire,
        "sip_required_12pct": round(sip_at_12),
        "sip_required_10pct": round(sip_at_10),
    }


# ── Emergency fund ────────────────────────────────────────────────────────────

def emergency_fund_gap(
    monthly_expenses: float,
    existing_liquid: float,
    months_target: int = 6,
) -> dict[str, float]:
    target = monthly_expenses * months_target
    gap = max(0.0, target - existing_liquid)
    return {
        "target": round(target),
        "existing": round(existing_liquid),
        "gap": round(gap),
        "months_covered": round(existing_liquid / monthly_expenses, 1) if monthly_expenses else 0,
    }


# ── Tax calculator (India FY 2024-25) ────────────────────────────────────────

_OLD_SLABS = [
    (250_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

_NEW_SLABS = [           # New regime (default from FY24-25)
    (300_000, 0.00),
    (600_000, 0.05),
    (900_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]

STANDARD_DEDUCTION_OLD = 50_000
STANDARD_DEDUCTION_NEW = 75_000


def _slab_tax(taxable: float, slabs: list) -> float:
    tax = 0.0
    prev = 0.0
    for limit, rate in slabs:
        if taxable <= prev:
            break
        band = min(taxable, limit) - prev
        tax += band * rate
        prev = limit
    return tax


def tax_old_regime(
    gross_annual: float,
    deductions_80c: float = 0,
    nps_80ccd: float = 0,
    home_loan_interest: float = 0,
    hra_exempt: float = 0,
    other_deductions: float = 0,
) -> dict[str, float]:
    """Compute tax under old regime with deductions."""
    gross = gross_annual - STANDARD_DEDUCTION_OLD
    total_deductions = (
        min(deductions_80c, 150_000)          # 80C cap
        + min(nps_80ccd, 50_000)              # 80CCD(1B) extra NPS
        + min(home_loan_interest, 200_000)    # Section 24
        + hra_exempt
        + other_deductions
    )
    taxable = max(0, gross - total_deductions)
    tax = _slab_tax(taxable, _OLD_SLABS)
    # Section 87A rebate (up to ₹12,500 if taxable ≤ ₹5L)
    rebate = min(tax, 12_500) if taxable <= 500_000 else 0
    # 4% health & education cess applied on tax after rebate
    tax_after_rebate = max(0, tax - rebate)
    cess = tax_after_rebate * 0.04
    total_tax = tax_after_rebate + cess
    return {
        "gross": round(gross_annual),
        "taxable_income": round(taxable),
        "total_deductions": round(total_deductions),
        "tax_before_cess": round(tax),
        "rebate_87a": round(rebate),
        "cess": round(cess),
        "total_tax": round(total_tax),
        "effective_rate": round(total_tax / gross_annual * 100, 2) if gross_annual else 0,
        "monthly_take_home": round((gross_annual - total_tax) / 12),
    }


def tax_new_regime(gross_annual: float) -> dict[str, float]:
    """Compute tax under new regime (no deductions except standard)."""
    taxable = max(0, gross_annual - STANDARD_DEDUCTION_NEW)
    tax = _slab_tax(taxable, _NEW_SLABS)
    rebate = min(tax, 25_000) if taxable <= 700_000 else 0
    tax_after_rebate = max(0, tax - rebate)
    cess = tax_after_rebate * 0.04
    total_tax = tax_after_rebate + cess
    return {
        "gross": round(gross_annual),
        "taxable_income": round(taxable),
        "total_deductions": round(STANDARD_DEDUCTION_NEW),
        "tax_before_cess": round(tax),
        "rebate_87a": round(rebate),
        "cess": round(cess),
        "total_tax": round(total_tax),
        "effective_rate": round(total_tax / gross_annual * 100, 2) if gross_annual else 0,
        "monthly_take_home": round((gross_annual - total_tax) / 12),
    }


def tax_comparison(
    gross_annual: float,
    deductions_80c: float = 0,
    nps_80ccd: float = 0,
    home_loan_interest: float = 0,
    hra_exempt: float = 0,
) -> dict[str, Any]:
    old = tax_old_regime(gross_annual, deductions_80c, nps_80ccd, home_loan_interest, hra_exempt)
    new = tax_new_regime(gross_annual)
    saving = old["total_tax"] - new["total_tax"]
    recommendation = "old_regime" if saving > 0 else "new_regime"
    return {
        "old_regime": old,
        "new_regime": new,
        "saving_with_old": round(saving),
        "recommendation": recommendation,
        "reason": (
            f"Old regime saves ₹{abs(saving):,.0f}/year due to deductions"
            if saving > 0
            else f"New regime saves ₹{abs(saving):,.0f}/year — your deductions don't exceed the threshold"
        ),
    }


# ── HRA exemption ─────────────────────────────────────────────────────────────

def hra_exemption(
    basic_salary_annual: float,
    hra_received_annual: float,
    rent_paid_annual: float,
    is_metro: bool = True,
) -> float:
    """
    HRA exemption = minimum of:
    (a) HRA actually received
    (b) 50% of basic (metro) or 40% (non-metro)
    (c) Rent paid - 10% of basic
    """
    metro_pct = 0.50 if is_metro else 0.40
    exempt = min(
        hra_received_annual,
        basic_salary_annual * metro_pct,
        max(0, rent_paid_annual - basic_salary_annual * 0.10),
    )
    return round(exempt)


# ── XIRR (simple Newton-Raphson) ──────────────────────────────────────────────

def xirr(cash_flows: list[tuple[date, float]], guess: float = 0.12) -> float | None:
    """
    Calculate XIRR for a list of (date, amount) tuples.
    Negative amounts = investments; positive = redemptions/current value.
    Returns annualised rate or None if it doesn't converge.
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    dates = [cf[0] for cf in cash_flows]
    amounts = [cf[1] for cf in cash_flows]
    t0 = dates[0]
    days = [(d - t0).days / 365.0 for d in dates]

    r = guess
    for _ in range(200):
        f = sum(a / math.pow(1 + r, t) for a, t in zip(amounts, days))
        df = sum(-t * a / math.pow(1 + r, t + 1) for a, t in zip(amounts, days))
        if df == 0:
            break
        r_new = r - f / df
        if abs(r_new - r) < 1e-7:
            return round(r_new * 100, 2)
        r = r_new

    return None


# ── Portfolio overlap (simplified Jaccard on fund name tokens) ────────────────

def portfolio_overlap_score(fund_names: list[str]) -> float:
    """
    Naive overlap heuristic: what % of holdings share a category
    (large-cap / mid-cap / etc.). Real overlap needs holdings data.
    Returns 0-100 overlap score.
    """
    categories = []
    keywords = {
        "large cap": ["large cap", "bluechip", "top 100", "nifty 50"],
        "mid cap": ["mid cap", "midcap", "emerging"],
        "small cap": ["small cap", "smallcap"],
        "elss": ["elss", "tax saver", "tax saving"],
        "index": ["index", "nifty", "sensex", "etf"],
        "debt": ["debt", "liquid", "overnight", "gilt", "bond", "income"],
    }
    for name in fund_names:
        lower = name.lower()
        for cat, kw_list in keywords.items():
            if any(k in lower for k in kw_list):
                categories.append(cat)
                break
        else:
            categories.append("other")

    if not categories:
        return 0.0
    from collections import Counter
    counts = Counter(categories)
    duplicates = sum(v - 1 for v in counts.values())
    return round(duplicates / len(categories) * 100, 1)


# ── Money health score ────────────────────────────────────────────────────────

def compute_health_score(
    monthly_income: float,
    monthly_expenses: float,
    emergency_fund: float,
    life_cover: float,
    health_cover: float,
    debt_emi: float,
    investment_monthly: float,
    has_term_plan: bool,
    age: int,
) -> dict[str, Any]:
    """
    Score across 6 dimensions (each 0-100, weighted average = total score).
    Dimensions: emergency, insurance, investment, debt, tax_efficiency, retirement.
    """
    scores: dict[str, float] = {}

    # 1. Emergency preparedness (target: 6 months of expenses)
    months_covered = emergency_fund / monthly_expenses if monthly_expenses else 0
    scores["emergency"] = min(100, months_covered / 6 * 100)

    # 2. Insurance coverage
    life_multiple = life_cover / (monthly_income * 12) if monthly_income else 0
    life_score = min(100, life_multiple / 10 * 100)  # target 10× income
    health_score_val = min(100, health_cover / 500_000 * 100)  # target 5L cover
    scores["insurance"] = (life_score * 0.6 + health_score_val * 0.4)
    if has_term_plan:
        scores["insurance"] = min(100, scores["insurance"] + 10)

    # 3. Investment discipline (target: save 20% of income)
    savings_rate = investment_monthly / monthly_income if monthly_income else 0
    scores["investment"] = min(100, savings_rate / 0.20 * 100)

    # 4. Debt health (target: EMI/income < 40%)
    emi_ratio = debt_emi / monthly_income if monthly_income else 0
    scores["debt"] = max(0, 100 - emi_ratio / 0.40 * 100)

    # 5. Tax efficiency (placeholder — full analysis in tax wizard)
    scores["tax_efficiency"] = 60.0  # default medium; agent enriches this

    # 6. Retirement readiness (age-based: closer to 60 = harder to catch up)
    if age < 30:
        scores["retirement"] = 80.0
    elif age < 40:
        scores["retirement"] = 65.0
    elif age < 50:
        scores["retirement"] = 45.0
    else:
        scores["retirement"] = 30.0

    weights = {
        "emergency": 0.20,
        "insurance": 0.20,
        "investment": 0.25,
        "debt": 0.15,
        "tax_efficiency": 0.10,
        "retirement": 0.10,
    }
    total = sum(scores[k] * w for k, w in weights.items())

    return {
        "total_score": round(total, 1),
        "grade": _score_grade(total),
        "dimensions": {k: round(v, 1) for k, v in scores.items()},
        "savings_rate_pct": round(savings_rate * 100, 1),
        "emi_income_ratio_pct": round(emi_ratio * 100, 1),
    }


def _score_grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"
