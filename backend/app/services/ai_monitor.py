import json
import logging
from dataclasses import dataclass
import re
import anthropic
from app.config import settings
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    severity: str  # info | warning | thesis_breaking
    analysis: str
    # supports | threatens | neutral | "" — separate from severity so a
    # low-severity event that clearly *validates* the thesis (e.g. an earnings
    # call quote confirming a stated pillar) surfaces on the "Held up this
    # week" positive channel instead of vanishing as an info/neutral FYI.
    direction: str = ""


def _provider_failure_kind(exc: Exception) -> str:
    message = str(exc).lower()
    if "credit balance is too low" in message or "insufficient_quota" in message or "quota" in message:
        return "credits_exhausted"
    if "api key not configured" in message or "not configured" in message:
        return "not_configured"
    if "timeout" in message:
        return "timeout"
    if "connection" in message:
        return "connection_error"
    return type(exc).__name__


_CLASSIFY_SYSTEM = """You classify new data against an investor's written reason for holding a stock.

Classify as: "skip" | "info" | "warning" | "thesis_breaking"

First triage — when to skip:
- If the article is primarily about the holding company itself, never skip — classify per the severity rules below.
- If the article is primarily about ANOTHER company (a competitor, supplier, customer, ETF, or index peer), apply one test: does the event bear on any condition stated in the thesis? Stated conditions include categorical ones — "a competitor deploys X at scale" covers any credible competitor doing or moving toward X, and a company explicitly named in the thesis always counts. If the event bears on a stated condition, do NOT skip: it is at least "info". If it does not, skip. The holding merely being name-dropped never counts as bearing on the thesis: appearing in a supplier's announcement as a listed customer or demand driver, being mentioned as market context in another company's earnings story, or being held by an ETF is a passing mention, not thesis evidence.
- Do not skip price moves, earnings results, or events that test a quantitative threshold for the holding itself.

Default to "info" when the event is genuine news about the holding company but doesn't directly test any stated pillar — geographic expansion into a market the thesis doesn't mention, a peripheral product line, brand or milestone announcements, general corporate updates. These are info, not skip: the investor still owns the stock and wants the noise filtered, not erased.

Severity rules for non-skip events (apply strictly):
- "thesis_breaking": ONLY when an explicit stated condition is clearly met. Two distinct cases:
  (1) Quantitative threshold definitively breached: the stated floor or ceiling is missed by more than ~5 percentage points. A miss of 5pp or less from a stated threshold is "warning", not "thesis_breaking" — and this holds even when it is the first breach in years and even when the threshold sits in must_remain_true. A single-period slip of a point or two past a stated floor is "warning" until the breach is decisive (>5pp) or sustained.
  (2) Qualitative event explicitly stated: a "must remain true" or "what would change my mind" condition names a specific discrete event and that event has clearly occurred — even if the full financial impact is not yet reported. A qualitative condition being met overrides the quantitative near-miss rule.
  Positive or thesis-confirming events are never "thesis_breaking" in this generic classifier. If the news supports the thesis, confirms demand, validates management commentary, or shows a metric above a stated floor, use direction="supports" and severity="info" or "warning" instead.
  Discrete events vs competitive dynamics: discrete events are single, datable occurrences (a government ban, a court ruling, a dividend cut, a product withdrawal, a confirmed shift in business practice reported in results) — these require only one clear occurrence. Competitive dynamics are ongoing situations that are matters of degree (a competitor gaining share, a market shifting) — use "warning" unless specific measurable evidence shows the threshold has definitively been crossed.
  Multi-period conditions: when "what would change my mind" specifies an explicit time requirement (e.g. "for two consecutive quarters"), a single period of violation is "warning" — classify "thesis_breaking" only when the full multi-period threshold is completed.
  Multiple conditions: each condition in "what would change my mind" is independent — any single one clearly met is sufficient for "thesis_breaking".
- "warning": when a thesis pillar is weakening, a quantitative threshold is missed by 5pp or less, or a stated qualitative scenario is beginning to materialize. Also use for: management signals that weaken a thesis pillar — significant insider sales (CEO or founders disposing of meaningfully-sized stakes, even under pre-planned 10b5-1 schedules), executive departures, negative guidance — or trends consistently moving against a stated pillar. A large price decline explicitly attributed to market doubts about a stated pillar is also "warning" — the investor should look — but its direction still follows the fundamentals the article reports.
  Competitor activity bar: a competitor's product launch, revenue beat, or capacity expansion is warning ONLY when (a) that competitor is explicitly named in what_would_change_my_mind, AND (b) the event shows a material share or threshold-level shift — not just routine quarterly results, fundraising, or hiring. Without both, classify as info. "AMD reports record revenue" alone is info; "AMD wins a specific hyperscaler from NVIDIA" or "AMD share moves from 5% to 15%" is warning.
- "info": when the event does not directly touch any specific stated condition. Macro moves, index-level rallies, unrelated product launches, general market surveys, a competitor's fundraising or hiring, and same-company news outside the thesis pillars are almost always "info". Classify as "warning" only when the event reports direct evidence that a stated condition is currently changing, not because it might eventually lead to one. Distinguish speculation from process: analyst forecasts, think-pieces, and hypothetical scenarios about a stated condition are "info", but a formal process that has actually begun and carries quantified impact on a stated condition — a regulator's published proposal, a filed lawsuit, an opened investigation — counts as that scenario beginning to materialize and is "warning" even if the final effect is years away.
- Sector-aware macro rule: some macro events are "info" for most stocks but "warning" for specific sectors. When the holding sector is provided and the event directly affects that sector's economics, use "warning" even if the thesis doesn't explicitly name the macro risk. Examples: geopolitical conflict or oil supply disruption → Energy; central bank rate decision → Financials or REITs; trade tariffs on specific goods → the sector that makes or imports those goods; currency moves → companies with heavy international revenue; defence spending news → Industrials/Aerospace & Defence.

Also decide direction — whether this event validates or threatens the thesis, independent of severity:
- "supports": the event provides evidence FOR a stated pillar. Management commentary confirming a growth driver, a metric printing above a stated floor, a competitor failing where the thesis assumed they would. Use even at info severity if the direction is unambiguous — "Held up this week" needs positive signal.
- "threatens": the event provides evidence AGAINST a stated pillar. Guidance cut, a signal weakening, a competitor gaining where the thesis assumed they wouldn't.
- "neutral": genuinely no directional signal for the thesis (skip candidates fall here by default).

Judge direction from the article's substance about the stated pillars, never from headline tone or the stock's price reaction:
- A price move alone is not evidence for or against a fundamental pillar. "Shares fell on X concerns" reports what the market fears, not what the business did.
- Mixed articles are common: a dramatic negative headline or sell-off wrapped around fundamentals that affirm the pillar ("shares drop 30%, but subscription growth remains solid"). That is direction="supports" — the reported fundamentals back the stated reason — even when the sell-off itself justifies severity="warning".
- The reverse holds too: a celebratory headline or rally wrapped around evidence that a stated condition is deteriorating is direction="threatens".
- If the article reports only a price move with no fundamental evidence either way, direction="neutral".

A single event can be severity="info" AND direction="supports" — that combination is the whole point of separating them. So is severity="warning" AND direction="supports": a large sell-off attributed to doubts about a stated pillar deserves the investor's attention (warning), while the fundamentals the article actually reports still back the reason (supports).

Output valid JSON:
{"severity": "skip|info|warning|thesis_breaking", "direction": "supports|threatens|neutral", "analysis": "Exactly 2 short sentences, or empty string if skip."}

Requirements for analysis:
- Lead with the conclusion. Sentence 1 must name the company, metric, customer group, competitor, or regulator and state plainly what is holding up, weakening, or has happened.
- Sentence 2 must give the strongest concrete fact or number behind that conclusion.
- Do not write the action. The app adds "No action needed", "Review this position", or "A decision is needed now".
- Do not write "This evidence", "This news", "This event", "supports the thesis", "supports the case", "supports the story", "threatens your reason", "hits a pillar", or "tests an assumption". Name the exact business condition instead.
- Do not write "suggests" when you can state the result directly. When the source is uncertain or forward-looking, name it: "Analysts forecast..." or "Management has not yet reported...".
- Use familiar words, active voice, and no labels such as "What changed:".
- Avoid em dashes. Use commas or periods instead.

Bad: "This evidence suggests the demand story remains intact."
Good: "ServiceNow's customer demand is holding up."
Bad: "That range, if it prints, would support the thesis."
Good: "Analysts forecast 21% to 21.5% subscription growth. ServiceNow has not reported the quarter yet."

Do not use filler ("worth noting", "decision pressure", "it's important to", "landscape", "robust"). Write like a sharp friend who owns stocks, not a chatbot.

Output ONLY valid JSON."""

