from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache: {ticker:YYYY-MM-DD} → StressTestResult
_cache: dict[str, StressTestResult] = {}


@dataclass
class StressTestOutput:
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    what_to_watch: list[str]


@dataclass
class StressTestResult:
    ticker: str
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    what_to_watch: list[str]
    current_price: float | None
    cached: bool = False


async def _generate(
    ticker: str,
    draft_thesis: str | None,
    current_price: float | None,
    recent_headlines: list[str],
) -> StressTestOutput:
    from app.services.ai_thesis import generate_stress_test_analysis

    return await generate_stress_test_analysis(
        ticker=ticker,
        draft_thesis=draft_thesis,
        current_price=current_price,
        recent_headlines=recent_headlines,
    )


async def run_stress_test(
    ticker: str,
    draft_thesis: str | None,
    current_price: float | None,
    recent_headlines: list[str],
) -> StressTestResult:
    ticker = ticker.upper()
    use_cache = draft_thesis is None
    cache_key = f"{ticker}:{date.today().isoformat()}"

    if use_cache and cache_key in _cache:
        cached = _cache[cache_key]
        return StressTestResult(
            ticker=cached.ticker,
            bear_case=cached.bear_case,
            key_risks=cached.key_risks,
            blind_spots=cached.blind_spots,
            what_to_watch=cached.what_to_watch,
            current_price=cached.current_price,
            cached=True,
        )

    output = await _generate(
        ticker=ticker,
        draft_thesis=draft_thesis,
        current_price=current_price,
        recent_headlines=recent_headlines,
    )

    result = StressTestResult(
        ticker=ticker,
        bear_case=output.bear_case,
        key_risks=output.key_risks,
        blind_spots=output.blind_spots,
        what_to_watch=output.what_to_watch,
        current_price=current_price,
        cached=False,
    )

    if use_cache:
        _cache[cache_key] = result

    return result
