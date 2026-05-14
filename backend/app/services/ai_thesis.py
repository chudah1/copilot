import json
import logging
from dataclasses import dataclass, field
import re

import anthropic

from app.config import settings
from app.services.market_data import fetch_company_data

logger = logging.getLogger(__name__)


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
    return ThesisAssistOutput(
        ai_summary=data["ai_summary"],
        interpretation=data["interpretation"],
    )


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
    if market_data:
        market_data_section = (
            f"Market Data:\n"
            f"- Sector: {market_data.sector}\n"
            f"- Industry: {market_data.industry}\n"
            f"- Revenue Growth: {market_data.revenue_growth_yoy}%\n"
            f"- Earnings Growth: {market_data.earnings_growth_yoy}%"
        )
    else:
        market_data_section = "Market Data: Not available. Use your knowledge of this company."

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
        if not result.ai_summary or not isinstance(result.interpretation, dict):
            raise ValueError("Incomplete thesis output")
        result.interpretation = _normalize_interpretation(result.interpretation)
        return result
    except Exception as e:
        logger.error(f"Thesis generation failed for {ticker}: {e}")
        try:
            result = await _call_claude(prompt + "\n\nIMPORTANT: Output ONLY valid JSON.")
            result.interpretation = _normalize_interpretation(result.interpretation)
            return result
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
        return CounterThesisOutput(
            bear_case=data["bear_case"],
            key_risks=data["key_risks"][:5],
            blind_spots=data["blind_spots"][:3],
            suggested_additions=data["suggested_additions"][:3],
        )
    except Exception as e:
        logger.error(f"Counter-thesis generation failed for {ticker}: {e}")
        return _fallback_counter_thesis(
            why_own_it=why_own_it,
            must_remain_true=must_remain_true,
            what_would_change_my_mind=what_would_change_my_mind,
            ai_summary=ai_summary,
            ticker=ticker,
        )