_CLASSIFY_USER_TEMPLATE = """Holding: {ticker} ({company_name})

Thesis:
- Why own it: {why_own_it}
- What must remain true: {must_remain_true}
- What would change the user's mind: {what_would_change_my_mind}
- AI summary: {ai_summary}
- Investor profile: {investor_profile_label}
- Decision framing: {investor_profile_guidance}
- Holding sector: {sector}

New data point:
{event_description}"""


def _classification_profile_context(investor_profile: str | None) -> tuple[str, str]:
    if investor_profile == "thesis_driven":
        return (
            "thesis_driven",
            "Name the exact condition that changed and state the change plainly.",
        )
    if investor_profile == "hearsay_driven":
        return (
            "hearsay_driven",
            "The user may have started from a tip or theme. Name the business fact that now makes the position stronger or weaker.",
        )
    return (
        "general",
        "Be direct. Tie the news to why they said they own the position.",
    )


def _next_step_sentence(severity: str, investor_profile: str | None) -> str:
    if severity == "thesis_breaking":
        return "A decision is needed now."
    if severity == "warning":
        return "Review this position."
    return "No action needed."


_ACTION_LANGUAGE = re.compile(
    r"\b(?:"
    r"no action|no rush|keep watching|review (?:soon|this|the)|"
    r"a decision is needed|rewrite (?:the|your)|leave it on watch|"
    r"thesis may be broken|may need to exit"
    r")\b",
    re.IGNORECASE,
)

