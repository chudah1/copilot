"""Post-earnings review: evaluate thesis claims against latest earnings data."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from app.config import settings
from app.services.ai_utils import strip_code_fences
from app.services.market_data import CompanyData

logger = logging.getLogger(__name__)


@dataclass
class ClaimVerdict:
    claim_id: str
    claim_text: str
    verdict: str  # "holds" | "watch" | "broken" | "unclear"
    explanation: str  # starts with "You said..."
    evidence: str | None = None  # specific number or fact from earnings


@dataclass
class EarningsReviewResult:
    verdicts: list[ClaimVerdict]
    overall_assessment: str  # "thesis_intact" | "watch" | "thesis_challenged"
    summary: str
    fiscal_quarter: str | None
    earnings_surprise_pct: float | None


_EARNINGS_REVIEW_PROMPT = """\
You are a rigorous investment analyst helping a retail investor evaluate their thesis after earnings.

The investor owns {ticker} ({name}). Here is their investment thesis:

WHY THEY OWN IT:
{why_own_it}

CONDITIONS THAT MUST REMAIN TRUE:
{must_remain_true}

WHAT WOULD CHANGE THEIR MIND:
{what_would_change_my_mind}

SPECIFIC CLAIMS FROM THEIR THESIS (evaluate each one):
{claims_section}

LATEST EARNINGS DATA:
- Fiscal quarter: {fiscal_quarter}
- Earnings surprise: {earnings_surprise}
- Revenue growth (YoY): {revenue_growth}
- Earnings growth (YoY): {earnings_growth}
- Current P/E ratio: {pe_ratio}
- Market cap: {market_cap}
- Recent news headlines:
{news_headlines}

For each claim, evaluate whether the latest earnings data supports, threatens, or is unclear about that claim.

Return valid JSON with this exact structure:
{{
  "verdicts": [
    {{
      "claim_id": "the claim id from the list above",
      "claim_text": "the exact claim text",
      "verdict": "holds" | "watch" | "broken" | "unclear",
      "explanation": "Start with 'You said [direct quote of their claim]. [Evidence from earnings]. This [holds/is worth watching/no longer holds] because [specific reason].'",
      "evidence": "Specific number or fact from the earnings data, or null if not applicable"
    }}
  ],
  "overall_assessment": "thesis_intact" | "watch" | "thesis_challenged",
  "summary": "2-3 sentences. Be direct. Reference specific numbers from earnings. Say what the investor needs to hear, not what they want to hear.",
  "fiscal_quarter": "Q1 2026 or similar, null if unknown"
}}

Rules:
- explanation must start with "You said" and quote from their actual thesis
- Be direct about broken conditions — do not soften bad news
- Only mark "broken" if earnings data directly contradicts a specific claim
- Use "watch" when the trend is concerning but not definitively broken
- Use "unclear" when there is not enough data to evaluate
- If no claims provided, still give an overall assessment based on the thesis text
- Output ONLY valid JSON, no markdown fences"""


def _format_claims_section(claims: list[dict]) -> str:
    if not claims:
        return "(No specific claims decomposed — evaluate the thesis as a whole)"
    lines = []
    for c in claims:
        lines.append(f'- claim_id: "{c["id"]}" | "{c["claim_text"]}"')
    return "\n".join(lines)


def _format_news_headlines(company_data: CompanyData) -> str:
    headlines = company_data.recent_news[:5]
    if not headlines:
        return "  - No recent news available"
    return "\n".join(f"  - {h}" for h in headlines)


def _format_metric_pct(value: float | None) -> str:
    if value is None:
        return "Not available"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{pct:.1f}%"


def _fallback_review(
    claims: list[dict],
    company_data: CompanyData,
    ticker: str,
) -> EarningsReviewResult:
    verdicts = [
        ClaimVerdict(
            claim_id=c["id"],
            claim_text=c["claim_text"],
            verdict="unclear",
            explanation=f"You said \"{c['claim_text']}\". Unable to evaluate automatically — review earnings report directly.",
            evidence=None,
        )
        for c in claims
    ]
    surprise = company_data.recent_earnings_surprise_pct
    if surprise is not None and abs(surprise) >= 10:
        assessment = "watch" if surprise > 0 else "thesis_challenged"
        summary = f"Earnings came in {'+' if surprise > 0 else ''}{surprise:.1f}% vs expectations. Review earnings details to evaluate your thesis claims."
    else:
        assessment = "watch"
        summary = "Unable to complete AI-assisted review. Check the earnings report and update your thesis manually."

    return EarningsReviewResult(
        verdicts=verdicts,
        overall_assessment=assessment,
        summary=summary,
        fiscal_quarter=company_data.recent_fiscal_quarter,
        earnings_surprise_pct=surprise,
    )


def _parse_review_output(data: dict, claims: list[dict]) -> EarningsReviewResult:
    raw_verdicts = data.get("verdicts", [])
    # Index claims by id for fallback
    claims_by_id = {c["id"]: c for c in claims}

    verdicts = []
    for v in raw_verdicts:
        claim_id = str(v.get("claim_id", ""))
        claim_text = v.get("claim_text") or claims_by_id.get(claim_id, {}).get("claim_text", "")
        verdicts.append(
            ClaimVerdict(
                claim_id=claim_id,
                claim_text=claim_text,
                verdict=v.get("verdict", "unclear"),
                explanation=v.get("explanation", ""),
                evidence=v.get("evidence"),
            )
        )

    return EarningsReviewResult(
        verdicts=verdicts,
        overall_assessment=data.get("overall_assessment", "watch"),
        summary=data.get("summary", ""),
        fiscal_quarter=data.get("fiscal_quarter"),
        earnings_surprise_pct=None,  # set by caller from company_data
    )


async def run_earnings_review(
    *,
    ticker: str,
    name: str,
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    claims: list[dict],
    company_data: CompanyData,
) -> EarningsReviewResult:
    """Evaluate thesis claims against latest earnings data.

    claims: list of {"id": str, "claim_text": str}
    """
    if not settings.anthropic_api_key:
        return _fallback_review(claims, company_data, ticker)

    surprise = company_data.recent_earnings_surprise_pct
    surprise_str = f"{'+' if surprise and surprise > 0 else ''}{surprise:.1f}%" if surprise is not None else "Not available"

    prompt = _EARNINGS_REVIEW_PROMPT.format(
        ticker=ticker,
        name=name,
        why_own_it=why_own_it,
        must_remain_true=must_remain_true or "Not specified",
        what_would_change_my_mind=what_would_change_my_mind or "Not specified",
        claims_section=_format_claims_section(claims),
        fiscal_quarter=company_data.recent_fiscal_quarter or "Most recent quarter",
        earnings_surprise=surprise_str,
        revenue_growth=_format_metric_pct(company_data.revenue_growth_yoy),
        earnings_growth=_format_metric_pct(company_data.earnings_growth_yoy),
        pe_ratio=f"{company_data.pe_ratio:.1f}x" if company_data.pe_ratio else "Not available",
        market_cap=f"${company_data.market_cap / 1e9:.1f}B" if company_data.market_cap else "Not available",
        news_headlines=_format_news_headlines(company_data),
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
            timeout=45.0,
        )
        data = json.loads(strip_code_fences(response.content[0].text))
        result = _parse_review_output(data, claims)
        result.earnings_surprise_pct = surprise
        if result.fiscal_quarter is None:
            result.fiscal_quarter = company_data.recent_fiscal_quarter
        return result
    except Exception as e:
        logger.error("Earnings review failed for %s: %s", ticker, e)
        return _fallback_review(claims, company_data, ticker)
