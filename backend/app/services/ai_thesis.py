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
    why_own_it: str
    must_remain_true: str
    what_would_change_my_mind: str
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
HEARSAY_PATTERNS = (
    r"\bheard\b",
    r"\bhearsay\b",
    r"\bbuzz\b",
    r"\bhype\b",
    r"\bchat(?:ter)?\b",
    r"\beveryone was talking about\b",
    r"\bpeople kept talking about\b",
    r"\bseemed like the one to own\b",
    r"\bstory\b",
    r"\bmomentum\b",
)
GENERIC_OUTPUT_PATTERNS = (
    r"\bcore investment thesis\b",
    r"\blong[- ]term potential\b",
    r"\bmarket position\b",
    r"\bbusiness model\b",
    r"\bfundamental change\b",
    r"\bremains intact\b",
)
GENERIC_CONDITION_PATTERNS = (
    r"\bcore investment thesis\b",
    r"\bremains intact\b",
    r"\bmarket position\b",
    r"\bbusiness model\b",
    r"\blong[- ]term potential\b",
    r"\bfundamental change\b",
    r"\boriginal reason for owning\b",
)
GENERIC_DRAFT_PATTERNS = (
    r"\bcore position in the portfolio\b",
    r"\blong[- ]term potential\b",
    r"\bmaintains (?:its )?market position\b",
    r"\bfundamental change in the business model\b",
    r"\bedit this\b",
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
OPENAI_ASSIST_MODEL = "gpt-4.1-mini"

THESIS_ASSIST_WATCH_HINT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["price_move_pct", "metric_threshold"]},
        "threshold": {"type": "number"},
        "metric": {"type": "string"},
        "operator": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["kind", "threshold", "metric", "operator", "rationale"],
    "additionalProperties": False,
}

THESIS_ASSIST_PROXY_SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string"},
        "rationale": {"type": "string"},
        "signal_hint": {"type": "string"},
        "allowed_metrics": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["ticker", "rationale", "signal_hint", "allowed_metrics"],
    "additionalProperties": False,
}

THESIS_ASSIST_INTERPRETATION_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {"type": "string"},
        },
        "monitorability": {"type": "string", "enum": ["high", "medium", "low"]},
        "watch_hints": {
            "type": "array",
            "items": THESIS_ASSIST_WATCH_HINT_SCHEMA,
        },
        "proxy_signals": {
            "type": "array",
            "items": THESIS_ASSIST_PROXY_SIGNAL_SCHEMA,
        },
        "ambiguity_note": {"type": "string"},
    },
    "required": ["labels", "monitorability", "watch_hints", "proxy_signals", "ambiguity_note"],
    "additionalProperties": False,
}


THESIS_ASSIST_FROM_BLANK_PROMPT = """Draft a first-pass reason for holding a specific stock, in the investor's own first-person voice.
The investor hasn't written anything yet — generate a starting point they can edit and make their own.

Position:
- Ticker: {ticker}
- Name: {name}
- Shares: {quantity}
- Average cost: {average_cost}

{market_data_section}

Rules:
- Write in first person throughout: "I own this because...", "I need...", "I'd sell if..."
- Name the specific business driver rather than describing it vaguely.
- must_remain_true: a specific, observable condition — not "maintains competitive advantage" or "continues to grow".
- what_would_change_my_mind: a specific event or scenario, not a vague "if the business deteriorates".
- Sound like a thoughtful individual investor, not a sell-side analyst.
- Do NOT use phrases like "long-term potential", "solid fundamentals", or "maintains market position".
- Ground the draft in the recent news headlines provided above — reference what is actually happening now, not generic statements from your training data. If recent news is not provided, use what you know but keep claims conservative.

Output valid JSON with this exact structure:
{{
    "why_own_it": "First-person, 2-3 sentences: 'I own this because [specific driver]...'",
    "must_remain_true": "First-person: the specific condition(s) the investor needs to stay true.",
    "what_would_change_my_mind": "First-person: the specific event or scenario that would make them sell.",
    "ai_summary": "2-3 sentences summarising the thesis in plain English.",
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
        "proxy_signals": [],
        "ambiguity_note": ""
    }}
}}

- Include 0-3 watch_hints. For growth metrics, only set a threshold if you can infer a specific rate from the position data; never use 0. Thresholds for growth metrics are decimal fractions (0.10 = 10%).
- For structured output compatibility, every watch_hint must include metric and operator strings (use empty strings for price_move_pct).
- Output ONLY valid JSON, no markdown fences."""


