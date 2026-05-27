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
    current_price = company_data.current_price if company_data else None
    recent_headlines = (
        [n.headline for n in (company_data.news_items or [])[:5]]
        if company_data and company_data.news_items
        else []
    )

    result = await run_stress_test(
        ticker=ticker,
        draft_thesis=body.draft_thesis,
        current_price=current_price,
        recent_headlines=recent_headlines,
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
