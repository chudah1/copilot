import json
import logging
from dataclasses import dataclass
import anthropic
from app.config import settings
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    severity: str  # info | warning | thesis_breaking
    analysis: str


CLASSIFY_PROMPT = """You are an investment monitoring assistant. Given a thesis and new data, classify impact.

Thesis:
- Why own it: {why_own_it}
- What must remain true: {must_remain_true}
- What would change the user's mind: {what_would_change_my_mind}
- AI summary: {ai_summary}

New data point:
{event_description}

Classify as: "info" | "warning" | "thesis_breaking"

Output valid JSON:
{{"severity": "info|warning|thesis_breaking", "analysis": "2-3 sentences."}}

Output ONLY valid JSON."""

DEFAULT_CLASSIFICATION = ClassificationResult(
    severity="warning",
    analysis="Something changed that appears relevant to the user's thesis. Review the position to confirm whether the original reason still holds.",
)


def _build_classification_prompt(
    *,
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    event_description: str,
) -> str:
    return CLASSIFY_PROMPT.format(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true or "Not specified",
        what_would_change_my_mind=what_would_change_my_mind or "Not specified",
        ai_summary=ai_summary or "Not available",
        event_description=event_description,
    )


def _parse_classification_response(text: str) -> ClassificationResult:
    data = json.loads(strip_code_fences(text))
    severity = data.get("severity")
    analysis = data.get("analysis")
    if severity not in {"info", "warning", "thesis_breaking"} or not isinstance(analysis, str):
        raise ValueError("Invalid classification payload")
    return ClassificationResult(severity=severity, analysis=analysis)


async def classify_event(
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    event_description: str,
) -> ClassificationResult | None:
    prompt = _build_classification_prompt(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true,
        what_would_change_my_mind=what_would_change_my_mind,
        ai_summary=ai_summary,
        event_description=event_description,
    )
    try:
        if not settings.anthropic_api_key:
            return DEFAULT_CLASSIFICATION
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )
        text = response.content[0].text.strip()
        return _parse_classification_response(text)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        return None
