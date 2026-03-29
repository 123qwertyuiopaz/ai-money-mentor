"""
Report generation endpoint.
Runs all agents in sequence and produces a professional PDF report.
"""
import json
from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import CurrentUser, DBSession
from app.database.models import FinancialProfile, Portfolio, AgentSession, AgentType
from app.agents.health_score_agent import HealthScoreAgent
from app.agents.fire_planner_agent import FIREPlannerAgent
from app.agents.tax_wizard_agent import TaxWizardAgent
from app.agents.portfolio_xray_agent import PortfolioXRayAgent
from app.services.report_generator import generate_report

router = APIRouter(prefix="/report", tags=["Report"])

_health_agent = HealthScoreAgent()
_fire_agent   = FIREPlannerAgent()
_tax_agent    = TaxWizardAgent()
_xray_agent   = PortfolioXRayAgent()


@router.post("/generate")
def generate_financial_report(
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Run all agents against the user's saved profile and return a
    professional multi-page PDF report as a binary download.
    """
    # Load profile
    profile = db.query(FinancialProfile).filter(
        FinancialProfile.user_id == current_user.id
    ).first()
    profile_dict = {}
    if profile:
        profile_dict = {
            col.name: getattr(profile, col.name)
            for col in profile.__table__.columns
            if col.name not in ("id", "user_id")
        }

    user_name = current_user.full_name or current_user.email.split("@")[0]

    # ── Run agents (best-effort — skip on failure) ───────────────────────────
    health_data = portfolio_data = fire_data = tax_data = None

    try:
        health_data = _health_agent.run(db, current_user, {})
    except Exception:
        pass

    try:
        fire_data = _fire_agent.run(db, current_user, {})
    except Exception:
        pass

    try:
        annual_income = (profile.monthly_income or 0) * 12 if profile else 0
        tax_data = _tax_agent.run(db, current_user, {"annual_income": annual_income or None})
    except Exception:
        pass

    # Portfolio X-Ray — only if user has uploaded a CAMS statement
    try:
        port = db.query(Portfolio).filter(
            Portfolio.user_id == current_user.id
        ).order_by(Portfolio.created_at.desc()).first()
        if port and port.raw_text:
            portfolio_data = _xray_agent.run(db, current_user, {"cams_text": port.raw_text})
    except Exception:
        pass

    # ── Generate PDF ─────────────────────────────────────────────────────────
    pdf_bytes = generate_report(
        user_name=user_name,
        profile=profile_dict,
        health_data=health_data,
        fire_data=fire_data,
        tax_data=tax_data,
        portfolio_data=portfolio_data,
    )

    filename = f"AI_Money_Mentor_Report_{current_user.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/preview")
def report_preview(current_user: CurrentUser, db: DBSession):
    """Return metadata about what will be in the report before generating."""
    profile = db.query(FinancialProfile).filter(
        FinancialProfile.user_id == current_user.id
    ).first()

    has_portfolio = bool(
        db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    )

    sessions = db.query(AgentSession).filter(
        AgentSession.user_id == current_user.id
    ).all()
    agents_run = list({s.agent.value for s in sessions})

    return {
        "user_name": current_user.full_name or current_user.email,
        "profile_complete": bool(profile and profile.monthly_income),
        "has_portfolio": has_portfolio,
        "agents_previously_run": agents_run,
        "sections_in_report": [
            "Executive Summary",
            "Money Health Score" if profile else None,
            "FIRE Planner" if profile and profile.monthly_income else None,
            "Tax Analysis" if profile and profile.monthly_income else None,
            "Portfolio X-Ray" if has_portfolio else None,
            "Disclaimer",
        ],
        "estimated_pages": 4 + (1 if has_portfolio else 0),
    }
