# PenKeep

PenKeep is a decision journal and monitoring system for long-term investors. It records **why** a position belongs in a portfolio, checks new evidence against that written case, and preserves the decisions made afterwards.

It is designed for both investors with a structured thesis and investors starting with a simple belief such as “this is a durable company.” PenKeep helps turn either starting point into clear, monitorable reasoning without requiring institutional finance tooling.

## The product loop

```text
Import positions
      ↓
Write why each position belongs
      ↓
Confirm what PenKeep should watch
      ↓
Review evidence that tests the reason
      ↓
Reaffirm, lower confidence, rewrite, or exit
      ↓
Build a decision record that improves future judgment
```

PenKeep keeps two ideas separate:

- **Decision state**: whether new evidence leaves a position calm, changed, or needing a decision.
- **Case quality**: whether the written reason is specific, monitorable, and current.

An overdue review can reduce case quality without implying that the investment itself has changed.

## What is included

- Manual, CSV, and Trading 212 portfolio import
- Guided onboarding from a rough reason to one monitored position
- AI-assisted writing that preserves the investor's own reasoning
- Decomposition of a written case into claims and monitorable signals
- Evidence monitoring across market data, filings, earnings, and news
- Guided evidence reviews with explicit investor decisions
- Append-only decision history, notes, and conviction changes
- Weekly digests, open follow-ups, and quarterly reviews
- Portfolio-level behavioral memory and decision coaching
- Pre-purchase research and portfolio-impact simulation

## Repository layout

```text
backend/          FastAPI API, monitoring jobs, models, migrations, and tests
frontend/         Next.js application and frontend tests
docs/             Product plans, architecture notes, and domain guidance
marketing-video/  Remotion product-video project
bridge/           Supporting integration utilities
```

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, SWR |
| Backend | FastAPI, SQLAlchemy async, Alembic, APScheduler |
| Data | PostgreSQL in production; SQLite for lightweight local development |
| Queue/cache | Redis |
| AI | OpenAI, Anthropic, and Gemini provider paths |
| Market evidence | SEC EDGAR, yfinance or Alpha Vantage, Trading 212 |

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop or another Docker Compose runtime

### 1. Start PostgreSQL and Redis

```bash
docker compose up -d
```

This starts the local infrastructure only. PostgreSQL is available on port `5432` and Redis on port `6379`.

### 2. Configure and run the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Set the local database URL in `backend/.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://copilot:copilot@localhost:5432/copilot_investor
REDIS_URL=redis://localhost:6379
ENABLE_SCHEDULER=false
MARKET_DATA_PROVIDER=yfinance
```

Then apply migrations and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The API is available at [http://localhost:8000](http://localhost:8000), with interactive documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

For a lighter setup, use `DATABASE_URL=sqlite+aiosqlite:///./copilot_investor.db`. The application creates the SQLite development schema at startup.

### 3. Run the frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Local browser builds automatically use the API on port `8000`; set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` only when the API is elsewhere.

## Environment variables

Start from [`backend/.env.example`](backend/.env.example). Important settings include:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL or SQLite connection URL |
| `REDIS_URL` | Redis connection used by supporting workflows |
| `JWT_SECRET` | Authentication signing secret; replace the development value in production |
| `ENCRYPTION_KEY` | Encryption key for stored credentials; replace the development value in production |
| `OPENAI_API_KEY` | OpenAI reasoning and generation provider |
| `ANTHROPIC_API_KEY` | Anthropic fallback/provider path |
| `GEMINI_API_KEY` | Gemini fallback/provider path |
| `ALPHA_VANTAGE_API_KEY` | Required when `MARKET_DATA_PROVIDER=alpha_vantage` |
| `RESEND_API_KEY` | Email delivery for digests and account flows |
| `ENABLE_SCHEDULER` | Enables recurring monitoring and digest jobs |

The application can boot without AI-provider keys, but AI-assisted writing and model-based monitoring require a configured provider. Never commit `.env` files or production secrets.

Frontend deployment variables:

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Public backend URL; defaults to local port `8000` in development |
| `NEXT_PUBLIC_REGISTRATION_OPEN` | Set to `false` to show the waitlist instead of public signup |

## Verification

Backend:

```bash
cd backend
pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npx tsc --noEmit
node --test tests/*.mjs tests/*.mts
npm run build
```

The backend health endpoint is `GET /health`. It reports `degraded` when a scheduled job has failed while remaining available to infrastructure health checks.

## Domain language

[`CONTEXT.md`](CONTEXT.md) is the source of truth for product terminology. In particular, use **written case**, **decision state**, **case quality**, and **review overdue** consistently when changing product behavior or copy.

## Current direction

PenKeep is being developed around one core outcome: helping investors make calmer, evidence-based decisions while preserving the reasoning that led to them. The remaining product phases and success signals are tracked in [`docs/stickiness-phases.md`](docs/stickiness-phases.md).
