#  AI Money Mentor

> **ET AI Hackathon 2026 — Problem Statement 9**
> India's AI-powered personal finance mentor, built on NVIDIA NIM + FastAPI + SQLite.

---

## What It Does

AI Money Mentor gives every Indian retail investor access to a CFA-grade financial advisor at zero cost. Five specialised AI agents — each combining deterministic financial math with NVIDIA NIM's LLM reasoning — answer the questions that a ₹25,000/year human advisor would.

| Agent | What it answers |
|---|---|
| **Money Health Score** | How financially healthy am I? (6-dimension score) |
| 🔥 **FIRE Planner** | Month-by-month roadmap to financial independence |
| 🔬 **Portfolio X-Ray** | Is my mutual fund portfolio any good? |
| 🧾 **Tax Wizard** | Old or new regime? What deductions am I missing? |
| 🎉 **Life Event Advisor** | Got a bonus / having a baby / buying a house — now what? |

---

## Architecture

```
Client (browser/mobile/curl)
    │ REST + JSON
    ▼
FastAPI Gateway  ─────  JWT auth · Pydantic validation · OpenAPI docs
    │
    ▼
Agent Orchestrator  ──  Selects agent, injects user context from DB
    │
    ├─ HealthScoreAgent
    ├─ FIREPlannerAgent        ──── Financial Calculator (pure Python)
    ├─ PortfolioXRayAgent      ──── PDF / CAMS Parser
    ├─ TaxWizardAgent          ──── Tax Math (FY 2024-25 slabs)
    └─ LifeEventAgent
         │
         ▼
    NVIDIA NIM API  (meta/llama-3.1-70b-instruct)
         │
         ▼
    SQLite Database  ──  users · financial_profiles · portfolios · audit_log
```

Every agent call is: **pre-compute math → inject context → call NIM → persist audit log → return structured JSON.**

---

## Prerequisites

- Python 3.11+
- An **NVIDIA NIM API key** — get one free at https://integrate.api.nvidia.com

That's it. No Docker, no PostgreSQL, no Redis. Runs on any laptop.

---

## Quick Start (3 minutes)

```bash
# 1. Clone and enter the project
git clone <https://github.com/123qwertyuiopaz/ai-money-mentor>
cd ai-money-mentor

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Open .env and set:
#   NVIDIA_NIM_API_KEY=nvapi-your-key-here
#   SECRET_KEY=any-random-32-char-string

# 5. Run the server
uvicorn app.main:app --reload
```

The API is now live at **http://localhost:8000**
Interactive docs at **http://localhost:8000/docs**

---

## Usage Examples

### Register & get a token
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "yourpassword", "full_name": "Your Name"}'
```

### Save your financial profile (once — agents auto-use it)
```bash
curl -X PATCH http://localhost:8000/api/v1/auth/profile \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "age": 32,
    "monthly_income": 150000,
    "monthly_expenses": 80000,
    "existing_mutual_funds": 500000,
    "section_80c_used": 100000,
    "risk_profile": "moderate"
  }'
```

### Get your Money Health Score
```bash
curl -X POST http://localhost:8000/api/v1/agents/health-score \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{}'   # Uses your saved profile
```

### FIRE Planner
```bash
curl -X POST http://localhost:8000/api/v1/agents/fire-planner \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"target_retirement_age": 45}'
```

### Tax Wizard (old vs new regime)
```bash
curl -X POST http://localhost:8000/api/v1/agents/tax-wizard \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "annual_income": 1200000,
    "section_80c_used": 50000,
    "nps_contribution": 0,
    "rent_paid_annual": 240000
  }'
```

### Life Event — Bonus received
```bash
curl -X POST http://localhost:8000/api/v1/agents/life-event \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"event": "bonus", "event_amount": 500000}'
```

### Portfolio X-Ray (paste CAMS text)
```bash
curl -X POST http://localhost:8000/api/v1/agents/portfolio-xray \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"cams_text": "<paste your CAMS statement here>"}'
```

### Upload a CAMS PDF
```bash
curl -X POST http://localhost:8000/api/v1/agents/portfolio-upload \
  -H "Authorization: Bearer <your_token>" \
  -F "file=@/path/to/your/CAMS_statement.pdf"
