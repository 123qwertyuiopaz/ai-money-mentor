from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
import enum
import uuid
from app.database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ──────────────────────────────────────────────────────────────────────

class RiskProfile(str, enum.Enum):
    conservative = "conservative"
    moderate = "moderate"
    aggressive = "aggressive"


class AgentType(str, enum.Enum):
    health_score = "health_score"
    fire_planner = "fire_planner"
    portfolio_xray = "portfolio_xray"
    tax_wizard = "tax_wizard"
    life_event = "life_event"


# ── User & Auth ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("FinancialProfile", back_populates="user", uselist=False)
    portfolios = relationship("Portfolio", back_populates="user")
    sessions = relationship("AgentSession", back_populates="user")


# ── Financial Profile ─────────────────────────────────────────────────────────

class FinancialProfile(Base):
    """Core financial data for a user — drives all agent computations."""
    __tablename__ = "financial_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # Demographics
    age = Column(Integer, nullable=True)
    city = Column(String(100), nullable=True)

    # Income & Expenses (monthly, INR)
    monthly_income = Column(Float, nullable=True)
    monthly_expenses = Column(Float, nullable=True)
    annual_bonus = Column(Float, default=0.0)

    # Employment
    employer_type = Column(String(50), nullable=True)  # salaried / self_employed / business
    basic_salary = Column(Float, nullable=True)
    hra_received = Column(Float, nullable=True)
    rent_paid = Column(Float, nullable=True)

    # Existing investments (current corpus, INR)
    existing_mutual_funds = Column(Float, default=0.0)
    existing_stocks = Column(Float, default=0.0)
    existing_ppf = Column(Float, default=0.0)
    existing_nps = Column(Float, default=0.0)
    existing_fd = Column(Float, default=0.0)
    existing_real_estate = Column(Float, default=0.0)

    # Liabilities (outstanding, INR)
    home_loan_outstanding = Column(Float, default=0.0)
    car_loan_outstanding = Column(Float, default=0.0)
    personal_loan_outstanding = Column(Float, default=0.0)
    credit_card_debt = Column(Float, default=0.0)

    # Insurance
    life_cover = Column(Float, default=0.0)
    health_cover = Column(Float, default=0.0)
    has_term_plan = Column(Boolean, default=False)

    # Retirement
    target_retirement_age = Column(Integer, default=60)
    monthly_retirement_expenses = Column(Float, nullable=True)

    # Risk
    risk_profile = Column(Enum(RiskProfile), default=RiskProfile.moderate)

    # Tax (annual, INR)
    section_80c_used = Column(Float, default=0.0)
    nps_contribution = Column(Float, default=0.0)
    home_loan_interest = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


# ── Portfolio ──────────────────────────────────────────────────────────────────

class Portfolio(Base):
    """Parsed mutual fund / stock portfolio holdings."""
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(255), default="My Portfolio")
    raw_text = Column(Text, nullable=True)         # original CAMS text
    analysis_json = Column(Text, nullable=True)    # last X-Ray result (JSON string)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="portfolios")
    holdings = relationship("Holding", back_populates="portfolio")


class Holding(Base):
    """Individual fund / stock holding inside a portfolio."""
    __tablename__ = "holdings"

    id = Column(String, primary_key=True, default=_uuid)
    portfolio_id = Column(String, ForeignKey("portfolios.id", ondelete="CASCADE"))

    fund_name = Column(String(500))
    isin = Column(String(20), nullable=True)
    category = Column(String(100), nullable=True)   # Large Cap, ELSS, etc.
    units = Column(Float, default=0.0)
    avg_nav = Column(Float, nullable=True)          # purchase average NAV
    current_nav = Column(Float, nullable=True)
    invested_amount = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    xirr = Column(Float, nullable=True)
    expense_ratio = Column(Float, nullable=True)

    portfolio = relationship("Portfolio", back_populates="holdings")


# ── Agent Sessions & Audit Log ─────────────────────────────────────────────────

class AgentSession(Base):
    """Full record of every agent call — required for hackathon audit trail."""
    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent = Column(Enum(AgentType), nullable=False)
    request_json = Column(Text)            # sanitised input payload
    response_json = Column(Text)           # full structured response
    nim_prompt_tokens = Column(Integer, default=0)
    nim_completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