THESIS_PROMPT = """You help a retail investor tighten why they own a position — same meaning, clearer words.

Given the position, the user's current thesis draft, and any available market data, produce:
- refined thesis text that preserves the investor's meaning while making it clearer and more monitorable
- a concise summary of the likely thesis in plain English
- a lightweight interpretation object that helps the product monitor or review the thesis

Position:
- Ticker: {ticker}
- Name: {name}
- Shares: {quantity}
- Average cost: {average_cost}
- Own it because: {why_own_it}
- Must remain true: {must_remain_true}
- What would change their mind: {what_would_change_my_mind}

{market_data_section}

Output valid JSON with this exact structure:
{{
    "why_own_it": "First-person: 'I own this because...' — refined version of the investor's own reason, in their voice.",
    "must_remain_true": "First-person or direct: the specific condition(s) the investor needs to stay true.",
    "what_would_change_my_mind": "First-person or direct: the specific event or scenario that would make the investor sell.",
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
- Preserve the investor's core meaning and tone; refine, don't replace.
- Make each field more concrete, specific, and monitorable when possible.
- If one field is missing, infer a reasonable version from the others instead of leaving it blank.
- If the user's draft is vague, say so directly in ambiguity_note
- Include 0-3 watch_hints total
- For structured output compatibility, every watch_hint must include metric and operator strings. Use empty strings when kind is price_move_pct and those fields do not apply.
- For growth metrics (revenue_growth_yoy, earnings_growth_yoy), only include a watch_hint if you can infer a meaningful threshold from the thesis (e.g. 10%, 15%). Never use 0 as a threshold — if no specific rate is implied, omit the hint entirely.
- Thresholds for growth metrics are expressed as decimal fractions (e.g. 0.10 means 10%).
- Include 0-3 proxy_signals: other tickers (never the held ticker itself) whose news or earnings would inform whether this thesis holds.
- For each proxy, include:
  - rationale: why it matters in the causal chain
  - signal_hint: the specific commentary, guidance, or operating signal to watch
  - allowed_metrics: only from revenue_growth_yoy, earnings_growth_yoy, pe_ratio, dividend_yield when they genuinely help
- For structured output compatibility, every proxy_signal must include allowed_metrics. Use an empty array when no metric is needed.
- Use price_move_pct only when a generic price review trigger is sensible
- Output ONLY valid JSON, no markdown fences"""

THESIS_ASSIST_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "why_own_it": {"type": "string"},
        "must_remain_true": {"type": "string"},
        "what_would_change_my_mind": {"type": "string"},
        "ai_summary": {"type": "string"},
        "interpretation": THESIS_ASSIST_INTERPRETATION_SCHEMA,
    },
    "required": [
        "why_own_it",
        "must_remain_true",
        "what_would_change_my_mind",
        "ai_summary",
        "interpretation",
    ],
    "additionalProperties": False,
}



def _format_metric_pct(value: float | None) -> str:
    if value is None:
        return "Not available"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{pct:.1f}%"


