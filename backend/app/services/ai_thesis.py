import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import anthropic

from app.config import settings
from app.services.ai_utils import strip_code_fences
from app.services.market_data import fetch_company_data

logger = logging.getLogger(__name__)


@dataclass
class SynthesisOutput:
    why_own_it: str
    must_remain_true: str
    what_would_change_my_mind: str
    ai_summary: str
    interpretation: dict


@dataclass
class CounterThesisOutput:
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    suggested_additions: list[str]


@dataclass
class ThesisAssistOutput:
    ai_summary: str
    interpretation: dict


VAGUE_PATTERNS = (
    r"\bfriend recommended\b",
    r"\brecommended it\b",
    r"\btip from\b",
    r"\beveryone was talking about it\b",
    r"\bnot sure\b",
    r"\bjust because\b",
    r"\bi like the stock\b",
    r"\blong[- ]term hold\b",
)
THEME_KEYWORDS = {
    "growth": ("growth", "demand", "expansion", "adoption"),
    "income": ("dividend", "income", "yield"),
    "quality": ("margin", "margins", "cash flow", "profitability", "resilient"),
    "valuation": ("valuation", "multiple", "cheap", "expensive", "pe", "p/e"),
    "theme": ("ai", "cloud", "energy", "semiconductor", "automation", "infrastructure"),
}
SUPPORTED_PROXY_METRICS = {
    "revenue_growth_yoy",
    "earnings_growth_yoy",
    "pe_ratio",
    "dividend_yield",
}
PROXY_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


THESIS_PROMPT = """You are an investment thesis assistant helping a retail investor clarify why they own a position.

Given the position, the user's rough draft, and any available market data, produce:
- a concise summary of the likely thesis in plain English
- a lightweight interpretation object that helps the product monitor or review the thesis

Position:
- Ticker: {ticker}
- Name: {name}
- Shares: {quantity}
- Average cost: {average_cost}
- User draft: {draft_text}

{market_data_section}

Output valid JSON with this exact structure:
{{
    "ai_summary": "2-3 sentences explaining the thesis in investor language.",
    "interpretation": {{
        "labels": ["theme_or_reason"],
        "monitorability": "high|medium|low",
        "watch_hints": [
            {{
                "kind": "price_move_pct" or "metric_threshold",
                "threshold": 10.0,
                "metric": "optional_metric_name",
                "operator": "optional_operator",
                "rationale": "Why this would matter to the thesis"
            }}
        ],
        "proxy_signals": [
            {{
                "ticker": "RELATED_TICKER",
                "rationale": "Why this company sits in the causal chain for the thesis",
                "signal_hint": "What specifically to look for in this proxy's earnings/news",
                "allowed_metrics": ["optional_metric_name"]
            }}
        ],
        "ambiguity_note": "Explain any vagueness or missing specificity."
    }}
}}

Requirements:
- If the user's draft is vague, say so directly in ambiguity_note
- Include 0-3 watch_hints total
- Include 0-3 proxy_signals: other tickers (never the held ticker itself) whose news or earnings would inform whether this thesis holds.
- For each proxy, include:
  - rationale: why it matters in the causal chain
  - signal_hint: the specific commentary, guidance, or operating signal to watch
  - allowed_metrics: only from revenue_growth_yoy, earnings_growth_yoy, pe_ratio, dividend_yield when they genuinely help
- Use price_move_pct only when a generic price review trigger is sensible
- Output ONLY valid JSON, no markdown fences"""



def _format_metric_pct(value: float | None) -> str:
    if value is None:
        return "Not available"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{pct:.1f}%"


def _build_market_data_section(market_data: Any | None) -> str:
    if not market_data:
        return "Market Data: Not available. Use your knowledge of this company."
    return (
        "Market Data:\n"
        f"- Sector: {market_data.sector}\n"
        f"- Industry: {market_data.industry}\n"
        f"- Revenue Growth: {_format_metric_pct(market_data.revenue_growth_yoy)}\n"
        f"- Earnings Growth: {_format_metric_pct(market_data.earnings_growth_yoy)}"
    )


