# Instant Activation — Historical Audit Design

**Date:** 2026-06-08
**Status:** Approved
**Scope:** Auto-trigger a 90-day historical monitoring audit after thesis decomposition confirmation, delivered as a non-persisted onboarding card

---

## Problem

A user who confirms their thesis decomposition has no monitoring output until the next 6 AM scheduled run — up to 24 hours. `run_first_pulse` already fires a live monitoring pass immediately, but it uses a 7-day lookback and `apply_thesis_floor` filters everything predating thesis creation, so a brand-new thesis sees zero results on its very first check.

The user's first dashboard visit shows "all calm" when nothing has actually been checked in a meaningful window.

---

## Solution

When a thesis decomposition is confirmed, trigger a 90-day historical audit in the background. Run the full monitoring pipeline against the last 90 days — bypassing the thesis creation floor and cooldown checks — and surface the results as an onboarding card framed as: "If you'd held this thesis for the last 90 days, here's what would have fired."

Results are **not persisted** as MonitoringEvents. They are stored as a JSON blob on the Thesis row with a status flag, and read via a dedicated endpoint. This keeps the live monitoring feed clean and avoids polluting cooldown state.

---

## Changes

### 1. Thesis Model — Two New Columns

```
historical_audit_status   VARCHAR(20) nullable  — "pending" | "ready" | "empty" | "failed"
historical_audit_results  JSON nullable          — list of classified event dicts
```

Alembic migration required.

---

### 2. Historical Audit Service

New function `run_historical_audit(thesis_id)` in `backend/app/services/check_now.py`.

**Differences from `run_check_now`:**

| Behaviour | `run_check_now` | `run_historical_audit` |
|---|---|---|
| Lookback window | 7 days | 90 days |
| `apply_thesis_floor` | Yes (thesis creation date) | No — floor is `now - 90 days` |
| Cooldown filtering | Yes | No |
| Persistence | Writes MonitoringEvent rows | No — writes to `thesis.historical_audit_results` |
| Rate limiting | Yes (4h) | No |

**Logic:**
1. Load thesis + holding from DB
2. Set `thesis.historical_audit_status = "pending"`, commit
3. Run the full pipeline: market data, EDGAR 8-Ks (90-day window), Gemini news, signal matching, noise filtering (excluding cooldown), LLM classification
4. Collect all `(candidate, severity, analysis)` tuples that survive classification
5. Sort: severity order (thesis_breaking → warning → info), then recency within each tier
6. Serialise to a list of dicts:
   ```json
   {
     "description": "...",
     "severity": "warning",
     "event_type": "gemini_news",
     "event_date": "2026-04-15",
     "evidence": { ... }
   }
   ```
   `evidence` is passed through as-is from the candidate — shape varies by event type (news: `headline`+`url`; EDGAR: `filing_type`+`items`; etc.).
7. Write `thesis.historical_audit_results = results` and `thesis.historical_audit_status = "ready"` (or `"empty"` if list is empty), commit
8. On any unhandled exception: set `thesis.historical_audit_status = "failed"`, commit, log, do not raise

The function opens its own DB session (pattern established by `run_first_pulse`) and is designed as a `BackgroundTask`.

---

### 3. Trigger Point

`POST /theses/{thesis_id}/decomposition/confirm` — the existing endpoint in `backend/app/routes/thesis.py`.

After the existing `run_first_pulse` background task is added:

```python
from app.services.check_now import run_historical_audit
background_tasks.add_task(run_historical_audit, thesis.id)
```

---

### 4. API Endpoint

New endpoint on the existing `thesis` router:

```
GET /theses/{thesis_id}/historical-audit
```

Returns:
```json
{
  "status": "pending" | "ready" | "empty" | "failed",
  "results": [ ... ] | null
}
```

Auth: same JWT guard as other thesis routes. Returns 404 if thesis not owned by current user.

---

### 5. Frontend

**Location:** `thesis-decomposition-review.tsx` or the page that renders after decomposition confirm.

**Behaviour:**
- After confirm, start polling `GET /theses/{thesis_id}/historical-audit` every 3 seconds
- Stop polling when status is `ready`, `empty`, or `failed`

**States:**

| Status | UI |
|---|---|
| `pending` | Small spinner + "Running 90-day audit…" below the confirmed decomposition |
| `ready` | Card with header "If you'd held this thesis for the last 90 days, here's what would have fired:" + result list |
| `empty` | Single line: "No major events in the last 90 days — your thesis has been steady." |
| `failed` | Silently hidden — no error shown to user |

**Result list item:** severity badge (coloured by warning/info/thesis_breaking) + event date + description. News items include a URL link. Results ordered newest-first within each severity tier.

No dismiss button — card stays visible as context while the user explores.

---

## What This Does NOT Change

- `run_first_pulse` — still fires, still persists live events from the last 7 days
- `apply_thesis_floor` — unchanged; still applied in the live pipeline
- Daily monitoring run — unaffected
- Any cooldown state — historical audit never writes cooldown records

---

## Testing

- Unit test: `run_historical_audit` sets status `"pending"` then `"ready"` on success
- Unit test: results are sorted severity-first, then recency
- Unit test: status set to `"failed"` when pipeline raises, no exception propagated
- Unit test: endpoint returns 404 for thesis not owned by current user
- Unit test: endpoint returns `{status: "pending", results: null}` while audit is running
- Manual: confirm decomposition → spinner appears → card loads with historical events
