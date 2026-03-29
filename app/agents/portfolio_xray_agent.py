"""
Portfolio X-Ray Agent
Analyses a mutual fund portfolio from CAMS statement text/PDF.
Computes XIRR, overlap, expense drag, and generates rebalancing plan.
"""
from __future__ import annotations
from typing import Any
from datetime import date

from app.agents.base_agent import BaseAgent
from app.database.models import AgentType, FinancialProfile
from app.services.pdf_parser import parse_cams_text, summarise_holdings
from app.services.financial_calculator import portfolio_overlap_score, xirr as compute_xirr


class PortfolioXRayAgent(BaseAgent):
    agent_type = AgentType.portfolio_xray

    def _system_prompt(self) -> str:
        return """You are a CFA-level mutual fund analyst for Indian retail investors.
You receive a parsed portfolio and must provide a comprehensive X-Ray report.

Rules:
- Be specific about fund categories and their roles in the portfolio.
- Flag concentration risk, overlap, and expense ratio drag in rupee terms.
- Rebalancing recommendations must reference specific fund categories (not fund names).
- Use SEBI fund category names: Large Cap, Mid Cap, Small Cap, Flexi Cap, ELSS, Index, etc.
- Show the math: how much the expense ratio drag costs per year in rupees.
- Respond ONLY with valid JSON. No markdown, no extra text.

JSON structure:
{
  "portfolio_summary": {
    "total_invested": number, "total_current_value": number,
    "absolute_gain": number, "gain_pct": number,
    "xirr": number or null, "fund_count": number
  },
  "health_signals": {
    "overlap_score": number,
    "overlap_verdict": "low|medium|high",
    "concentration_risk": "string",
    "expense_drag_annual_inr": number,
    "expense_drag_verdict": "string"
  },
  "category_breakdown": [
    {"category": "string", "allocation_pct": number, "ideal_pct": number, "verdict": "underweight|ok|overweight"}
  ],
  "fund_ratings": [
    {"fund_name": "string", "verdict": "keep|review|exit", "reason": "string", "action": "string"}
  ],
  "rebalancing_plan": {
    "overall_action": "string",
    "steps": ["string"],
    "tax_considerations": "string"
  },
  "benchmark_comparison": "string",
  "top_insights": ["string"]
}"""

    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw_text = payload.get("cams_text", "")
        holdings = parse_cams_text(raw_text) if raw_text else []

        summary = summarise_holdings(holdings)

        # Overlap analysis on fund names
        fund_names = [h["fund_name"] for h in holdings]
        overlap = portfolio_overlap_score(fund_names)

        # Approximate XIRR using invested vs current and rough 3yr holding period
        # (Real XIRR needs transaction history; this is a proxy)
        xirr_val = None
        if summary["total_invested"] > 0 and summary["total_current_value"] > 0:
            today = date.today()
            approx_start = date(today.year - 3, today.month, today.day)
            cf = [
                (approx_start, -summary["total_invested"]),
                (today, summary["total_current_value"]),
            ]
            xirr_val = compute_xirr(cf)

        # Expense ratio drag (assume average 1.5% if not available in CAMS text)
        avg_expense_ratio = 0.015
        expense_drag_inr = summary["total_current_value"] * avg_expense_ratio

        # Category allocation from parsed holdings
        categories: dict[str, float] = {}
        for h in holdings:
            cat = _classify_fund(h["fund_name"])
            categories[cat] = categories.get(cat, 0) + (h.get("current_value") or 0)
        total_val = summary["total_current_value"] or 1
        category_pct = {k: round(v / total_val * 100, 1) for k, v in categories.items()}

        return {
            "holdings": holdings,
            "summary": summary,
            "overlap_score": overlap,
            "xirr": xirr_val,
            "expense_drag_annual_inr": round(expense_drag_inr),
            "category_allocation": category_pct,
        }

    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        s = computed.get("summary", {})
        holdings = computed.get("holdings", [])

        holdings_text = "\n".join(
            f"  • {h['fund_name']} | Invested: {self._fmt_inr(h.get('invested_amount') or 0)} "
            f"| Value: {self._fmt_inr(h.get('current_value') or 0)} "
            f"| Gain: {h.get('gain_pct', 'N/A')}%"
            for h in holdings[:20]  # cap to avoid prompt overflow
        )

        cat_text = "\n".join(
            f"  {cat}: {pct}%"
            for cat, pct in computed.get("category_allocation", {}).items()
        )

        return f"""Portfolio overview:
- Total invested: {self._fmt_inr(s.get('total_invested', 0))}
- Current value: {self._fmt_inr(s.get('total_current_value', 0))}
- Absolute gain: {self._fmt_inr(s.get('absolute_gain', 0))} ({s.get('gain_pct', 0):.1f}%)
- Approximate XIRR: {computed.get('xirr')}%
- Fund count: {s.get('fund_count', 0)}
- Overlap score: {computed.get('overlap_score')}/100 (higher = more overlap)
- Estimated expense drag: {self._fmt_inr(computed.get('expense_drag_annual_inr', 0))}/year

Category allocation:
{cat_text}

Individual holdings:
{holdings_text}

Investor profile:
- Age: {profile.age if profile else payload.get('age', 'unknown')}
- Risk profile: {profile.risk_profile.value if profile and profile.risk_profile else payload.get('risk_profile', 'moderate')}

Generate the complete X-Ray JSON report."""


def _classify_fund(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["elss", "tax saver", "tax saving"]):
        return "ELSS"
    if any(k in n for k in ["index", "nifty", "sensex", "etf"]):
        return "Index/ETF"
    if any(k in n for k in ["liquid", "overnight", "money market"]):
        return "Liquid/Overnight"
    if any(k in n for k in ["debt", "gilt", "bond", "income", "credit"]):
        return "Debt"
    if any(k in n for k in ["small cap", "smallcap"]):
        return "Small Cap"
    if any(k in n for k in ["mid cap", "midcap"]):
        return "Mid Cap"
    if any(k in n for k in ["large cap", "bluechip", "top 100"]):
        return "Large Cap"
    if any(k in n for k in ["flexi", "multi cap", "multicap", "focused"]):
        return "Flexi/Multi Cap"
    if any(k in n for k in ["hybrid", "balanced", "aggressive hybrid"]):
        return "Hybrid"
    if any(k in n for k in ["international", "global", "us equity"]):
        return "International"
    return "Other"