def _text_matches_patterns(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _dedupe_watch_hints(watch_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for hint in watch_hints:
        key = (
            hint.get("kind"),
            hint.get("metric"),
            hint.get("operator"),
            hint.get("threshold"),
        )
        if key in seen:
            continue
        deduped.append(hint)
        seen.add(key)
    return deduped


def _infer_story_watch_hints(text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    watch_hints: list[dict[str, Any]] = [
        {
            "kind": "price_move_pct",
            "threshold": 5.0,
            "rationale": "Prompt a review when price moves sharply.",
        }
    ]
    # Only trigger on explicit revenue/unit language — "growth", "AI", "demand" alone are too generic
    if any(keyword in lowered for keyword in ("revenue", "sales", "orders", "bookings", "subscribers", "users", "capex", "top line", "top-line")):
        watch_hints.append(
            {
                "kind": "metric_threshold",
                "metric": "revenue_growth_yoy",
                "operator": ">=",
                "threshold": 0.0,
                "rationale": "Revenue growth must stay positive to validate this thesis.",
            }
        )
    if any(keyword in lowered for keyword in ("margin", "margins", "profit", "profitability", "earnings", "cash flow", "ebitda", "eps")):
        watch_hints.append(
            {
                "kind": "metric_threshold",
                "metric": "earnings_growth_yoy",
                "operator": ">=",
                "threshold": 0.0,
                "rationale": "The thesis depends on profitable execution — monitor earnings growth.",
            }
        )
    return _dedupe_watch_hints(watch_hints)[:3]


def _infer_hearsay_conditions(ticker: str, answer1: str, answer2: str) -> tuple[str, str, str]:
    combined = f"{answer1} {answer2}".strip()
    lowered = combined.lower()

    ambiguity_note = (
        "Still sounds like story or chatter — name the business driver we should actually watch."
        if _text_matches_patterns(combined, HEARSAY_PATTERNS) or len(answer1.split()) < 8
        else ""
    )

    must_remain_true = (
        f"The original story in {ticker} needs to keep showing up in measurable business performance rather than sentiment alone."
    )
    what_would_change_my_mind = (
        "If the operating results and management commentary stop supporting the original story for multiple quarters, the position should be reconsidered."
    )

    if any(keyword in lowered for keyword in ("growth", "demand", "adoption", "sales", "orders", "capex", "ai")):
        must_remain_true = (
            f"The demand story in {ticker} needs to keep showing up in revenue growth, customer adoption, and management commentary."
        )
        what_would_change_my_mind = (
            "If demand weakens for multiple quarters or management commentary stops backing the original growth story, the position should be reconsidered."
        )
    elif any(keyword in lowered for keyword in ("margin", "margins", "profit", "profitability", "earnings", "cash flow")):
        must_remain_true = (
            f"{ticker} needs to turn the story into profitable execution rather than just narrative excitement."
        )
        what_would_change_my_mind = (
            "If margins or earnings deteriorate while the original story is still being sold aggressively, the thesis is weaker than it looks."
        )
    elif any(keyword in lowered for keyword in ("leader", "leadership", "moat", "ecosystem", "competitive")):
        must_remain_true = (
            f"{ticker} needs to keep showing real competitive strength in customer adoption, pricing, or product leadership."
        )
        what_would_change_my_mind = (
            "If credible competition starts eroding adoption, pricing power, or management confidence in the core story, the position should be reconsidered."
        )

    return must_remain_true, what_would_change_my_mind, ambiguity_note


def _infer_specific_conditions(
    ticker: str,
    *,
    why_text: str,
    change_text: str,
    investor_profile: str | None,
) -> tuple[str, str, str]:
    combined = f"{why_text} {change_text}".strip()
    lowered = combined.lower()

    if investor_profile == "hearsay_driven":
        return _infer_hearsay_conditions(ticker, why_text, change_text)

    ambiguity_note = (
        "Still vague — nail the business driver and what would make you sell before we can watch the right things."
        if len(why_text.split()) < 8 or _text_matches_patterns(combined, GENERIC_CONDITION_PATTERNS)
        else ""
    )

    must_remain_true = (
        f"{ticker} still needs to show measurable operating progress that directly supports the reason for owning it."
    )
    what_would_change_my_mind = (
        "If operating results or management commentary stop validating the core business driver for multiple quarters, the position should be reconsidered."
    )

    if any(keyword in lowered for keyword in ("growth", "demand", "adoption", "orders", "capex", "ai", "sales")):
        must_remain_true = (
            f"{ticker} needs to keep showing real demand in revenue growth, customer adoption, and management commentary."
        )
        what_would_change_my_mind = (
            "If demand softens for multiple quarters or management commentary stops supporting the growth driver behind the thesis, the position should be reconsidered."
        )
    elif any(keyword in lowered for keyword in ("margin", "margins", "profit", "profitability", "earnings", "cash flow")):
        must_remain_true = (
            f"{ticker} needs to keep turning the thesis into healthy margins, earnings, or cash flow rather than just narrative momentum."
        )
        what_would_change_my_mind = (
            "If margins, earnings, or cash generation deteriorate for multiple quarters, the position should be reconsidered."
        )
    elif any(keyword in lowered for keyword in ("moat", "ecosystem", "leadership", "competitive", "pricing power")):
        must_remain_true = (
            f"{ticker} needs to keep showing competitive strength through customer adoption, pricing power, or product leadership."
        )
        what_would_change_my_mind = (
            "If credible competition starts eroding adoption, pricing power, or management confidence in the competitive edge, the position should be reconsidered."
        )
    elif any(keyword in lowered for keyword in ("valuation", "multiple", "cheap", "expensive", "p/e", "pe")):
        must_remain_true = (
            f"{ticker} needs to keep delivering enough business performance to justify the valuation being paid today."
        )
        what_would_change_my_mind = (
            "If business performance no longer justifies the valuation or management guidance weakens materially, the position should be reconsidered."
        )

    return must_remain_true, what_would_change_my_mind, ambiguity_note


def _looks_generic_output(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped.split()) < 6:
        return True
    return _text_matches_patterns(stripped, GENERIC_OUTPUT_PATTERNS)


def _infer_market_driver(ticker: str, market_data: Any | None) -> tuple[str, str, str]:
    sector = getattr(market_data, "sector", None) or "its market"
    industry = getattr(market_data, "industry", None) or "its category"
    revenue_growth = getattr(market_data, "revenue_growth_yoy", None)
    earnings_growth = getattr(market_data, "earnings_growth_yoy", None)

    if isinstance(revenue_growth, (int, float)) and revenue_growth > 0.08:
        return (
            f"{ticker} looks interesting because the business is still showing real demand in {industry.lower()}, not just narrative momentum.",
            f"Revenue growth and management commentary in {industry.lower()} need to keep supporting the demand story.",
            f"If revenue growth stalls or management stops supporting the current demand story in {industry.lower()}, the position should be reconsidered.",
        )
    if isinstance(earnings_growth, (int, float)) and earnings_growth > 0.08:
        return (
            f"{ticker} looks interesting because the company is turning its position in {sector.lower()} into actual earnings momentum.",
            f"Earnings growth needs to stay healthy enough to show the business case is real rather than thematic excitement alone.",
            f"If earnings momentum fades for multiple quarters or margins deteriorate sharply, the position should be reconsidered.",
        )
    return (
        f"{ticker} looks interesting if the company can turn its position in {industry.lower()} into durable operating results rather than just investor excitement.",
        f"The business needs to keep showing measurable progress in demand, execution, or profitability within {industry.lower()}.",
        f"If operating results stop validating the current story around {ticker}, the position should be reconsidered.",
    )


def _fallback_initial_draft(ticker: str, market_data: Any | None = None) -> dict[str, str]:
    why_own_it, must_remain_true, what_would_change_my_mind = _infer_market_driver(ticker, market_data)
    return {
        "why_own_it": why_own_it,
        "must_remain_true": must_remain_true,
        "what_would_change_my_mind": what_would_change_my_mind,
    }


def _apply_synthesis_guardrails(
    output: SynthesisOutput,
    *,
    ticker: str,
    answer1: str,
    answer2: str,
    investor_profile: str | None,
) -> SynthesisOutput:
    interpretation = _normalize_interpretation(output.interpretation)
    why_own_it = output.why_own_it.strip()
    must_remain_true = output.must_remain_true.strip()
    what_would_change_my_mind = output.what_would_change_my_mind.strip()
    ai_summary = output.ai_summary.strip()

    if investor_profile != "hearsay_driven":
        inferred_must, inferred_change, inferred_ambiguity = _infer_specific_conditions(
            ticker,
            why_text=why_own_it or answer1,
            change_text=what_would_change_my_mind or answer2,
            investor_profile=investor_profile,
        )
        if _looks_generic_output(must_remain_true) or _text_matches_patterns(must_remain_true, GENERIC_CONDITION_PATTERNS):
            must_remain_true = inferred_must
        if _looks_generic_output(what_would_change_my_mind) or _text_matches_patterns(what_would_change_my_mind, GENERIC_CONDITION_PATTERNS):
            what_would_change_my_mind = inferred_change
        if not interpretation.get("ambiguity_note") and inferred_ambiguity:
            interpretation["ambiguity_note"] = inferred_ambiguity
        if not any(hint.get("kind") == "metric_threshold" for hint in interpretation["watch_hints"]):
            interpretation["watch_hints"] = _dedupe_watch_hints(
                [*interpretation["watch_hints"], *_infer_story_watch_hints(f"{why_own_it} {answer1} {answer2}")]
            )[:3]
        if interpretation["monitorability"] == "low" and any(
            hint.get("kind") == "metric_threshold" for hint in interpretation["watch_hints"]
        ):
            interpretation["monitorability"] = "medium"
        return SynthesisOutput(
            why_own_it=why_own_it or f"Investing in {ticker} for long-term potential.",
            must_remain_true=must_remain_true or inferred_must,
            what_would_change_my_mind=what_would_change_my_mind or inferred_change,
            ai_summary=ai_summary,
            interpretation=interpretation,
        )

    inferred_must, inferred_change, inferred_ambiguity = _infer_hearsay_conditions(ticker, answer1, answer2)
    combined_story_text = f"{why_own_it} {answer1} {answer2}".strip()

    if _looks_generic_output(must_remain_true):
        must_remain_true = inferred_must
    if _looks_generic_output(what_would_change_my_mind):
        what_would_change_my_mind = inferred_change
    if _text_matches_patterns(why_own_it or answer1, HEARSAY_PATTERNS):
        why_own_it = (
            why_own_it or answer1.strip() or f"This started as a rough idea in {ticker}."
        ).strip()
        if "operating results" not in why_own_it.lower() and "business performance" not in why_own_it.lower():
            why_own_it = f"{why_own_it} The case only holds if the underlying business results start validating that story."
    if not ai_summary:
        ai_summary = f"{ticker}: this started as a story-driven idea and only holds if the operating results validate it."

    inferred_watch_hints = _infer_story_watch_hints(combined_story_text)
    if not any(hint.get("kind") == "metric_threshold" for hint in interpretation["watch_hints"]):
        interpretation["watch_hints"] = _dedupe_watch_hints(
            [*interpretation["watch_hints"], *inferred_watch_hints]
        )[:3]
    if not interpretation.get("ambiguity_note") and inferred_ambiguity:
        interpretation["ambiguity_note"] = inferred_ambiguity
    if interpretation["monitorability"] == "low" and any(
        hint.get("kind") == "metric_threshold" for hint in interpretation["watch_hints"]
    ):
        interpretation["monitorability"] = "medium"

    return SynthesisOutput(
        why_own_it=why_own_it or f"Investing in {ticker} because the story still appears backed by the business.",
        must_remain_true=must_remain_true,
        what_would_change_my_mind=what_would_change_my_mind,
        ai_summary=ai_summary,
        interpretation=interpretation,
    )


def _build_market_data_section(market_data: Any | None) -> str:
    if not market_data:
        return "Market Data: Not available. Use your knowledge of this company."
    lines = [
        "Market Data:",
        f"- Sector: {market_data.sector}",
        f"- Industry: {market_data.industry}",
        f"- Revenue Growth: {_format_metric_pct(market_data.revenue_growth_yoy)}",
        f"- Earnings Growth: {_format_metric_pct(market_data.earnings_growth_yoy)}",
    ]
    recent_headlines = [h for h in (market_data.recent_news or []) if h][:5]
    if recent_headlines:
        lines.append("- Recent news (last 7 days, use these to ground the draft in current context):")
        for headline in recent_headlines:
            lines.append(f"  • {headline}")
    return "\n".join(lines)


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


async def _call_openai_json(
    *,
    prompt: str,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=model,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "thesis_assist",
                "strict": True,
                "schema": THESIS_ASSIST_JSON_SCHEMA,
            },
        },
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        timeout=30.0,
        max_tokens=max_tokens,
    )
    return json.loads(strip_code_fences(response.choices[0].message.content or "{}"))


def _coalesce_assist_fields(
    *,
    why_own_it: str | None,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    draft_text: str | None,
) -> tuple[str, str, str]:
    primary = (why_own_it or draft_text or "").strip()
    must = (must_remain_true or "").strip()
    change = (what_would_change_my_mind or "").strip()
    return primary, must, change


def _fallback_assist(
    ticker: str,
    *,
    why_own_it: str | None,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    draft_text: str | None,
) -> ThesisAssistOutput:
    cleaned, must, change = _coalesce_assist_fields(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true,
        what_would_change_my_mind=what_would_change_my_mind,
        draft_text=draft_text,
    )
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
        refined_must = must or (
            "Demand, execution, and the core business driver stay strong enough for the original reason to remain intact."
            if is_vague
            else "The specific business driver behind the thesis continues to hold."
        )
        refined_change = change or (
            "New evidence shows the original reason for owning this is no longer intact."
            if is_vague
            else "A measurable deterioration in the key business driver or execution would break the thesis."
        )
    else:
        ai_summary = f"No clear thesis draft was provided for {ticker}."
        interpretation = {
            "labels": ["unclear"],
            "monitorability": "low",
            "watch_hints": [],
            "proxy_signals": [],
            "ambiguity_note": "The user has not given enough detail to monitor this thesis well.",
        }
        cleaned = f"I own {ticker} because it fits my investment strategy."
        refined_must = "The underlying business case remains intact."
        refined_change = "Evidence shows the original investment case is no longer valid."
    return ThesisAssistOutput(
        why_own_it=cleaned,
        must_remain_true=refined_must,
        what_would_change_my_mind=refined_change,
        ai_summary=ai_summary,
        interpretation=interpretation,
    )


async def _call_claude(prompt: str) -> ThesisAssistOutput:
    data = await _call_anthropic_json(
        prompt=prompt,
        model=settings.anthropic_model,
        max_tokens=1500,
    )
    return ThesisAssistOutput(
        why_own_it=str(data["why_own_it"]),
        must_remain_true=str(data["must_remain_true"]),
        what_would_change_my_mind=str(data["what_would_change_my_mind"]),
        ai_summary=data["ai_summary"],
        interpretation=data["interpretation"],
    )


async def _call_openai_assist(prompt: str) -> ThesisAssistOutput:
    data = await _call_openai_json(
        prompt=prompt,
        model=OPENAI_ASSIST_MODEL,
        max_tokens=1500,
    )
    return ThesisAssistOutput(
        why_own_it=str(data["why_own_it"]),
        must_remain_true=str(data["must_remain_true"]),
        what_would_change_my_mind=str(data["what_would_change_my_mind"]),
        ai_summary=data["ai_summary"],
        interpretation=data["interpretation"],
    )


def _parse_assist_output(result: ThesisAssistOutput) -> ThesisAssistOutput:
    if (
        not result.why_own_it.strip()
        or not result.must_remain_true.strip()
        or not result.what_would_change_my_mind.strip()
        or not result.ai_summary
        or not isinstance(result.interpretation, dict)
    ):
        raise ValueError("Incomplete thesis output")
    return ThesisAssistOutput(
        why_own_it=result.why_own_it.strip(),
        must_remain_true=result.must_remain_true.strip(),
        what_would_change_my_mind=result.what_would_change_my_mind.strip(),
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


_STALE_ADMIN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bthe\s+biden\s+administration'?s?\b", re.IGNORECASE),
        "U.S. federal policy",
    ),
    (
        re.compile(r"\bbiden\s+administration'?s?\b", re.IGNORECASE),
        "U.S. federal policy",
    ),
)


