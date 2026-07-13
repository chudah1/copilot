# Monitoring Soak Toolkit

Use the soak report to review whether a small basket of holdings is becoming launch-ready over a 3-7 day window.

## Example basket

Start from [monitoring_soak.example.json](/Users/cyakung/Projects/copilot_investor/backend/docs/monitoring_soak.example.json) and replace the placeholder IDs with real holdings when a ticker is ambiguous.

## Run it

From `backend/`:

```bash
python scripts/monitoring_soak_report.py \
  --config docs/monitoring_soak.example.json \
  --days 5 \
  --tz Europe/London
```

Or ad hoc:

```bash
python scripts/monitoring_soak_report.py \
  --ticker ASML \
  --ticker MSFT \
  --days 3
```

## Server-side endpoint

For an always-on environment, POST to `/api/monitoring/soak-report` with the
same basket shape. The endpoint is protected by `X-Metrics-Token` and returns
both the full Markdown report and structured summary data.

Example:

```bash
curl -s -X POST https://your-backend.example.com/api/monitoring/soak-report \
  -H "Content-Type: application/json" \
  -H "X-Metrics-Token: $METRICS_TOKEN" \
  -d '{
    "days": 5,
    "timezone_name": "Europe/London",
    "holdings": [
      {"label": "MSFT control", "ticker": "MSFT"},
      {"label": "NVDA control", "ticker": "NVDA"}
    ]
  }'
```

If `holdings` is omitted, the endpoint falls back to `docs/monitoring_soak.json`.

## Scheduled snapshots

The backend scheduler now runs a separate `monitoring_soak_report` job twice
daily at `08:00` and `18:00`. It reads `docs/monitoring_soak.json`, computes
the report, and persists a snapshot to `monitoring_soak_reports`.

Use the protected read endpoint to inspect the stored history:

```bash
curl -s https://your-backend.example.com/api/monitoring/soak-reports \
  -H "X-Metrics-Token: $METRICS_TOKEN"
```

This keeps soak reporting off the hot monitoring pipeline while still making it
automatic and durable.

## What the report shows

- A summary table per holding:
  - number of passes in the window
  - total persisted events
  - total same-event merges
  - source errors
  - the latest funnel including `after_same_event_merge`
- A detail section per holding:
  - assessment (`healthy`, `noisy`, `quiet`, `review`, `failing`, `unmonitored`)
  - last pass trigger and timestamp
  - recent event samples

## Review rubric

- `healthy`: event volume and pass shape look sane.
- `quiet`: no events surfaced, but the pipeline still ran cleanly.
- `noisy`: latest pass still persisted too many items.
- `review`: volume looks suspicious relative to same-event merge activity.
- `failing`: one or more passes recorded a pipeline error.
- `unmonitored`: no pass landed in the chosen window.