async def _call_anthropic_json(
    *,
    prompt: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        timeout=30.0,
    )
    return json.loads(strip_code_fences(response.content[0].text))


def _fallback_assist(ticker: str, draft_text: str | None) -> ThesisAssistOutput:
    cleaned = (draft_text or "").strip()
    if cleaned:
        lowered = cleaned.lower()
        is_vague = any(re.search(pattern, lowered) for pattern in VAGUE_PATTERNS) or len(cleaned.split()) < 5
        labels = [
            label
            for label, keywords in THEME_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        ] or ["user_defined"]
        monitorability = "low" if is_vague else "medium"
        watch_hints = [] if is_vague else [
            {
                "kind": "price_move_pct",
                "threshold": 5.0,
                "rationale": "Prompt a review when price moves sharply.",
            }
        ]
        if not is_vague and any(keyword in lowered for keyword in ("growth", "demand", "adoption")):
            watch_hints.append(
                {
                    "kind": "metric_threshold",
                    "metric": "revenue_growth_yoy",
                    "operator": ">=",
                    "threshold": 0.0,
                    "rationale": "Revenue growth should stay positive if the thesis depends on demand expansion.",
                }
            )
        if not is_vague and any(keyword in lowered for keyword in ("margin", "margins", "profitability")):
            watch_hints.append(
                {
                    "kind": "metric_threshold",
                    "metric": "earnings_growth_yoy",
                    "operator": ">=",
                    "threshold": 0.0,
                    "rationale": "Earnings growth should remain healthy if margins are a key part of the thesis.",
                }
            )
        ai_summary = f"{ticker} thesis draft: {cleaned}"
        interpretation = {
            "labels": labels[:3],
            "monitorability": monitorability,
            "watch_hints": watch_hints[:3],
            "proxy_signals": [],
            "ambiguity_note": "The reason is still vague and may need clarification before monitoring can be precise." if is_vague else "",
        }
    else:
        ai_summary = f"No clear thesis draft was provided for {ticker}."
        interpretation = {
            "labels": ["unclear"],
            "monitorability": "low",
            "watch_hints": [],
            "proxy_signals": [],
            "ambiguity_note": "The user has not given enough detail to monitor this thesis well.",
        }
    return ThesisAssistOutput(ai_summary=ai_summary, interpretation=interpretation)


async def _call_claude(prompt: str) -> ThesisAssistOutput:
    data = await _call_anthropic_json(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
    )
    return ThesisAssistOutput(
        ai_summary=data["ai_summary"],
        interpretation=data["interpretation"],
    )


def _parse_assist_output(result: ThesisAssistOutput) -> ThesisAssistOutput:
    if not result.ai_summary or not isinstance(result.interpretation, dict):
        raise ValueError("Incomplete thesis output")
    return ThesisAssistOutput(
        ai_summary=result.ai_summary,
        interpretation=_normalize_interpretation(result.interpretation),
    )


def _parse_counter_thesis_output(data: dict[str, Any]) -> CounterThesisOutput:
    bear_case = data.get("bear_case")
    key_risks = data.get("key_risks")
    blind_spots = data.get("blind_spots")
    suggested_additions = data.get("suggested_additions")
    if not isinstance(bear_case, str):
        raise ValueError("Missing bear_case")
    if not isinstance(key_risks, list) or not isinstance(blind_spots, list) or not isinstance(suggested_additions, list):
        raise ValueError("Invalid counter-thesis payload")
    return CounterThesisOutput(
        bear_case=bear_case,
        key_risks=[str(item) for item in key_risks if str(item).strip()][:5],
        blind_spots=[str(item) for item in blind_spots if str(item).strip()][:3],
        suggested_additions=[str(item) for item in suggested_additions if str(item).strip()][:3],
    )