def _sanitize_time_sensitive_references(text: str) -> str:
    cleaned = text.strip()
    for pattern, replacement in _STALE_ADMIN_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def _parse_draft_output(data: dict[str, Any], ticker: str) -> dict[str, str]:
    why_own_it = data.get("why_own_it")
    must_remain_true = data.get("must_remain_true")
    what_would_change_my_mind = data.get("what_would_change_my_mind")
    if not all(isinstance(item, str) for item in (why_own_it, must_remain_true, what_would_change_my_mind)):
        raise ValueError("Invalid draft payload")
    cleaned_why = _sanitize_time_sensitive_references(why_own_it)
    cleaned_must = _sanitize_time_sensitive_references(must_remain_true)
    cleaned_change = _sanitize_time_sensitive_references(what_would_change_my_mind)
    fallback = _fallback_initial_draft(ticker)
    return {
        "why_own_it": fallback["why_own_it"] if _text_matches_patterns(cleaned_why, GENERIC_DRAFT_PATTERNS) else cleaned_why,
        "must_remain_true": fallback["must_remain_true"] if _text_matches_patterns(cleaned_must, GENERIC_DRAFT_PATTERNS) else cleaned_must,
        "what_would_change_my_mind": fallback["what_would_change_my_mind"] if _text_matches_patterns(cleaned_change, GENERIC_DRAFT_PATTERNS) else cleaned_change,
    }


