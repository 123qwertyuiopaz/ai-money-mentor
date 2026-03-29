"""
AI Money Mentor — FastAPI Application
ET AI Hackathon 2026 | Problem Statement 9

Entry point. Run with:
    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.base import init_db
from app.api.routes import auth, agents, report

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    init_db()
    logger.info("Database initialised ✓")
    yield
    logger.info("Shutting down...")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## AI Money Mentor

India's AI-powered personal finance mentor — powered by NVIDIA NIM.

### Features
- **Money Health Score** — 6-dimension financial wellness score
- **FIRE Planner** — Month-by-month roadmap to financial independence
- **Portfolio X-Ray** — CAMS statement analysis with XIRR & rebalancing
- **Tax Wizard** — Old vs new regime comparison + deduction gap analysis
- **Life Event Advisor** — Bonus, marriage, baby, home purchase planning

### Quick Start
1. `POST /api/v1/auth/register` — create account
2. `PATCH /api/v1/auth/profile` — save your financial profile
3. Call any agent endpoint — profile data is auto-injected

All agent endpoints require `Authorization: Bearer <token>`.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")


# ── Root endpoints ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe — returns 200 if the server is running."""
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "detail": str(exc)},
    )