def _parse_draft_output(data: dict[str, Any], ticker: str) -> dict[str, str]:
    why_own_it = data.get("why_own_it")
    must_remain_true = data.get("must_remain_true")
    what_would_change_my_mind = data.get("what_would_change_my_mind")
    if not all(isinstance(item, str) for item in (why_own_it, must_remain_true, what_would_change_my_mind)):
        raise ValueError("Invalid draft payload")
    return {
        "why_own_it": why_own_it.strip() or f"Investing in {ticker} for its long term potential.",
        "must_remain_true": must_remain_true.strip() or "The company maintains its market position.",
        "what_would_change_my_mind": what_would_change_my_mind.strip() or "A fundamental change in the business model.",
    }


def _normalize_interpretation(interpretation: dict | None) -> dict:
    data = interpretation if isinstance(interpretation, dict) else {}

    labels = data.get("labels")
    if not isinstance(labels, list):
        labels = []
    normalized_labels = [str(label).strip() for label in labels if str(label).strip()][:3]

    monitorability = data.get("monitorability")
    if monitorability not in {"high", "medium", "low"}:
        monitorability = "medium" if normalized_labels else "low"

    ambiguity_note = data.get("ambiguity_note")
    if not isinstance(ambiguity_note, str):
        ambiguity_note = ""

    normalized_watch_hints: list[dict] = []
    for hint in data.get("watch_hints", []) if isinstance(data.get("watch_hints"), list) else []:
        if not isinstance(hint, dict):
            continue
        kind = hint.get("kind")
        if kind == "price_move_pct":
            threshold = hint.get("threshold")
            if isinstance(threshold, (int, float)):
                normalized_watch_hints.append(
                    {
                        "kind": "price_move_pct",
                        "threshold": float(threshold),
                        "rationale": str(hint.get("rationale", "")).strip(),
                    }
                )
        elif kind == "metric_threshold":
            metric = hint.get("metric")
            operator = hint.get("operator")
            threshold = hint.get("threshold")
            if (
                isinstance(metric, str)
                and isinstance(operator, str)
                and operator in {">=", "<=", ">", "<", "=="}
                and isinstance(threshold, (int, float))
            ):
                normalized_watch_hints.append(
                    {
                        "kind": "metric_threshold",
                        "metric": metric,
                        "operator": operator,
                        "threshold": float(threshold),
                        "rationale": str(hint.get("rationale", "")).strip(),
                    }
                )

    if monitorability in {"high", "medium"} and not any(hint.get("kind") == "price_move_pct" for hint in normalized_watch_hints):
        normalized_watch_hints.insert(
            0,
            {
                "kind": "price_move_pct",
                "threshold": 5.0,
                "rationale": "Prompt a review when price moves sharply.",
            },
        )

    normalized_proxy_signals: list[dict[str, object]] = []
    seen_proxy_tickers: set[str] = set()
    for signal in data.get("proxy_signals", []) if isinstance(data.get("proxy_signals"), list) else []:
        if not isinstance(signal, dict):
            continue
        proxy_ticker = signal.get("ticker")
        rationale = signal.get("rationale", "")
        signal_hint = signal.get("signal_hint", "")
        allowed_metrics = signal.get("allowed_metrics", [])
        if isinstance(proxy_ticker, str) and proxy_ticker.strip():
            upper_ticker = proxy_ticker.strip().upper()
            if not PROXY_TICKER_PATTERN.match(upper_ticker):
                continue
            if upper_ticker not in seen_proxy_tickers:
                entry: dict[str, object] = {"ticker": upper_ticker, "rationale": str(rationale).strip()}
                if isinstance(signal_hint, str) and signal_hint.strip():
                    entry["signal_hint"] = signal_hint.strip()
                if isinstance(allowed_metrics, list):
                    normalized_allowed_metrics = [
                        str(metric).strip()
                        for metric in allowed_metrics
                        if str(metric).strip() in SUPPORTED_PROXY_METRICS
                    ]
                    if normalized_allowed_metrics:
                        entry["allowed_metrics"] = normalized_allowed_metrics[:3]
                normalized_proxy_signals.append(entry)
                seen_proxy_tickers.add(upper_ticker)

    return {
        "labels": normalized_labels or ["user_defined"],
        "monitorability": monitorability,
        "watch_hints": normalized_watch_hints[:3],
        "proxy_signals": normalized_proxy_signals[:3],
        "ambiguity_note": ambiguity_note,
    }


