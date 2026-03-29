"""
FIRE Path Planner Agent
Builds a month-by-month financial roadmap toward Financial Independence.
Computes SIP amounts, asset allocation shifts, and milestone targets.
"""
from __future__ import annotations
from typing import Any

from app.agents.base_agent import BaseAgent
from app.database.models import AgentType, FinancialProfile
from app.services.financial_calculator import (
    retirement_corpus_needed,
    sip_future_value,
    required_sip,
    inflation_adjusted,
    tax_comparison,
)


class FIREPlannerAgent(BaseAgent):
    agent_type = AgentType.fire_planner

    def _system_prompt(self) -> str:
        return """You are India's most rigorous FIRE (Financial Independence, Retire Early) planning expert.
You receive pre-computed financial numbers and must produce a structured, actionable FIRE roadmap.

Rules:
- All amounts in Indian Rupees (₹). Use Cr/L notation for large numbers.
- Every SIP recommendation must name a specific fund category (not a specific fund name).
- Phase the plan into 5-year milestones.
- Include NPS, PPF, ELSS allocation for tax optimization.
- Account for lifestyle inflation of 6% per year.
- Flag risks: market downturns, income disruption, medical emergencies.
- Respond ONLY with valid JSON. No markdown, no preamble.

JSON structure:
{
  "fire_summary": {
    "corpus_needed": number,
    "years_to_fire": number,
    "fire_date": "YYYY",
    "monthly_sip_required": number,
    "current_gap_per_month": number
  },
  "asset_allocation": {
    "current_phase": {"equity": %, "debt": %, "gold": %},
    "5_years_out": {"equity": %, "debt": %, "gold": %},
    "at_retirement": {"equity": %, "debt": %, "gold": %}
  },
  "sip_breakdown": [
    {"category": "string", "monthly_amount": number, "rationale": "string", "tax_benefit": "string"}
  ],
  "milestones": [
    {"year": "YYYY", "age": number, "target_corpus": number, "key_action": "string"}
  ],
  "insurance_gaps": ["string"],
  "risks": [
    {"risk": "string", "mitigation": "string"}
  ],
  "annual_review_checklist": ["string"]
}"""

    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        age = payload.get("age") or (profile.age if profile else 30) or 30
        income = payload.get("monthly_income") or (profile.monthly_income if profile else 0) or 0
        expenses = payload.get("monthly_expenses") or (profile.monthly_expenses if profile else 0) or 0
        target_retire_age = payload.get("target_retirement_age") or (
            profile.target_retirement_age if profile else 45
        ) or 45
        monthly_retire_exp = payload.get("monthly_retirement_expenses") or (
            profile.monthly_retirement_expenses if profile else expenses
        ) or expenses
        existing_corpus = payload.get("existing_corpus") or (
            (profile.existing_mutual_funds or 0)
            + (profile.existing_stocks or 0)
            + (profile.existing_ppf or 0)
            + (profile.existing_nps or 0)
        ) if profile else 0

        # Core FIRE math
        retire_data = retirement_corpus_needed(
            monthly_expenses_today=monthly_retire_exp,
            current_age=age,
            retirement_age=target_retire_age,
        )

        # Existing corpus future value at 10% CAGR
        years = retire_data["years_to_retire"]
        existing_fv = existing_corpus * ((1 + 0.10) ** years) if existing_corpus else 0

        # Remaining corpus to build via SIP
        remaining_corpus = max(0, retire_data["corpus_needed"] - existing_fv)
        sip_10pct = required_sip(remaining_corpus, 0.10, years) if years > 0 else 0
        sip_12pct = required_sip(remaining_corpus, 0.12, years) if years > 0 else 0

        # Savings available
        monthly_savings = income - expenses
        gap = max(0, sip_12pct - monthly_savings)

        # 5-year milestones
        milestones = []
        for yr in range(5, years + 1, 5):
            milestone_age = age + yr
            target = sip_future_value(sip_12pct, 0.12, yr) + existing_fv
            milestones.append({
                "years_from_now": yr,
                "age": milestone_age,
                "target_corpus": round(target),
            })

        # Tax comparison on current income
        annual_income = income * 12
        tax_data = tax_comparison(annual_income) if annual_income else {}

        return {
            "retire_math": retire_data,
            "existing_corpus": round(existing_corpus),
            "existing_corpus_fv": round(existing_fv),
            "remaining_corpus": round(remaining_corpus),
            "sip_required_12pct": round(sip_12pct),
            "sip_required_10pct": round(sip_10pct),
            "monthly_savings_available": round(monthly_savings),
            "monthly_gap": round(gap),
            "milestones_data": milestones,
            "tax_data": tax_data,
            "inputs": {
                "age": age,
                "monthly_income": income,
                "monthly_expenses": expenses,
                "target_retirement_age": target_retire_age,
            },
        }

    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        rm = computed.get("retire_math", {})
        inp = computed.get("inputs", {})
        tax = computed.get("tax_data", {})

        return f"""User FIRE planning data:

Demographics:
- Age: {inp.get('age')} | Target FIRE age: {inp.get('target_retirement_age')}
- Monthly income: {self._fmt_inr(inp.get('monthly_income', 0))}
- Monthly expenses: {self._fmt_inr(inp.get('monthly_expenses', 0))}
- Monthly savings available: {self._fmt_inr(computed.get('monthly_savings_available', 0))}

FIRE corpus math:
- Corpus needed at retirement: {self._fmt_inr(rm.get('corpus_needed', 0))}
- Monthly expenses at retirement (inflation-adjusted): {self._fmt_inr(rm.get('monthly_expenses_at_retire', 0))}
- Existing investments (today): {self._fmt_inr(computed.get('existing_corpus', 0))}
- Existing investments (future value at retirement): {self._fmt_inr(computed.get('existing_corpus_fv', 0))}
- Remaining corpus to build via SIP: {self._fmt_inr(computed.get('remaining_corpus', 0))}
- SIP required @ 12% CAGR: {self._fmt_inr(computed.get('sip_required_12pct', 0))}/month
- SIP required @ 10% CAGR: {self._fmt_inr(computed.get('sip_required_10pct', 0))}/month
- Current SIP gap: {self._fmt_inr(computed.get('monthly_gap', 0))}/month

Tax situation:
- Annual income: {self._fmt_inr(inp.get('monthly_income', 0) * 12)}
- Recommended regime: {tax.get('recommendation', 'N/A')} (saves {self._fmt_inr(abs(tax.get('saving_with_old', 0)))}/year)

Milestones:
{chr(10).join(f"  Year +{m['years_from_now']} (Age {m['age']}): Target corpus {self._fmt_inr(m['target_corpus'])}" for m in computed.get('milestones_data', []))}

Risk profile: {payload.get('risk_profile') or (profile.risk_profile.value if profile and profile.risk_profile else 'moderate')}
Life goals: {payload.get('life_goals', 'Not specified')}

Build the complete FIRE roadmap JSON."""
