import json
import logging
from dataclasses import dataclass

import anthropic

from app.config import settings
from app.services.market_data import fetch_company_data

logger = logging.getLogger(__name__)


@dataclass
class ThesisOutput:
    bull_case: str
    key_metrics: list[dict]
    risk_factors: str
    suggested_conviction: str


THESIS_PROMPT = """You are an investment analyst assistant helping a retail investor understand why they hold a stock.

Given the following position and any available market data, generate a thesis for why a retail investor likely owns this stock.

Position:
- Ticker: {ticker}
- Name: {name}
- Shares: {quantity}
- Average cost: {average_cost}

{market_data_section}

Output valid JSON with this exact structure:
{{
    "bull_case": "2-3 sentences explaining why this is a good hold. Reference specific numbers.",
    "key_metrics": [
        {{
            "metric": "metric_name_snake_case",
            "operator": ">=" or "<=" or ">" or "<" or "==",
            "threshold": 15.0,
            "rationale": "Why this metric matters to the thesis"
        }}
    ],
    "risk_factors": "2-3 sentences about what could go wrong. Be specific.",
    "suggested_conviction": "high" or "medium" or "low"
}}

Requirements:
- key_metrics must have 2-4 items
- Metrics must be specific and measurable
- Be direct and specific, not generic
- Output ONLY valid JSON, no markdown fences"""


async def _call_claude(prompt: str) -> ThesisOutput:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    return ThesisOutput(
        bull_case=data["bull_case"],
        key_metrics=data["key_metrics"],
        risk_factors=data["risk_factors"],
        suggested_conviction=data["suggested_conviction"],
    )


async def generate_thesis(ticker: str, name: str, quantity: float, average_cost: float) -> ThesisOutput | None:
    market_data = await fetch_company_data(ticker)
    if market_data:
        market_data_section = f"Market Data:\n- Sector: {market_data.sector}\n- P/E: {market_data.pe_ratio}\n- Revenue Growth: {market_data.revenue_growth_yoy}%"
    else:
        market_data_section = "Market Data: Not available. Use your knowledge of this company."

    prompt = THESIS_PROMPT.format(ticker=ticker, name=name, quantity=quantity, average_cost=average_cost, market_data_section=market_data_section)

    try:
        result = await _call_claude(prompt)
        if not result.bull_case or not result.key_metrics:
            raise ValueError("Incomplete thesis output")
        return result
    except Exception as e:
        logger.error(f"Thesis generation failed for {ticker}: {e}")
        try:
            return await _call_claude(prompt + "\n\nIMPORTANT: Output ONLY valid JSON.")
        except Exception:
            logger.error(f"Thesis generation retry failed for {ticker}")
            return None