_INDIRECT_LANGUAGE = re.compile(
    r"(?:"
    r"^\s*(?:this evidence|this news|this event|this development|that range)\b|"
    r"\b(?:supports?|threatens?|weakens?|validates?|confirms?|tests?|hits?)\s+"
    r"(?:your\s+|the\s+|a\s+|an\s+)?"
    r"(?:reason|thesis|case|story|pillar|assumption)\b|"
    r"\b(?:reason|thesis|case|story|pillar|assumption)\s+"
    r"(?:remains?|stays?|is|looks?|appears?)\b"
    r")",
    re.IGNORECASE,
)

_COPY_LABEL = re.compile(
    r"^\s*(?:what happened|why it matters(?: now)?|next step|model read)\s*:\s*",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", text.strip())
        if segment.strip()
    ]


def _finish_sentence(sentence: str) -> str:
    cleaned = _COPY_LABEL.sub("", sentence.strip())
    if not cleaned:
        return ""
    cleaned = f"{cleaned[0].upper()}{cleaned[1:]}"
    if not cleaned.endswith((".", "!", "?")):
        cleaned = f"{cleaned}."
    return cleaned


def _direct_analysis_sentences(analysis: str) -> list[str]:
    direct: list[str] = []
    for sentence in _sentences(analysis):
        cleaned = _finish_sentence(sentence)
        if not cleaned:
            continue
        if _ACTION_LANGUAGE.search(cleaned) or _INDIRECT_LANGUAGE.search(cleaned):
            continue
        if cleaned.casefold() not in {existing.casefold() for existing in direct}:
            direct.append(cleaned)
        if len(direct) == 2:
            break
    return direct


def _normalize_analysis_text(
    *,
    event_description: str,
    analysis: str,
    severity: str,
    investor_profile: str | None,
) -> str:
    content = _direct_analysis_sentences(analysis)
    if not content:
        content = [
            finished
            for sentence in _sentences(event_description)
            if (finished := _finish_sentence(sentence))
        ][:2]
    if not content:
        content = ["New evidence was found."]

    action = _next_step_sentence(severity, investor_profile)
    return " ".join([*content, action]).strip()


def _build_classification_prompt(
    *,
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    event_description: str,
    investor_profile: str | None = None,
    sector: str | None = None,
    ticker: str | None = None,
    company_name: str | None = None,
) -> str:
    investor_profile_label, investor_profile_guidance = _classification_profile_context(investor_profile)
    return _CLASSIFY_USER_TEMPLATE.format(
        ticker=ticker or "Unknown",
        company_name=company_name or ticker or "Unknown",
        why_own_it=why_own_it,
        must_remain_true=must_remain_true or "Not specified",
        what_would_change_my_mind=what_would_change_my_mind or "Not specified",
        ai_summary=ai_summary or "Not available",
        event_description=event_description,
        investor_profile_label=investor_profile_label,
        investor_profile_guidance=investor_profile_guidance,
        sector=sector or "Not specified",
    )


