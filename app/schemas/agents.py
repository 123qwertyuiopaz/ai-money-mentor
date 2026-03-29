from pydantic import BaseModel, field_validator
from typing import Optional, Any


# ── Health Score ──────────────────────────────────────────────────────────────

class HealthScoreRequest(BaseModel):
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    emergency_fund: Optional[float] = None
    life_cover: Optional[float] = None
    health_cover: Optional[float] = None
    debt_emi: Optional[float] = 0.0
    monthly_investment: Optional[float] = 0.0
    has_term_plan: Optional[bool] = False
    age: Optional[int] = None
    additional_context: Optional[str] = None


# ── FIRE Planner ──────────────────────────────────────────────────────────────

class FIREPlannerRequest(BaseModel):
    age: Optional[int] = None
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    target_retirement_age: Optional[int] = 45
    monthly_retirement_expenses: Optional[float] = None
    existing_corpus: Optional[float] = None
    risk_profile: Optional[str] = "moderate"
    life_goals: Optional[str] = None


# ── Portfolio X-Ray ───────────────────────────────────────────────────────────

class PortfolioXRayRequest(BaseModel):
    cams_text: Optional[str] = None    # pasted CAMS statement
    age: Optional[int] = None
    risk_profile: Optional[str] = None


# ── Tax Wizard ────────────────────────────────────────────────────────────────

class TaxWizardRequest(BaseModel):
    annual_income: Optional[float] = None
    basic_salary_annual: Optional[float] = None
    hra_received_annual: Optional[float] = None
    rent_paid_annual: Optional[float] = None
    section_80c_used: Optional[float] = 0.0
    nps_contribution: Optional[float] = 0.0
    home_loan_interest: Optional[float] = 0.0
    is_metro_city: Optional[bool] = True
    additional_context: Optional[str] = None


# ── Life Event ────────────────────────────────────────────────────────────────

VALID_EVENTS = {
    "bonus", "inheritance", "marriage", "new_baby",
    "job_change", "home_purchase", "retirement", "medical_emergency"
}


class LifeEventRequest(BaseModel):
    event: str
    event_amount: Optional[float] = None
    home_value: Optional[float] = None   # for home_purchase event
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    age: Optional[int] = None
    risk_profile: Optional[str] = "moderate"
    additional_context: Optional[str] = None

    @field_validator("event")
    @classmethod
    def valid_event(cls, v: str) -> str:
        if v not in VALID_EVENTS:
            raise ValueError(f"event must be one of: {', '.join(sorted(VALID_EVENTS))}")
        return v


# ── Generic response wrapper ─────────────────────────────────────────────────

class AgentResponse(BaseModel):
    success: bool = True
    agent: str
    data: dict[str, Any]
    session_id: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