async def assist_thesis(
    ticker: str,
    name: str,
    quantity: float,
    average_cost: float,
    draft_text: str | None,
) -> ThesisAssistOutput | None:
    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for thesis assist on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)

    prompt = THESIS_PROMPT.format(
        ticker=ticker,
        name=name,
        quantity=quantity,
        average_cost=average_cost,
        draft_text=(draft_text or "None provided"),
        market_data_section=market_data_section,
    )

    try:
        if not settings.anthropic_api_key:
            return _fallback_assist(ticker=ticker, draft_text=draft_text)
        result = await _call_claude(prompt)
        return _parse_assist_output(result)
    except Exception as e:
        logger.error(f"Thesis generation failed for {ticker}: {e}")
        try:
            result = await _call_claude(prompt + "\n\nIMPORTANT: Output ONLY valid JSON.")
            return _parse_assist_output(result)
        except Exception:
            logger.error(f"Thesis generation retry failed for {ticker}")
            return _fallback_assist(ticker=ticker, draft_text=draft_text)


COUNTER_THESIS_PROMPT = """You are a devil's advocate investment analyst. Given a retail investor's thesis for holding a stock, generate a structured counter-argument to sharpen their thinking.

Ticker: {ticker}
Why they own it: {why_own_it}
Must remain true: {must_remain_true}
What would change their mind: {what_would_change_my_mind}
AI Summary of thesis: {ai_summary}

Output valid JSON with this exact structure:
{{
    "bear_case": "2-3 sentences presenting the strongest bear case against this thesis.",
    "key_risks": ["risk1", "risk2", "risk3"],
    "blind_spots": ["blind_spot1", "blind_spot2"],
    "suggested_additions": ["suggested_addition1", "suggested_addition2"]
}}

Requirements:
- bear_case: 2-3 sentences, be specific and reference the actual thesis points
- key_risks: 3-5 concrete risks the investor should monitor
- blind_spots: 2-3 things the thesis doesn't address but should
- suggested_additions: 2-3 specific "what would change my mind" criteria the investor should add
- Be constructive but challenging — the goal is to make the investor think harder
- Output ONLY valid JSON, no markdown fences"""


def _fallback_counter_thesis(
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    ticker: str,
) -> CounterThesisOutput:
    lowered = (why_own_it or "").lower()
    labels = [
        label
        for label, keywords in THEME_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ] or ["general"]

    bear_case = (
        f"The bull case for {ticker} may be overly optimistic. "
        f"Investors should consider whether the thesis assumptions around "
        f"{', '.join(labels)} are already priced in or face structural headwinds."
    )

    key_risks = [
        f"Competitive pressure could erode {ticker}'s position",
        "Macroeconomic downturn may reduce demand",
        "Valuation may already reflect the optimistic scenario",
    ]
    if "growth" in labels:
        key_risks.append("Growth deceleration could trigger a re-rating")
    if "income" in labels:
        key_risks.append("Dividend sustainability under earnings pressure")

    blind_spots = [
        "Regulatory or geopolitical risks not addressed in thesis",
        "Management execution risk and capital allocation decisions",
    ]

    suggested_additions = [
        "Set a specific valuation ceiling where the risk/reward no longer holds",
        "Define a timeline for thesis milestones to be achieved",
    ]
    if not what_would_change_my_mind or len(what_would_change_my_mind.strip()) < 10:
        suggested_additions.append(
            "Add concrete, measurable exit criteria rather than vague conditions"
        )

    return CounterThesisOutput(
        bear_case=bear_case,
        key_risks=key_risks[:5],
        blind_spots=blind_spots[:3],
        suggested_additions=suggested_additions[:3],
    )


