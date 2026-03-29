from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    DBSession, CurrentUser,
    hash_password, verify_password, create_access_token,
)
from app.database.models import User, FinancialProfile, RiskProfile
from app.schemas.user import UserCreate, UserLogin, Token, UserOut, FinancialProfileIn

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DBSession):
    """Create a new account and return an access token."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    # Create empty financial profile
    profile = FinancialProfile(user=user)

    try:
        db.add(user)
        db.add(profile)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")

    token = create_access_token({"sub": user.id})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: DBSession):
    """Authenticate and return a JWT token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    token = create_access_token({"sub": user.id})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUser):
    """Return the currently authenticated user."""
    return current_user


@router.patch("/profile")
def update_profile(payload: FinancialProfileIn, current_user: CurrentUser, db: DBSession):
    """
    Upsert the user's financial profile.
    Only provided fields are updated — omitted fields stay unchanged.
    """
    profile = (
        db.query(FinancialProfile)
        .filter(FinancialProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        profile = FinancialProfile(user_id=current_user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_none=True)

    # Handle risk_profile enum conversion
    if "risk_profile" in update_data:
        try:
            update_data["risk_profile"] = RiskProfile(update_data["risk_profile"])
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"risk_profile must be one of: {[e.value for e in RiskProfile]}",
            )

    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return {"success": True, "message": "Profile updated"}


@router.get("/profile")
def get_profile(current_user: CurrentUser, db: DBSession):
    """Return the user's full financial profile."""
    profile = (
        db.query(FinancialProfile)
        .filter(FinancialProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        return {}
    return {
        col.name: getattr(profile, col.name)
        for col in profile.__table__.columns
        if col.name not in ("id", "hashed_password")
    }