def _parse_classification_response(text: str) -> ClassificationResult:
    data = json.loads(strip_code_fences(text))
    severity = data.get("severity")
    analysis = data.get("analysis")
    if severity not in {"skip", "info", "warning", "thesis_breaking"} or not isinstance(analysis, str):
        raise ValueError("Invalid classification payload")
    direction_raw = data.get("direction")
    direction = direction_raw if direction_raw in {"supports", "threatens", "neutral"} else ""
    return ClassificationResult(severity=severity, analysis=analysis, direction=direction)


def _normalize_classification_result(result: ClassificationResult) -> ClassificationResult:
    # "thesis_breaking" is reserved for thesis damage. If the model says the
    # event clearly supports the thesis, keep the positive direction but cap the
    # urgency to warning so supportive operating news does not look like a red alert.
    if result.direction == "supports" and result.severity == "thesis_breaking":
        return ClassificationResult(
            severity="warning",
            analysis=result.analysis,
            direction=result.direction,
        )
    return result


async def classify_event(
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    event_description: str,
    investor_profile: str | None = None,
    sector: str | None = None,
    ticker: str | None = None,
    company_name: str | None = None,
) -> ClassificationResult | None:
    prompt = _build_classification_prompt(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true,
        what_would_change_my_mind=what_would_change_my_mind,
        ai_summary=ai_summary,
        event_description=event_description,
        investor_profile=investor_profile,
        sector=sector,
        ticker=ticker,
        company_name=company_name,
    )
    anthropic_failed = False
    if settings.anthropic_api_key:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_CLASSIFY_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0,
                # Classification is a judgment with a right answer; default
                # temperature made the same event flip severity/direction
                # between runs (observed 4/5 vs 1/5 splits on a real case).
                temperature=0.0,
            )
            text = response.content[0].text.strip()
            parsed = _normalize_classification_result(_parse_classification_response(text))
            if parsed.severity == "skip":
                return None
            return ClassificationResult(
                severity=parsed.severity,
                analysis=_normalize_analysis_text(
                    event_description=event_description,
                    analysis=parsed.analysis,
                    severity=parsed.severity,
                    investor_profile=investor_profile,
                ),
                direction=parsed.direction,
            )
        except Exception as e:
            anthropic_failed = True
            logger.warning(
                "[MONITOR-DIAG] classification provider failed provider=anthropic kind=%s ticker=%s company=%s detail=%s",
                _provider_failure_kind(e),
                ticker or "",
                company_name or "",
                e,
            )

    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            oa_client = AsyncOpenAI(api_key=settings.openai_api_key)
            # Side-by-side test on the NVDA "+5.6% surprise" walkthrough case
            # showed gpt-4o-mini classifies the beat as a warning regardless of
            # how unambiguous the description is (tried three description
            # variants — all wrong on mini, all correct on gpt-4o). gpt-4o is
            # the cheapest model that handles event-against-thesis judgments
            # reliably.
            oa_response = await oa_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                timeout=30.0,
                temperature=0.0,
            )
            text = (oa_response.choices[0].message.content or "").strip()
            parsed = _normalize_classification_result(_parse_classification_response(text))
            if parsed.severity == "skip":
                return None
            if anthropic_failed:
                logger.info(
                    "[MONITOR-DIAG] classification provider fallback_succeeded provider=openai ticker=%s company=%s severity=%s direction=%s",
                    ticker or "",
                    company_name or "",
                    parsed.severity,
                    parsed.direction or "neutral",
                )
            return ClassificationResult(
                severity=parsed.severity,
                analysis=_normalize_analysis_text(
                    event_description=event_description,
                    analysis=parsed.analysis,
                    severity=parsed.severity,
                    investor_profile=investor_profile,
                ),
                direction=parsed.direction,
            )
        except Exception as e:
            logger.error(
                "[MONITOR-DIAG] classification provider failed provider=openai kind=%s ticker=%s company=%s detail=%s",
                _provider_failure_kind(e),
                ticker or "",
                company_name or "",
                e,
            )

    # Qualitative evidence needs an actual thesis judgment. Manufacturing a
    # warning when every classifier is unavailable turns an outage into noise.
    # The monitoring pipeline separately preserves objective threshold breaches
    # and signal-bound transcript evidence, so returning None here stays quiet
    # without hiding deterministic changes.
    logger.warning(
        "[MONITOR-DIAG] classification unavailable returning_none ticker=%s company=%s anthropic_enabled=%s openai_enabled=%s",
        ticker or "",
        company_name or "",
        bool(settings.anthropic_api_key),
        bool(settings.openai_api_key),
    )
    return None
