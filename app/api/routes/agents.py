"""
Agent routes — one endpoint per AI agent.
All routes require a valid JWT. Payloads are merged with the user's
stored financial profile so callers can omit fields already on file.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.agents.health_score_agent import HealthScoreAgent
from app.agents.fire_planner_agent import FIREPlannerAgent
from app.agents.portfolio_xray_agent import PortfolioXRayAgent
from app.agents.tax_wizard_agent import TaxWizardAgent
from app.agents.life_event_agent import LifeEventAgent
from app.schemas.agents import (
    HealthScoreRequest,
    FIREPlannerRequest,
    PortfolioXRayRequest,
    TaxWizardRequest,
    LifeEventRequest,
)
from app.services.pdf_parser import parse_cams_pdf
from app.database.models import Portfolio, Holding, AgentSession

router = APIRouter(prefix="/agents", tags=["Agents"])

# Module-level agent instances (stateless — safe to share)
_health_agent = HealthScoreAgent()
_fire_agent = FIREPlannerAgent()
_xray_agent = PortfolioXRayAgent()
_tax_agent = TaxWizardAgent()
_life_agent = LifeEventAgent()


# ── 1. Money Health Score ────────────────────────────────────────────────────

@router.post("/health-score")
def run_health_score(
    payload: HealthScoreRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Compute a 0-100 Money Health Score across 6 dimensions.
    Provide any of the fields; missing ones are pulled from your saved profile.
    """
    try:
        result = _health_agent.run(db, current_user, payload.model_dump())
        return {"success": True, "agent": "health_score", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 2. FIRE Planner ───────────────────────────────────────────────────────────

@router.post("/fire-planner")
def run_fire_planner(
    payload: FIREPlannerRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Build a complete FIRE roadmap with SIP amounts, milestones, and asset allocation.
    """
    try:
        result = _fire_agent.run(db, current_user, payload.model_dump())
        return {"success": True, "agent": "fire_planner", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 3. Portfolio X-Ray ────────────────────────────────────────────────────────

@router.post("/portfolio-xray")
def run_portfolio_xray(
    payload: PortfolioXRayRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Analyse a CAMS statement (pasted as text). Returns XIRR, overlap score,
    expense drag, and a category-wise rebalancing plan.
    """
    if not payload.cams_text:
        # Try loading from the user's most recent saved portfolio
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == current_user.id)
            .order_by(Portfolio.created_at.desc())
            .first()
        )
        if portfolio and portfolio.raw_text:
            payload.cams_text = portfolio.raw_text
        else:
            raise HTTPException(
                status_code=422,
                detail="Provide cams_text in the request or upload a CAMS PDF first via /agents/portfolio-upload",
            )
    try:
        result = _xray_agent.run(db, current_user, payload.model_dump())
        return {"success": True, "agent": "portfolio_xray", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio-upload", status_code=status.HTTP_201_CREATED)
async def upload_portfolio(
    file: UploadFile,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Upload a CAMS PDF. Extracts text and saves holdings to the database.
    After uploading, call /agents/portfolio-xray without a body to analyse.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        raw_text, holdings_data = parse_cams_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")

    # Save portfolio
    portfolio = Portfolio(
        user_id=current_user.id,
        name=file.filename,
        raw_text=raw_text,
    )
    db.add(portfolio)
    db.flush()  # get ID before adding children

    for h in holdings_data:
        holding = Holding(
            portfolio_id=portfolio.id,
            fund_name=h.get("fund_name", "Unknown"),
            isin=h.get("isin"),
            units=h.get("units") or 0.0,
            avg_nav=h.get("nav"),
            current_value=h.get("current_value") or 0.0,
            invested_amount=h.get("invested_amount") or 0.0,
        )
        db.add(holding)

    db.commit()

    return {
        "success": True,
        "portfolio_id": portfolio.id,
        "funds_detected": len(holdings_data),
        "message": "Portfolio saved. Call POST /agents/portfolio-xray (no body) to analyse.",
    }


# ── 4. Tax Wizard ─────────────────────────────────────────────────────────────

@router.post("/tax-wizard")
def run_tax_wizard(
    payload: TaxWizardRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Old vs new regime comparison + personalised deduction gap analysis.
    Optionally provide Form 16 data; missing values are pulled from your profile.
    """
    try:
        result = _tax_agent.run(db, current_user, payload.model_dump())
        return {"success": True, "agent": "tax_wizard", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 5. Life Event Advisor ─────────────────────────────────────────────────────

@router.post("/life-event")
def run_life_event(
    payload: LifeEventRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get a tailored financial action plan for a life event.
    Supported events: bonus, inheritance, marriage, new_baby,
    job_change, home_purchase, retirement, medical_emergency.
    """
    try:
        result = _life_agent.run(db, current_user, payload.model_dump())
        return {"success": True, "agent": "life_event", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audit / history ───────────────────────────────────────────────────────────

@router.get("/history")
def get_history(current_user: CurrentUser, db: DBSession, limit: int = 20):
    """Return the last N agent calls for the current user."""
    sessions = (
        db.query(AgentSession)
        .filter(AgentSession.user_id == current_user.id)
        .order_by(AgentSession.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "session_id": s.id,
            "agent": s.agent.value,
            "created_at": s.created_at.isoformat(),
            "latency_ms": s.latency_ms,
            "nim_tokens": s.nim_prompt_tokens + s.nim_completion_tokens,
        }
        for s in sessions
    ]