async def generate_counter_thesis(
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    ticker: str,
) -> CounterThesisOutput:
    if not settings.anthropic_api_key:
        return _fallback_counter_thesis(
            why_own_it=why_own_it,
            must_remain_true=must_remain_true,
            what_would_change_my_mind=what_would_change_my_mind,
            ai_summary=ai_summary,
            ticker=ticker,
        )

    prompt = COUNTER_THESIS_PROMPT.format(
        ticker=ticker,
        why_own_it=why_own_it or "Not provided",
        must_remain_true=must_remain_true or "Not provided",
        what_would_change_my_mind=what_would_change_my_mind or "Not provided",
        ai_summary=ai_summary or "Not provided",
    )

    try:
        data = await _call_anthropic_json(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
        )
        return _parse_counter_thesis_output(data)
    except Exception as e:
        logger.error(f"Counter-thesis generation failed for {ticker}: {e}")
        return _fallback_counter_thesis(
            why_own_it=why_own_it,
            must_remain_true=must_remain_true,
            what_would_change_my_mind=what_would_change_my_mind,
            ai_summary=ai_summary,
            ticker=ticker,
        )


DRAFT_THESIS_PROMPT = """You are a smart investing assistant helping a retail investor draft a thesis for a specific stock.
Write a crisp, specific bull case using concrete numbers and named conditions — not generic language.

Rules:
- Use specific metrics: revenue growth rates, margins, market share percentages, P/E or EV/EBITDA ranges, unit economics.
- Name the key driver (product cycle, regulatory moat, network effects, etc.) rather than describing it generically.
- must_remain_true must contain at least one measurable threshold (e.g. "revenue growth above 15% YoY", "gross margin above 60%", "FCF positive by FY2026").
- what_would_change_my_mind must name a specific event or threshold breach (e.g. "market share falls below 40%", "operating margin compresses below 10%", "loses key customer accounting for >20% of revenue").
- Do NOT write phrases like "maintains competitive advantage", "long-term potential", or "solid fundamentals" — these are too vague to monitor.

Ticker: {ticker}
{market_data_section}

Output valid JSON with this exact structure:
{{
    "why_own_it": "2-3 sentences citing the specific business driver and supporting metrics (include at least one number).",
    "must_remain_true": "The concrete, measurable condition(s) that must hold for the thesis to stay valid.",
    "what_would_change_my_mind": "The specific event or threshold breach that would trigger a sell."
}}

Output ONLY valid JSON, no markdown fences."""

async def generate_initial_draft(ticker: str) -> dict[str, str]:
    if not settings.anthropic_api_key:
        return {
            "why_own_it": f"A solid holding in the portfolio. Believing in the long-term growth and market position of {ticker}.",
            "must_remain_true": "The core business continues to grow and maintain its competitive advantage.",
            "what_would_change_my_mind": "A fundamental shift in the industry or consistent revenue decline.",
        }

    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for draft thesis on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)

    prompt = DRAFT_THESIS_PROMPT.format(
        ticker=ticker,
        market_data_section=market_data_section,
    )

    try:
        data = await _call_anthropic_json(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            max_tokens=500,
        )
        return _parse_draft_output(data, ticker)
    except Exception as e:
        logger.error(f"Draft thesis generation failed for {ticker}: {e}")
        return {
            "why_own_it": f"Investing in {ticker} for its long term potential.",
            "must_remain_true": "The company maintains its market position.",
            "what_would_change_my_mind": "A fundamental change in the business model.",
        }