# Then call /agents/portfolio-xray with an empty body
```

---

## Run Tests

```bash
pytest tests/test_financial_calculator.py -v      # Pure math — no NIM key needed
pytest tests/ -v                                  # Full suite (skips NIM tests if no key)
```

---

## Project Structure

```
ai-money-mentor/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (reads .env)
│   ├── database/
│   │   ├── base.py              # SQLAlchemy engine + session
│   │   └── models.py            # All ORM models
│   ├── agents/
│   │   ├── base_agent.py        # Abstract base (run, log, context inject)
│   │   ├── health_score_agent.py
│   │   ├── fire_planner_agent.py
│   │   ├── portfolio_xray_agent.py
│   │   ├── tax_wizard_agent.py
│   │   └── life_event_agent.py
│   ├── services/
│   │   ├── nim_client.py        # NVIDIA NIM API wrapper
│   │   ├── financial_calculator.py  # All financial math
│   │   └── pdf_parser.py        # CAMS + Form 16 parser
│   ├── api/
│   │   ├── deps.py              # Auth dependencies
│   │   └── routes/
│   │       ├── auth.py          # Register, login, profile
│   │       └── agents.py        # All five agent endpoints
│   └── schemas/
│       ├── user.py              # User/auth schemas
│       └── agents.py            # Agent request/response schemas
├── tests/
│   ├── conftest.py              # Fixtures (in-memory DB)
│   ├── test_financial_calculator.py
│   └── test_api.py
├── data/
│   ├── samples/sample_cams.txt  # Sample CAMS for testing
│   └── money_mentor.db          # SQLite DB (auto-created)
├── .env.example                 # Copy to .env and fill in
├── .gitignore
├── requirements.txt
└── README.md
```

---

## API Reference

Full interactive API docs available at `/docs` (Swagger UI) and `/redoc` when the server is running.

### Auth endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT token |
| GET | `/api/v1/auth/me` | Current user |
| PATCH | `/api/v1/auth/profile` | Update financial profile |
| GET | `/api/v1/auth/profile` | Get financial profile |

### Agent endpoints (all require Bearer token)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agents/health-score` | Money Health Score |
| POST | `/api/v1/agents/fire-planner` | FIRE roadmap |
| POST | `/api/v1/agents/portfolio-xray` | Portfolio analysis |
| POST | `/api/v1/agents/portfolio-upload` | Upload CAMS PDF |
| POST | `/api/v1/agents/tax-wizard` | Tax optimisation |
| POST | `/api/v1/agents/life-event` | Life event advisor |
| GET | `/api/v1/agents/history` | Agent call history |

---

## Impact Model

| Metric | Estimate | Basis |
|---|---|---|
| Financial advisor cost saved | ₹25,000/year/user | Market rate for CFP-grade advice |
| Time to get advice | 30 seconds | vs 2-3 weeks for human advisor appointment |
| Tax saving per user (avg) | ₹18,000/year | 80CCD(1B) + optimal regime selection for ₹12L income |
| Portfolio alpha (overlap fix) | 1.5–2% CAGR | Eliminating fund overlap and expense ratio drag |
| Target addressable users | 14 Cr demat account holders | SEBI 2024 data |

**Conservative scenario**: 1M users × ₹18,000 tax saving = **₹18,000 Cr in annual tax savings unlocked.**

---

## NVIDIA NIM Configuration

The app uses `meta/llama-3.1-70b-instruct` by default. To use a different model, update `NVIDIA_NIM_MODEL` in `.env`.

Supported models on NIM include:
- `meta/llama-3.1-70b-instruct` (recommended — best reasoning)
- `meta/llama-3.1-8b-instruct` (faster, lower cost)
- `mistralai/mistral-7b-instruct-v0.3`

---

## License

MIT — free to use, modify, and deploy.
