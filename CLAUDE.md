# Copilot Investor — CLAUDE.md

## What This Project Does

AI-powered portfolio monitoring platform for retail investors. Users define investment "theses" (reasons for owning a stock), and the system continuously validates those theses against market data, news, SEC filings, and earnings events. It fires monitoring events when something meaningful changes, and sends weekly digest emails summarizing the portfolio.

## Architecture

Full-stack: **FastAPI backend** + **Next.js 16 frontend**, deployed on Railway via Docker.

```
backend/app/
  main.py           # FastAPI app, CORS, router registration, scheduler init
  config.py         # Pydantic Settings (all env vars live here)
  database.py       # SQLAlchemy async engine, UUIDType/TZDateTime cross-DB helpers
  models/           # ORM models (user, holding, thesis, monitoring_event, digest, …)
  routes/           # API routers: auth, portfolio, theses, monitoring, digests, onboarding, settings
  schemas/          # Pydantic request/response schemas
  services/         # Business logic & integrations
    reasoning/      # Multi-provider AI gateway (Anthropic → OpenAI fallback)
    ai_thesis.py    # Thesis synthesis, vagueness detection
    ai_monitor.py   # Monitoring orchestration
    ai_digest.py    # Digest generation
    monitoring_pipeline.py  # Classify candidates against thesis claims
    news_collector.py       # Collect news evidence
    edgar.py / edgar_extractor.py  # SEC filing analysis
    market_data.py  # yfinance / Alpha Vantage pricing
    trading212.py   # Broker integration
    email.py        # Resend SDK dispatch
  jobs/             # APScheduler background jobs (9 total)

frontend/src/
  app/              # Next.js App Router pages
  components/       # Reusable UI components
  lib/              # API client, utilities
  types/            # TypeScript interfaces
```

## Key Technologies

| Layer | Stack |
|---|---|
| Backend | FastAPI 0.115+, SQLAlchemy 2 (async), Alembic, APScheduler 3 |
| Database | PostgreSQL (prod), SQLite (dev fallback) |
| AI | Anthropic Claude (default), OpenAI, Google Gemini — routed by complexity |
| Market data | yfinance (default) or Alpha Vantage |
| Email | Resend SDK |
| Auth | JWT (python-jose) + bcrypt |
| Cache | Redis |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, Recharts, SWR |
| Deployment | Docker → Railway |

## Scheduled Jobs (APScheduler)

| Job | Schedule |
|---|---|
| `portfolio_sync` | Every 4 hours |
| `monitoring_run` | Daily 6 AM |
| `digest_builder` | Sundays 6 PM |
| `earnings_refresh` | Mondays 7 AM |
| `pre_earnings_nudge` | Daily 7:30 AM |
| `post_earnings_eval` | Daily 8 AM |
| `quarterly_review_prep` | First Monday of each quarter |
| `onboarding_drip` | Daily 9 AM |
| `reengagement` | Daily 10 AM |

## Running Locally

**Backend:**
```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env   # fill in API keys
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

**Tests:**
```bash
cd backend
pytest                 # all tests
pytest -m "not eval"   # skip tests requiring live API keys
```

## Required Environment Variables

Set in `backend/.env` (see `backend/app/config.py` for full list):

```
DATABASE_URL          postgresql+asyncpg://... (or sqlite+aiosqlite:///./dev.db)
JWT_SECRET            random 32-char string
ENCRYPTION_KEY        exactly 32 bytes
ANTHROPIC_API_KEY
OPENAI_API_KEY
GEMINI_API_KEY
RESEND_API_KEY
REDIS_URL             redis://localhost:6379
FRONTEND_URL          http://localhost:3000
ENABLE_SCHEDULER      true | false
EDGAR_USER_AGENT      CopilotInvestor contact@...
```

Optional: `ALPHA_VANTAGE_API_KEY`, `SENTRY_DSN`, `TRADING212_BASE_URL`.

## AI Routing

`services/reasoning/gateway.py` routes prompts by complexity:
- **Cheap tier:** `gpt-4o-mini` → Anthropic fallback
- **Expensive tier:** Anthropic Claude Sonnet → OpenAI GPT-4 Turbo fallback

Default model: `claude-sonnet-4-20250514`.

## Deployment

- `Dockerfile` — Python 3.12 slim, runs `alembic upgrade head` then `uvicorn` on `$PORT` (default 8080)
- `railway.toml` — health check at `GET /health`, auto-restart on failure
- Database migrations are run automatically on container start

## Common Gotchas

- SQLite dev mode auto-creates tables and patches missing columns; PostgreSQL relies on Alembic migrations.
- `ENABLE_SCHEDULER=false` disables all background jobs (useful during testing).
- Rate limiting via SlowAPI; errors tracked via Sentry if `SENTRY_DSN` is set.
- All UUIDs and datetimes use custom SQLAlchemy types (`UUIDType`, `TZDateTime`) for SQLite/PostgreSQL compatibility.