# ---------------------------------------------------------------------------
# Wizard synthesis — construct a thesis from two Q&A answers
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """You are an investment thesis assistant helping a retail investor articulate their investment thesis.

Based on the investor's answers to two simple questions, synthesise a well-structured thesis that preserves their voice.

Position:
- Ticker: {ticker}
- Name: {name}

{market_data_section}

Investor's answers:
- Q: {question1}
  A: {answer1}

- Q: {question2}
  A: {answer2}

Output valid JSON with this exact structure:
{{
    "why_own_it": "2-3 sentences in the investor's own voice explaining their main reason for holding.",
    "must_remain_true": "1 sentence on the key assumption that must hold for this thesis to stay valid.",
    "what_would_change_my_mind": "1 sentence on what would cause them to reconsider or exit the position.",
    "ai_summary": "2-3 sentences summarising the thesis in plain investor language.",
    "interpretation": {{
        "labels": ["theme_or_reason"],
        "monitorability": "high|medium|low",
        "watch_hints": [
            {{
                "kind": "price_move_pct",
                "threshold": 10.0,
                "rationale": "Why this would matter to the thesis"
            }}
        ],
        "proxy_signals": [],
        "ambiguity_note": "Explain any vagueness or missing specificity."
    }}
}}

Requirements:
- Preserve the investor's voice in why_own_it — do not sanitise into corporate-speak
- must_remain_true should follow logically from why_own_it
- what_would_change_my_mind should align closely with their answer to Q2
- Include 0-2 watch_hints, keep them concrete and directly tied to the thesis
- Output ONLY valid JSON, no markdown fences"""


def _fallback_synthesize(ticker: str, answer1: str, answer2: str) -> SynthesisOutput:
    why_own_it = answer1.strip() or f"Investing in {ticker} for long-term growth."
    what_would_change_my_mind = answer2.strip() or "A fundamental change in the business model."
    lowered = why_own_it.lower()
    labels = [
        label
        for label, keywords in THEME_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ] or ["user_defined"]
    return SynthesisOutput(
        why_own_it=why_own_it,
        must_remain_true=f"The core investment thesis for {ticker} remains intact.",
        what_would_change_my_mind=what_would_change_my_mind,
        ai_summary=f"{ticker}: {why_own_it[:150]}",
        interpretation={
            "labels": labels[:3],
            "monitorability": "medium",
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 5.0, "rationale": "Prompt a review when price moves sharply."}
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        },
    )


def _parse_synthesis_output(data: dict[str, Any], ticker: str) -> SynthesisOutput:
    why_own_it = data.get("why_own_it")
    must_remain_true = data.get("must_remain_true")
    what_would_change_my_mind = data.get("what_would_change_my_mind")
    ai_summary = data.get("ai_summary")
    interpretation = data.get("interpretation")
    if not all(isinstance(v, str) for v in (why_own_it, must_remain_true, what_would_change_my_mind, ai_summary)):
        raise ValueError("Invalid synthesis payload")
    return SynthesisOutput(
        why_own_it=why_own_it.strip() or f"Investing in {ticker} for long-term potential.",
        must_remain_true=must_remain_true.strip() or "The company maintains its market position.",
        what_would_change_my_mind=what_would_change_my_mind.strip() or "A fundamental change in the business model.",
        ai_summary=ai_summary.strip(),
        interpretation=_normalize_interpretation(interpretation),
    )


async def synthesize_thesis_from_qa(
    ticker: str,
    name: str,
    question1: str,
    answer1: str,
    question2: str,
    answer2: str,
) -> SynthesisOutput:
    if not settings.anthropic_api_key:
        return _fallback_synthesize(ticker=ticker, answer1=answer1, answer2=answer2)

    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for synthesis on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)

    prompt = SYNTHESIS_PROMPT.format(
        ticker=ticker,
        name=name,
        question1=question1,
        answer1=answer1 or "Not provided",
        question2=question2,
        answer2=answer2 or "Not provided",
        market_data_section=market_data_section,
    )

    try:
        data = await _call_anthropic_json(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
        )
        return _parse_synthesis_output(data, ticker)
    except Exception as e:
        logger.error("Synthesis failed for %s: %s", ticker, e)
        return _fallback_synthesize(ticker=ticker, answer1=answer1, answer2=answer2)


# ---------------------------------------------------------------------------
# Background draft generation — called after portfolio import
# ---------------------------------------------------------------------------

