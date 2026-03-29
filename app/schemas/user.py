from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FinancialProfileIn(BaseModel):
    """All fields optional — partial updates are fine."""
    age: Optional[int] = None
    city: Optional[str] = None
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    annual_bonus: Optional[float] = None
    employer_type: Optional[str] = None
    basic_salary: Optional[float] = None
    hra_received: Optional[float] = None
    rent_paid: Optional[float] = None
    existing_mutual_funds: Optional[float] = None
    existing_stocks: Optional[float] = None
    existing_ppf: Optional[float] = None
    existing_nps: Optional[float] = None
    existing_fd: Optional[float] = None
    existing_real_estate: Optional[float] = None
    home_loan_outstanding: Optional[float] = None
    car_loan_outstanding: Optional[float] = None
    personal_loan_outstanding: Optional[float] = None
    credit_card_debt: Optional[float] = None
    life_cover: Optional[float] = None
    health_cover: Optional[float] = None
    has_term_plan: Optional[bool] = None
    target_retirement_age: Optional[int] = None
    monthly_retirement_expenses: Optional[float] = None
    risk_profile: Optional[str] = None
    section_80c_used: Optional[float] = None
    nps_contribution: Optional[float] = None
    home_loan_interest: Optional[float] = None