_RATIO_KEYWORDS = {"margin", "share", "growth", "yield", "rate", "pct", "percent", "coverage"}
_LABEL_ABBREVS = {"ai", "ml", "pe", "ev", "roi", "yoy", "qoq", "ytd"}


def _metric_label(metric: str) -> str:
    return " ".join(
        w.upper() if w in _LABEL_ABBREVS else w.capitalize()
        for w in metric.replace("_", " ").split()
    )


def _metric_unit(metric: str) -> str:
    lower = metric.lower()
    return "pct" if any(kw in lower for kw in _RATIO_KEYWORDS) else "number"


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
                        "label": _metric_label(metric),
                        "unit": _metric_unit(metric),
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
    why_own_it: str | None = None,
    must_remain_true: str | None = None,
    what_would_change_my_mind: str | None = None,
    *,
    allow_fallback: bool = True,
) -> ThesisAssistOutput | None:
    from app.services.market_data import _normalize_ticker
    clean_ticker = _normalize_ticker(ticker)

    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for thesis assist on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)

    refined_why_own_it, refined_must_remain_true, refined_change_mind = _coalesce_assist_fields(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true,
        what_would_change_my_mind=what_would_change_my_mind,
        draft_text=draft_text,
    )
    is_blank = not any([refined_why_own_it, refined_must_remain_true, refined_change_mind])
    if is_blank:
        prompt = THESIS_ASSIST_FROM_BLANK_PROMPT.format(
            ticker=clean_ticker,
            name=name,
            quantity=quantity,
            average_cost=average_cost,
            market_data_section=market_data_section,
        )
    else:
        prompt = THESIS_PROMPT.format(
            ticker=clean_ticker,
            name=name,
            quantity=quantity,
            average_cost=average_cost,
            why_own_it=refined_why_own_it or "None provided",
            must_remain_true=refined_must_remain_true or "None provided",
            what_would_change_my_mind=refined_change_mind or "None provided",
            market_data_section=market_data_section,
        )

    try:
        if not settings.anthropic_api_key:
            raise RuntimeError("Anthropic API key not configured")

        result = await _call_claude(prompt)
        return _parse_assist_output(result)
    except Exception as anthropic_error:
        logger.error("Anthropic thesis assist failed for %s: %s", ticker, anthropic_error)
        try:
            if not settings.anthropic_api_key:
                raise RuntimeError("Anthropic API key not configured")
            result = await _call_claude(
                prompt
                + "\n\nIMPORTANT: Return strictly valid JSON. Escape all quotes inside strings and do not emit markdown fences."
            )
            return _parse_assist_output(result)
        except Exception as anthropic_retry_error:
            logger.error("Anthropic thesis assist retry failed for %s: %s", ticker, anthropic_retry_error)
        try:
            if not settings.openai_api_key:
                raise RuntimeError("OpenAI API key not configured")
            result = await _call_openai_assist(prompt)
            return _parse_assist_output(result)
        except Exception as openai_error:
            logger.error("OpenAI thesis assist failed for %s: %s", ticker, openai_error)
            return (
                _fallback_assist(
                    ticker=ticker,
                    why_own_it=why_own_it,
                    must_remain_true=must_remain_true,
                    what_would_change_my_mind=what_would_change_my_mind,
                    draft_text=draft_text,
                )
                if allow_fallback
                else None
            )


