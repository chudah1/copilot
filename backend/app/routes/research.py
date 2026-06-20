from fastapi import APIRouter, Request
from app.limiter import limiter
from app.schemas.thesis import StressTestRequest, StressTestResponse
from app.services.stress_test import run_stress_test
from app.services.market_data import fetch_company_data, detect_native_currency

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/stress-test", response_model=StressTestResponse)
@limiter.limit("2/hour")
async def stress_test(request: Request, body: StressTestRequest):
    ticker = body.ticker.upper().strip()

    company_data = await fetch_company_data(ticker)

    result = await run_stress_test(
        ticker=ticker,
        draft_thesis=body.draft_thesis,
        company_data=company_data,
    )

    # Prefer the provider's authoritative currency; fall back to the suffix
    # heuristic only when the provider didn't report one (e.g. fetch failed).
    currency = (company_data.currency if company_data else None) or detect_native_currency(ticker)

    return StressTestResponse(
        ticker=result.ticker,
        bear_case=result.bear_case,
        key_risks=result.key_risks,
        risk_groups=result.risk_groups,
        blind_spots=result.blind_spots,
        what_to_watch=result.what_to_watch,
        current_price=result.current_price,
        currency=currency,
        cached=result.cached,
        source_notes=result.source_notes,
        candidate_signals=result.candidate_signals,
    )
