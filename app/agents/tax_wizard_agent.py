"""
Tax Wizard Agent
Old vs new regime comparison, deduction gap analysis,
and personalised tax-saving investment recommendations.
"""
from __future__ import annotations
from typing import Any

from app.agents.base_agent import BaseAgent
from app.database.models import AgentType, FinancialProfile
from app.services.financial_calculator import tax_comparison, hra_exemption


class TaxWizardAgent(BaseAgent):
    agent_type = AgentType.tax_wizard

    def _system_prompt(self) -> str:
        return """You are a Chartered Accountant specialising in Indian income tax for salaried individuals.
You receive a detailed tax computation and must produce an actionable tax optimisation report.

Rules:
- Reference only current FY 2024-25 rules and slabs.
- Prioritise deductions by ROI: NPS 80CCD(1B) > ELSS 80C > PPF 80C > Term Insurance premium.
- Show exact rupee savings for each recommendation.
- Flag commonly missed deductions (home loan interest, HRA, LTA).
- Never suggest tax evasion — only legal optimisation.
- Respond ONLY with valid JSON. No markdown, no extra text.

JSON structure:
{
  "regime_comparison": {
    "old_tax": number, "new_tax": number,
    "recommended": "old|new",
    "savings_with_recommended": number,
    "reason": "string"
  },
  "deduction_gaps": [
    {"section": "string", "max_allowed": number, "currently_used": number,
     "gap": number, "potential_saving": number, "instruments": ["string"]}
  ],
  "tax_saving_plan": [
    {"priority": number, "action": "string", "section": "string",
     "invest_amount": number, "tax_saved": number, "deadline": "string"}
  ],
  "hra_analysis": {
    "exempt_amount": number, "taxable_hra": number, "optimization_tip": "string"
  },
  "total_potential_saving": number,
  "missed_deductions": ["string"],
  "advance_tax_schedule": [
    {"quarter": "string", "due_date": "string", "amount_due": number}
  ]
}"""

    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Collect inputs
        gross = payload.get("annual_income") or (
            (profile.monthly_income or 0) * 12 if profile else 0
        )
        basic_annual = payload.get("basic_salary_annual") or (
            (profile.basic_salary or 0) * 12 if profile else gross * 0.4
        )
        hra_received = payload.get("hra_received_annual") or (
            (profile.hra_received or 0) * 12 if profile else basic_annual * 0.5
        )
        rent_paid = payload.get("rent_paid_annual") or (
            (profile.rent_paid or 0) * 12 if profile else 0
        )
        section_80c = payload.get("section_80c_used") or (
            profile.section_80c_used if profile else 0
        ) or 0
        nps = payload.get("nps_contribution") or (
            profile.nps_contribution if profile else 0
        ) or 0
        home_loan_int = payload.get("home_loan_interest") or (
            profile.home_loan_interest if profile else 0
        ) or 0
        is_metro = payload.get("is_metro_city", True)

        # HRA exemption
        hra_exempt = hra_exemption(basic_annual, hra_received, rent_paid, is_metro) if rent_paid else 0

        # Tax comparison
        comparison = tax_comparison(
            gross_annual=gross,
            deductions_80c=section_80c,
            nps_80ccd=nps,
            home_loan_interest=home_loan_int,
            hra_exempt=hra_exempt,
        )

        # Deduction gaps
        gaps = {
            "80c_gap": max(0, 150_000 - section_80c),
            "nps_gap": max(0, 50_000 - nps),
            "home_loan_gap": max(0, 200_000 - home_loan_int),
            "hra_exempt": hra_exempt,
        }

        # Tax rate (marginal, for saving calculation)
        marginal_rate = _marginal_rate(gross)

        potential_saving = (
            gaps["80c_gap"] * marginal_rate
            + gaps["nps_gap"] * marginal_rate
            + gaps["home_loan_gap"] * marginal_rate
        )

        # Advance tax (if total tax > 10,000 and not TDS-covered)
        annual_tax = comparison["old_regime"]["total_tax"] if comparison["recommendation"] == "old_regime" \
            else comparison["new_regime"]["total_tax"]
        advance_tax = _compute_advance_tax(annual_tax)

        return {
            "comparison": comparison,
            "deduction_gaps": gaps,
            "hra_exempt": hra_exempt,
            "marginal_rate": marginal_rate,
            "potential_saving": round(potential_saving),
            "advance_tax": advance_tax,
            "inputs": {
                "gross_annual": gross,
                "basic_annual": basic_annual,
                "hra_received": hra_received,
                "rent_paid": rent_paid,
                "section_80c_used": section_80c,
                "nps_contribution": nps,
                "home_loan_interest": home_loan_int,
            },
        }

    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        c = computed.get("comparison", {})
        inp = computed.get("inputs", {})
        gaps = computed.get("deduction_gaps", {})

        return f"""Tax computation for FY 2024-25:

Income:
- Gross annual income: {self._fmt_inr(inp.get('gross_annual', 0))}
- Basic salary (annual): {self._fmt_inr(inp.get('basic_annual', 0))}
- HRA received: {self._fmt_inr(inp.get('hra_received', 0))}
- Rent paid: {self._fmt_inr(inp.get('rent_paid', 0))}
- HRA exemption calculated: {self._fmt_inr(computed.get('hra_exempt', 0))}

Current deductions used:
- Section 80C: {self._fmt_inr(inp.get('section_80c_used', 0))} (gap: {self._fmt_inr(gaps.get('80c_gap', 0))})
- NPS 80CCD(1B): {self._fmt_inr(inp.get('nps_contribution', 0))} (gap: {self._fmt_inr(gaps.get('nps_gap', 0))})
- Home loan interest 24(b): {self._fmt_inr(inp.get('home_loan_interest', 0))} (gap: {self._fmt_inr(gaps.get('home_loan_gap', 0))})

Tax comparison:
- Old regime tax: {self._fmt_inr(c.get('old_regime', {}).get('total_tax', 0))} (effective rate: {c.get('old_regime', {}).get('effective_rate', 0)}%)
- New regime tax: {self._fmt_inr(c.get('new_regime', {}).get('total_tax', 0))} (effective rate: {c.get('new_regime', {}).get('effective_rate', 0)}%)
- Recommended: {c.get('recommendation', 'N/A')} — saves {self._fmt_inr(abs(c.get('saving_with_old', 0)))}
- Reason: {c.get('reason', '')}

Potential additional tax saving: {self._fmt_inr(computed.get('potential_saving', 0))}
Marginal tax rate: {computed.get('marginal_rate', 0) * 100:.0f}%

Advance tax schedule:
{chr(10).join(f"  Q{q['quarter']}: {self._fmt_inr(q['amount'])} due {q['due_date']}" for q in computed.get('advance_tax', []))}

Additional context: {payload.get('additional_context', 'None')}

Generate the complete tax optimisation JSON report."""


def _marginal_rate(gross: float) -> float:
    if gross <= 300_000:
        return 0.0
    if gross <= 600_000:
        return 0.05
    if gross <= 900_000:
        return 0.10
    if gross <= 1_200_000:
        return 0.15
    if gross <= 1_500_000:
        return 0.20
    return 0.30


def _compute_advance_tax(annual_tax: float) -> list[dict]:
    if annual_tax < 10_000:
        return []
    return [
        {"quarter": "1", "due_date": "15 Jun 2025", "amount": round(annual_tax * 0.15)},
        {"quarter": "2", "due_date": "15 Sep 2025", "amount": round(annual_tax * 0.45 - annual_tax * 0.15)},
        {"quarter": "3", "due_date": "15 Dec 2025", "amount": round(annual_tax * 0.75 - annual_tax * 0.45)},
        {"quarter": "4", "due_date": "15 Mar 2026", "amount": round(annual_tax * 1.0 - annual_tax * 0.75)},
    ]