async def generate_draft_theses_for_user(
    user_id: uuid.UUID,
    holding_ids: list[uuid.UUID] | None = None,
) -> None:
    """Generate AI draft theses for up to 3 undrafted holdings.

    Designed to run as a FastAPI BackgroundTask — opens its own DB session.
    Creates OnboardingDraft rows (pending → ready/failed) and saves
    Thesis(status='draft', source='ai_draft') for each success.
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.holding import Holding
    from app.models.onboarding_draft import OnboardingDraft
    from app.models.onboarding_state import OnboardingState
    from app.models.thesis import Thesis

    async with async_session() as db:
        existing_thesis_sq = (
            select(Thesis.id)
            .where(Thesis.holding_id == Holding.id)
            .where(Thesis.status != "invalidated")
            .correlate(Holding)
            .limit(1)
        )
        q = (
            select(Holding)
            .where(Holding.user_id == user_id)
            .where(~existing_thesis_sq.exists())
            .order_by(func.coalesce(Holding.current_value, 0).desc())
            .limit(3)
        )
        if holding_ids:
            q = q.where(Holding.id.in_(holding_ids))

        result = await db.execute(q)
        holdings = result.scalars().all()

        if not holdings:
            return

        now = datetime.now(timezone.utc)

        # Phase 1 (sequential): create pending draft records and flush to get IDs before the
        # concurrent AI phase. SQLAlchemy sessions are not concurrency-safe, so DB work must
        # be sequential even though the AI calls run concurrently in Phase 2.
        draft_records: list[tuple[Holding, OnboardingDraft]] = []
        for holding in holdings:
            draft = OnboardingDraft(user_id=user_id, holding_id=holding.id, status="pending")
            db.add(draft)
            await db.flush()
            draft_records.append((holding, draft))

        # Phase 2 (concurrent): AI calls are safe to parallelize since they don't touch the DB session.
        async def _generate(holding: Holding) -> tuple[dict[str, str], ThesisAssistOutput | None] | Exception:
            try:
                draft_fields = await generate_initial_draft(holding.ticker)
                assist_result = await assist_thesis(
                    ticker=holding.ticker,
                    name=holding.name,
                    quantity=float(holding.quantity),
                    average_cost=float(holding.average_cost_basis),
                    draft_text=draft_fields["why_own_it"],
                )
                return (draft_fields, assist_result)
            except Exception as exc:
                return exc

        ai_results = await asyncio.gather(*[_generate(h) for h, _ in draft_records])

        # Phase 3 (sequential): add all thesis objects first, then a single flush to assign IDs.
        theses_to_link: list[tuple[OnboardingDraft, Thesis]] = []
        for (holding, draft), ai_result in zip(draft_records, ai_results):
            if isinstance(ai_result, Exception):
                logger.error("Background draft failed for %s (%s): %s", holding.id, holding.ticker, ai_result)
                draft.status = "failed"
                draft.error_message = str(ai_result)[:500]
                draft.updated_at = now
            else:
                draft_fields, assist_result = ai_result
                thesis = Thesis(
                    holding_id=holding.id,
                    user_id=user_id,
                    status="draft",
                    source="ai_draft",
                    confidence="medium",
                    why_own_it=draft_fields["why_own_it"],
                    must_remain_true=draft_fields["must_remain_true"],
                    what_would_change_my_mind=draft_fields["what_would_change_my_mind"],
                    ai_summary=assist_result.ai_summary if assist_result else None,
                    interpretation=assist_result.interpretation if assist_result else None,
                )
                db.add(thesis)
                theses_to_link.append((draft, thesis))

        if theses_to_link:
            await db.flush()
            for draft, thesis in theses_to_link:
                draft.status = "ready"
                draft.thesis_id = thesis.id
                draft.updated_at = now

        state_result = await db.execute(
            select(OnboardingState).where(OnboardingState.user_id == user_id)
        )
        state = state_result.scalar_one_or_none()
        if state is not None:
            state.drafts_generated_at = now

        await db.commit()