COUNTER_THESIS_PROMPT = """You play skeptic on a retail investor's thesis. Stress-test their case; don't flatter it.

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
- Be specific and blunt where the thesis is thin — the goal is a harder, more falsifiable case
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
        f"You may be paying up for {ticker} on {', '.join(labels)} — "
        f"check whether that story is already in the price or running into real headwinds."
    )

    key_risks = [
        f"A competitor could take share or pricing power from {ticker}",
        "A downturn could hit demand harder than the bull case assumes",
        "The multiple may already bake in the good outcome",
    ]
    if "growth" in labels:
        key_risks.append("Growth could slow and trigger a multiple reset")
    if "income" in labels:
        key_risks.append("The dividend could come under pressure if earnings slip")

    blind_spots = [
        "Regulation or geopolitics you did not spell out",
        "Whether management can actually execute and allocate capital well",
    ]

    suggested_additions = [
        "Name a valuation level where you would no longer own it",
        "Name a date or milestone by which the thesis must show up in results",
    ]
    if not what_would_change_my_mind or len(what_would_change_my_mind.strip()) < 10:
        suggested_additions.append(
            "Add a measurable sell trigger — not 'if things get bad'"
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
            model=settings.anthropic_model,
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


DRAFT_THESIS_PROMPT = """Draft a first-pass reason for holding a specific stock, written in the investor's own voice.

