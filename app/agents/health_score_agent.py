"""
Money Health Score Agent
Gives a 0-100 score across 6 financial wellness dimensions
with specific, actionable recommendations for each gap.
"""
from __future__ import annotations
from typing import Any

from app.agents.base_agent import BaseAgent
from app.database.models import AgentType, FinancialProfile
from app.services.financial_calculator import compute_health_score, emergency_fund_gap


class HealthScoreAgent(BaseAgent):
    agent_type = AgentType.health_score

    def _system_prompt(self) -> str:
        return """You are an expert Indian personal finance advisor embedded in the ET AI Money Mentor platform.
Your task is to analyse a user's Money Health Score across 6 dimensions and provide:
1. A brief overall assessment (2-3 sentences)
2. Top 3 priority actions ranked by financial impact
3. One specific, actionable fix for each weak dimension (score < 60)

Rules:
- All amounts in Indian Rupees (₹)
- Use Indian financial products: PPF, ELSS, NPS, term insurance, etc.
- Be direct and specific — avoid generic advice
- Tone: friendly but urgent where scores are low
- Respond ONLY with valid JSON. No markdown, no extra text.

JSON structure:
{
  "overall_assessment": "string",
  "priority_actions": [
    {"rank": 1, "action": "string", "monthly_impact": "string", "urgency": "high|medium|low"}
  ],
  "dimension_fixes": {
    "emergency": {"issue": "string", "fix": "string", "target": "string"},
    "insurance": {"issue": "string", "fix": "string", "target": "string"},
    "investment": {"issue": "string", "fix": "string", "target": "string"},
    "debt": {"issue": "string", "fix": "string", "target": "string"},
    "tax_efficiency": {"issue": "string", "fix": "string", "target": "string"},
    "retirement": {"issue": "string", "fix": "string", "target": "string"}
  },
  "quick_wins": ["string", "string", "string"]
}"""

    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Merge profile data with payload overrides
        income = payload.get("monthly_income") or (profile.monthly_income if profile else 0) or 0
        expenses = payload.get("monthly_expenses") or (profile.monthly_expenses if profile else 0) or 0
        emergency = payload.get("emergency_fund", 0) or (profile.existing_fd if profile else 0) or 0
        life_cover = payload.get("life_cover") or (profile.life_cover if profile else 0) or 0
        health_cover = payload.get("health_cover") or (profile.health_cover if profile else 0) or 0
        debt_emi = payload.get("debt_emi", 0)
        investment_monthly = payload.get("monthly_investment", 0)
        has_term = payload.get("has_term_plan") or (profile.has_term_plan if profile else False)
        age = payload.get("age") or (profile.age if profile else 30) or 30

        scores = compute_health_score(
            monthly_income=income,
            monthly_expenses=expenses,
            emergency_fund=emergency,
            life_cover=life_cover,
            health_cover=health_cover,
            debt_emi=debt_emi,
            investment_monthly=investment_monthly,
            has_term_plan=has_term,
            age=age,
        )

        ef_gap = emergency_fund_gap(
            monthly_expenses=expenses,
            existing_liquid=emergency,
        )

        return {
            **scores,
            "emergency_fund_analysis": ef_gap,
            "inputs": {
                "monthly_income": income,
                "monthly_expenses": expenses,
                "age": age,
            },
        }

    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        dims = computed.get("dimensions", {})
        ef = computed.get("emergency_fund_analysis", {})
        inputs = computed.get("inputs", {})

        weak = [k for k, v in dims.items() if v < 60]

        return f"""User financial snapshot:
- Age: {inputs.get('age')}
- Monthly income: {self._fmt_inr(inputs.get('monthly_income', 0))}
- Monthly expenses: {self._fmt_inr(inputs.get('monthly_expenses', 0))}
- Savings rate: {computed.get('savings_rate_pct')}%
- EMI-to-income ratio: {computed.get('emi_income_ratio_pct')}%

Money Health Score: {computed.get('total_score')}/100 (Grade {computed.get('grade')})

Dimension scores (0-100):
- Emergency preparedness: {dims.get('emergency', 0):.0f} — {ef.get('months_covered')} months covered, gap = {self._fmt_inr(ef.get('gap', 0))}
- Insurance coverage: {dims.get('insurance', 0):.0f}
- Investment discipline: {dims.get('investment', 0):.0f}
- Debt health: {dims.get('debt', 0):.0f}
- Tax efficiency: {dims.get('tax_efficiency', 0):.0f}
- Retirement readiness: {dims.get('retirement', 0):.0f}

Weak dimensions (score < 60): {weak}

Additional context from user: {payload.get('additional_context', 'None')}

Provide the analysis JSON as described in your instructions."""
