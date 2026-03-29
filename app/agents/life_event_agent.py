"""
Life Event Financial Advisor Agent
Handles specific life-event-triggered financial decisions:
bonus, inheritance, marriage, new baby, job change, home purchase.
"""
from __future__ import annotations
from typing import Any

from app.agents.base_agent import BaseAgent
from app.database.models import AgentType, FinancialProfile
from app.services.financial_calculator import (
    lumpsum_future_value,
    tax_comparison,
    required_sip,
)

LIFE_EVENTS = {
    "bonus": "Lump-sum windfall allocation",
    "inheritance": "Inheritance / large windfall",
    "marriage": "Marriage financial planning",
    "new_baby": "New baby financial preparation",
    "job_change": "Job change / salary hike planning",
    "home_purchase": "Home purchase decision",
    "retirement": "Pre-retirement transition",
    "medical_emergency": "Medical emergency financial recovery",
}


class LifeEventAgent(BaseAgent):
    agent_type = AgentType.life_event

    def _system_prompt(self) -> str:
        return """You are India's premier life-event financial planner.
A user has experienced a significant financial life event and needs an immediate action plan.

Rules:
- Prioritise emergency/liquidity before wealth-building in every event.
- For windfall events (bonus, inheritance): apply the 50/30/20 windfall rule unless profile says otherwise.
- For liability events (marriage, baby, home): stress-test the budget and flag EMI risk.
- Recommendations must be event-specific and time-bound (30-day, 90-day, 1-year).
- Always include an insurance review for every life event.
- Respond ONLY with valid JSON. No markdown, no extra text.

JSON structure:
{
  "event_summary": "string",
  "immediate_actions": [
    {"timeline": "Within 7 days", "action": "string", "amount": number or null, "priority": "critical|high|medium"}
  ],
  "allocation_plan": {
    "total_amount": number,
    "buckets": [
      {"bucket": "string", "amount": number, "pct": number, "instrument": "string", "rationale": "string"}
    ]
  },
  "insurance_review": {
    "life_cover_adequate": boolean,
    "health_cover_adequate": boolean,
    "gaps": ["string"]
  },
  "tax_implications": "string",
  "30_day_checklist": ["string"],
  "90_day_goals": ["string"],
  "1_year_milestone": "string",
  "risks_to_avoid": ["string"]
}"""

    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event = payload.get("event", "bonus")
        amount = payload.get("event_amount", 0) or 0
        income = payload.get("monthly_income") or (profile.monthly_income if profile else 0) or 0
        expenses = payload.get("monthly_expenses") or (profile.monthly_expenses if profile else 0) or 0
        age = payload.get("age") or (profile.age if profile else 30) or 30

        computed: dict[str, Any] = {
            "event": event,
            "event_label": LIFE_EVENTS.get(event, event),
            "amount": amount,
        }

        if event in ("bonus", "inheritance") and amount > 0:
            # 50/30/20 windfall split
            emergency_top_up = amount * 0.20
            investment = amount * 0.50
            debt_repay = amount * 0.30
            # FV of the 50% invested at 12% for 10 years
            fv_10yr = lumpsum_future_value(investment, 0.12, 10)
            computed["windfall_split"] = {
                "emergency_top_up": round(emergency_top_up),
                "debt_repayment": round(debt_repay),
                "investment": round(investment),
                "investment_fv_10yr": round(fv_10yr),
            }

        if event == "new_baby":
            # Education corpus: need ~₹50L in 18 years (inflation-adjusted to ₹2Cr+)
            education_corpus = 20_000_000  # 2 Cr inflation-adjusted
            edu_sip = required_sip(education_corpus, 0.12, 18)
            computed["education_planning"] = {
                "corpus_target": education_corpus,
                "monthly_sip": round(edu_sip),
            }

        if event == "home_purchase":
            home_value = payload.get("home_value", 0) or 0
            down_payment = home_value * 0.20
            loan_amount = home_value - down_payment
            emi_approx = loan_amount * 0.0075 / (1 - (1.0075 ** -240))  # 8% 20yr
            emi_to_income = emi_approx / income if income else 0
            computed["home_analysis"] = {
                "home_value": home_value,
                "down_payment_needed": round(down_payment),
                "loan_amount": round(loan_amount),
                "approx_emi": round(emi_approx),
                "emi_to_income_pct": round(emi_to_income * 100, 1),
                "affordable": emi_to_income < 0.40,
            }

        # Tax on windfall
        if event in ("bonus", "inheritance") and amount > 0:
            annual_income = income * 12
            tax_data = tax_comparison(annual_income + amount)
            computed["tax_on_windfall"] = {
                "applicable_tax_rate": f"{_marginal_rate(annual_income) * 100:.0f}%",
                "approx_tax_on_bonus": round(amount * _marginal_rate(annual_income)),
            }

        computed["profile_snapshot"] = {
            "age": age,
            "monthly_income": income,
            "monthly_expenses": expenses,
        }

        return computed

    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        event = computed.get("event", "bonus")
        amount = computed.get("amount", 0)
        ps = computed.get("profile_snapshot", {})

        sections = [
            f"Life event: {computed.get('event_label')}",
            f"Event amount: {self._fmt_inr(amount)}",
            f"User age: {ps.get('age')} | Monthly income: {self._fmt_inr(ps.get('monthly_income', 0))} "
            f"| Monthly expenses: {self._fmt_inr(ps.get('monthly_expenses', 0))}",
            f"Risk profile: {payload.get('risk_profile') or (profile.risk_profile.value if profile and profile.risk_profile else 'moderate')}",
        ]

        if "windfall_split" in computed:
            ws = computed["windfall_split"]
            sections.append(
                f"\nSuggested windfall split:\n"
                f"  Emergency top-up: {self._fmt_inr(ws['emergency_top_up'])}\n"
                f"  Debt repayment: {self._fmt_inr(ws['debt_repayment'])}\n"
                f"  Investment: {self._fmt_inr(ws['investment'])} "
                f"(FV in 10 years @ 12%: {self._fmt_inr(ws['investment_fv_10yr'])})"
            )
        if "education_planning" in computed:
            ep = computed["education_planning"]
            sections.append(
                f"\nChild education corpus needed: {self._fmt_inr(ep['corpus_target'])} in 18 years\n"
                f"Monthly SIP required: {self._fmt_inr(ep['monthly_sip'])}"
            )
        if "home_analysis" in computed:
            ha = computed["home_analysis"]
            sections.append(
                f"\nHome purchase analysis:\n"
                f"  Home value: {self._fmt_inr(ha['home_value'])}\n"
                f"  Down payment needed: {self._fmt_inr(ha['down_payment_needed'])}\n"
                f"  Loan amount: {self._fmt_inr(ha['loan_amount'])}\n"
                f"  Approx EMI: {self._fmt_inr(ha['approx_emi'])}/month\n"
                f"  EMI-to-income: {ha['emi_to_income_pct']}% ({'OK' if ha['affordable'] else 'RISKY — >40%'})"
            )
        if "tax_on_windfall" in computed:
            tw = computed["tax_on_windfall"]
            sections.append(
                f"\nTax on windfall: {tw['applicable_tax_rate']} marginal rate "
                f"≈ {self._fmt_inr(tw['approx_tax_on_bonus'])} tax"
            )

        sections.append(f"\nAdditional context: {payload.get('additional_context', 'None')}")
        sections.append("\nGenerate the complete life event action plan JSON.")

        return "\n".join(sections)


def _marginal_rate(gross: float) -> float:
    if gross <= 500_000:
        return 0.0
    if gross <= 1_000_000:
        return 0.20
    return 0.30