Rules:
- Write in first person: "I own this because...", "I need to see...", "I'd sell if..."
- Name the specific business driver (e.g. AI inference demand, government contract backlog, network effects, regulatory moat) rather than describing it vaguely.
- must_remain_true must state a specific, observable condition — not platitudes like "maintains competitive advantage" or "continues to grow".
- what_would_change_my_mind must name a specific event or scenario that would signal the thesis is broken.
- Do NOT use phrases like "long-term potential", "solid fundamentals", or "maintains market position" — these cannot be monitored.
- Avoid named politicians or named administrations unless the user explicitly mentioned them. Prefer neutral wording like "U.S. federal policy", "regulatory standards", or "government incentives".
- Sound like a thoughtful individual investor, not a sell-side analyst.

Ticker: {ticker}
{market_data_section}

Output valid JSON with this exact structure:
{{
    "why_own_it": "First-person, 2-3 sentences: 'I own this because [specific driver]...'",
    "must_remain_true": "First-person: 'I need [specific observable condition] to stay true...'",
    "what_would_change_my_mind": "First-person: 'I'd sell if [specific event or scenario]...'"
}}

Output ONLY valid JSON, no markdown fences."""

async def generate_initial_draft(ticker: str) -> dict[str, str]:
    from app.services.market_data import _normalize_ticker
    clean_ticker = _normalize_ticker(ticker)

    if not settings.anthropic_api_key:
        return _fallback_initial_draft(clean_ticker)

    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for draft thesis on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)

    prompt = DRAFT_THESIS_PROMPT.format(
        ticker=clean_ticker,
        market_data_section=market_data_section,
    )

    try:
        data = await _call_anthropic_json(
            prompt=prompt,
            model=settings.anthropic_model,
            max_tokens=500,
        )
        return _parse_draft_output(data, clean_ticker)
    except Exception as e:
        logger.error(f"Draft thesis generation failed for {ticker}: {e}")
        return _fallback_initial_draft(clean_ticker, market_data)


# ---------------------------------------------------------------------------
# Wizard synthesis — construct a thesis from two Q&A answers
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """Turn two short answers into a structured reason for holding a stock.

Keep the investor's wording where you can; clean up vagueness, don't corporate-wash it.

Investor profile:
- {investor_profile_label}
- Guidance: {investor_profile_guidance}

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


def _synthesis_profile_context(investor_profile: str | None) -> tuple[str, str]:
    if investor_profile == "hearsay_driven":
        return (
            "Hearsay-driven investor",
            "The investor may be starting from chatter, momentum, or a rough idea. Help them surface the implicit business reason, make it more concrete, and write a sharper break condition than they naturally would.",
        )
    return (
        "Thesis-driven investor",
        "They likely already have a clear view. Keep their structure, tighten specifics, don't pad.",
    )


