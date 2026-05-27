from fastapi import APIRouter, Request
from app.limiter import limiter
from app.schemas.thesis import StressTestRequest, StressTestResponse
from app.services.stress_test import run_stress_test
from app.services.market_data import fetch_company_data, detect_native_currency

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/stress-test", response_model=StressTestResponse)
@limiter.limit("5/hour")
async def stress_test(request: Request, body: StressTestRequest):
    ticker = body.ticker.upper().strip()

    company_data = await fetch_company_data(ticker)

    result = await run_stress_test(
        ticker=ticker,
        draft_thesis=body.draft_thesis,
        company_data=company_data,
    )

    return StressTestResponse(
        ticker=result.ticker,
        bear_case=result.bear_case,
        key_risks=result.key_risks,
        blind_spots=result.blind_spots,
        what_to_watch=result.what_to_watch,
        current_price=result.current_price,
        currency=detect_native_currency(ticker),
        cached=result.cached,
    )
