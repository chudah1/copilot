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


_CLASSIFY_SYSTEM = """You classify new data against an investor's written reason for holding a stock.

Classify as: "skip" | "info" | "warning" | "thesis_breaking"

First ask: is this event primarily about the holding itself (the ticker and company named in the prompt)? If the article is primarily about a different company — an ETF that references the ticker in its name, a customer, a competitor, or a third party — return "skip" even if the ticker appears in the text. Then ask: does this event touch any specific pillar, assumption, or stated concern in the thesis? If the answer is no — the news is about the company but has zero connection to why the investor owns it (e.g. geographic expansion into a market unrelated to the thesis, a product line the thesis never mentions, general corporate announcements with no bearing on stated assumptions) — return "skip". Do not return "skip" for price moves, earnings results, or any event that tests a quantitative threshold.

Severity rules for non-skip events (apply strictly):
- "thesis_breaking": ONLY when an explicit stated condition is clearly met. Two distinct cases:
  (1) Quantitative threshold definitively breached: the stated floor or ceiling is missed by more than ~5 percentage points. A miss of 5pp or less from a stated threshold is "warning", not "thesis_breaking".
  (2) Qualitative event explicitly stated: a "must remain true" or "what would change my mind" condition names a specific discrete event and that event has clearly occurred — even if the full financial impact is not yet reported. A qualitative condition being met overrides the quantitative near-miss rule.
  Discrete events vs competitive dynamics: discrete events are single, datable occurrences (a government ban, a court ruling, a dividend cut, a product withdrawal, a confirmed shift in business practice reported in results) — these require only one clear occurrence. Competitive dynamics are ongoing situations that are matters of degree (a competitor gaining share, a market shifting) — use "warning" unless specific measurable evidence shows the threshold has definitively been crossed.
  Multi-period conditions: when "what would change my mind" specifies an explicit time requirement (e.g. "for two consecutive quarters"), a single period of violation is "warning" — classify "thesis_breaking" only when the full multi-period threshold is completed.
  Multiple conditions: each condition in "what would change my mind" is independent — any single one clearly met is sufficient for "thesis_breaking".
- "warning": when a thesis pillar is weakening, a quantitative threshold is missed by 5pp or less, or a stated qualitative scenario is beginning to materialize. Also use for: direct competitor product launches or market share gains, management signals that weaken a thesis pillar (significant insider sales, executive departures, negative guidance), or trends consistently moving against a stated pillar.
- "info": when the event does not directly touch any specific stated condition. Macro moves, index-level rallies, unrelated product launches, general market surveys, and a competitor's fundraising or hiring are almost always "info". Classify as "warning" only when the event reports direct evidence that a stated condition is currently changing, not because it might eventually lead to one.
- Sector-aware macro rule: some macro events are "info" for most stocks but "warning" for specific sectors. When the holding sector is provided and the event directly affects that sector's economics, use "warning" even if the thesis doesn't explicitly name the macro risk. Examples: geopolitical conflict or oil supply disruption → Energy; central bank rate decision → Financials or REITs; trade tariffs on specific goods → the sector that makes or imports those goods; currency moves → companies with heavy international revenue; defence spending news → Industrials/Aerospace & Defence.

Output valid JSON:
{"severity": "skip|info|warning|thesis_breaking", "analysis": "2-3 sentences, or empty string if skip."}

Requirements for analysis (exactly 3 short sentences, plain English, no labels like "What changed:"):
- Sentence 1: what happened
- Sentence 2: why it matters to their stated reason or assumption
- Sentence 3: what to do next (keep watching / review soon / thesis may be broken)

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
            "The user writes in assumptions. Say whether the news weakens, supports, or breaks one of them — plainly.",
        )
    if investor_profile == "hearsay_driven":
        return (
            "hearsay_driven",
            "The user may have started from a tip or theme. Say whether the news makes that story more real, shakier, or dead.",
        )
    return (
        "general",
        "Be direct. Tie the news to why they said they own the position.",
    )


def _default_classification(investor_profile: str | None) -> ClassificationResult:
    if investor_profile == "thesis_driven":
        return ClassificationResult(
            severity="warning",
            analysis="This looks relevant to one of your assumptions. It may be weakening a pillar — not just market noise. Re-read that assumption before you add, trim, or shrug it off.",
        )
    if investor_profile == "hearsay_driven":
        return ClassificationResult(
            severity="warning",
            analysis="This touches the story behind the position. The question is whether it's showing up in real results yet, not just hype. Check if the story is getting stronger or starting to crack.",
        )
    return ClassificationResult(
        severity="warning",
        analysis="Something changed that may matter to why you own this. Decide if the original case still holds before you call it noise.",
    )


def _next_step_sentence(severity: str, investor_profile: str | None) -> str:
    if severity == "thesis_breaking":
        return (
            "You may need to rewrite the story or exit — don't just leave it on watch."
            if investor_profile == "hearsay_driven"
            else "You may need to rewrite the thesis or exit — don't just leave it on watch."
        )
    if severity == "warning":
        return (
            "Review soon; the story may be weakening and this isn't background noise."
            if investor_profile == "hearsay_driven"
            else "Review soon; a pillar may be weakening and this isn't background noise."
        )
    return "No rush — keep watching for now."


def _why_it_matters_sentence(analysis: str, investor_profile: str | None) -> str:
    cleaned = analysis.strip()
    if cleaned:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]
        if len(sentences) >= 2:
            return sentences[1]
        if len(sentences) == 1:
            return sentences[0]
    return (
        "The story needs to show up in real operating results, not just headlines."
        if investor_profile == "hearsay_driven"
        else "This hits one of the assumptions you wrote down."
    )


def _normalize_analysis_text(
    *,
    event_description: str,
    analysis: str,
    severity: str,
    investor_profile: str | None,
) -> str:
    first_sentence = event_description.strip().rstrip(".")
    if first_sentence:
        first_sentence = f"{first_sentence[0].upper()}{first_sentence[1:]}."
    else:
        first_sentence = "New evidence showed up."

    second_sentence = _why_it_matters_sentence(analysis, investor_profile).strip()
    if not second_sentence.endswith((".", "!", "?")):
        second_sentence = f"{second_sentence}."

    third_sentence = _next_step_sentence(severity, investor_profile)
    if not third_sentence.endswith((".", "!", "?")):
        third_sentence = f"{third_sentence}."

    return " ".join([first_sentence, second_sentence, third_sentence]).strip()


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
    return ClassificationResult(severity=severity, analysis=analysis)


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
    try:
        if not settings.anthropic_api_key:
            default = _default_classification(investor_profile)
            return ClassificationResult(
                severity=default.severity,
                analysis=_normalize_analysis_text(
                    event_description=event_description,
                    analysis=default.analysis,
                    severity=default.severity,
                    investor_profile=investor_profile,
                ),
            )
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )
        text = response.content[0].text.strip()
        parsed = _parse_classification_response(text)
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
        )
    except Exception as e:
        logger.error("AI classification failed (%s): %s", type(e).__name__, e)
        return None