def _fallback_synthesize(
    ticker: str,
    answer1: str,
    answer2: str,
    investor_profile: str | None = None,
) -> SynthesisOutput:
    why_own_it = answer1.strip() or f"Investing in {ticker} for long-term growth."
    what_would_change_my_mind = answer2.strip() or "A fundamental change in the business model."
    if investor_profile == "hearsay_driven":
        why_own_it = answer1.strip() or f"This started as a rough idea in {ticker}."
    lowered = why_own_it.lower()
    labels = [
        label
        for label, keywords in THEME_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ] or ["user_defined"]
    inferred_must, inferred_change, inferred_ambiguity = _infer_specific_conditions(
        ticker,
        why_text=why_own_it or answer1,
        change_text=what_would_change_my_mind or answer2,
        investor_profile=investor_profile,
    )
    output = SynthesisOutput(
        why_own_it=why_own_it,
        must_remain_true=inferred_must,
        what_would_change_my_mind=what_would_change_my_mind or inferred_change,
        ai_summary=f"{ticker}: {why_own_it[:150]}",
        interpretation={
            "labels": labels[:3],
            "monitorability": "medium",
            "watch_hints": _infer_story_watch_hints(f"{answer1} {answer2}"),
            "proxy_signals": [],
            "ambiguity_note": inferred_ambiguity,
        },
    )
    return _apply_synthesis_guardrails(
        output,
        ticker=ticker,
        answer1=answer1,
        answer2=answer2,
        investor_profile=investor_profile,
    )


def _parse_synthesis_output(
    data: dict[str, Any],
    ticker: str,
    *,
    answer1: str,
    answer2: str,
    investor_profile: str | None,
) -> SynthesisOutput:
    why_own_it = data.get("why_own_it")
    must_remain_true = data.get("must_remain_true")
    what_would_change_my_mind = data.get("what_would_change_my_mind")
    ai_summary = data.get("ai_summary")
    interpretation = data.get("interpretation")
    if not all(isinstance(v, str) for v in (why_own_it, must_remain_true, what_would_change_my_mind, ai_summary)):
        raise ValueError("Invalid synthesis payload")
    output = SynthesisOutput(
        why_own_it=why_own_it.strip() or f"Investing in {ticker} for long-term potential.",
        must_remain_true=must_remain_true.strip() or "",
        what_would_change_my_mind=what_would_change_my_mind.strip() or "",
        ai_summary=ai_summary.strip(),
        interpretation=_normalize_interpretation(interpretation),
    )
    return _apply_synthesis_guardrails(
        output,
        ticker=ticker,
        answer1=answer1,
        answer2=answer2,
        investor_profile=investor_profile,
    )


async def synthesize_thesis_from_qa(
    ticker: str,
    name: str,
    question1: str,
    answer1: str,
    question2: str,
    answer2: str,
    investor_profile: str | None = None,
) -> SynthesisOutput:
    if not settings.anthropic_api_key:
        return _fallback_synthesize(
            ticker=ticker,
            answer1=answer1,
            answer2=answer2,
            investor_profile=investor_profile,
        )

    try:
        market_data = await fetch_company_data(ticker)
    except Exception as e:
        logger.warning("Market data unavailable for synthesis on %s: %s", ticker, e)
        market_data = None
    market_data_section = _build_market_data_section(market_data)
    investor_profile_label, investor_profile_guidance = _synthesis_profile_context(investor_profile)

    prompt = SYNTHESIS_PROMPT.format(
        ticker=ticker,
        name=name,
        investor_profile_label=investor_profile_label,
        investor_profile_guidance=investor_profile_guidance,
        question1=question1,
        answer1=answer1 or "Not provided",
        question2=question2,
        answer2=answer2 or "Not provided",
        market_data_section=market_data_section,
    )

    try:
        data = await _call_anthropic_json(
            prompt=prompt,
            model=settings.anthropic_model,
            max_tokens=1024,
        )
        return _parse_synthesis_output(
            data,
            ticker,
            answer1=answer1,
            answer2=answer2,
            investor_profile=investor_profile,
        )
    except Exception as e:
        logger.error("Synthesis failed for %s: %s", ticker, e)
        return _fallback_synthesize(
            ticker=ticker,
            answer1=answer1,
            answer2=answer2,
            investor_profile=investor_profile,
        )


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

    try:
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

            draft_records: list[tuple[Holding, OnboardingDraft]] = []
            for holding in holdings:
                draft = OnboardingDraft(user_id=user_id, holding_id=holding.id, status="pending")
                db.add(draft)
                await db.flush()
                draft_records.append((holding, draft))

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
    except Exception:
        logger.exception("Background draft generation crashed for user %s", user_id)
