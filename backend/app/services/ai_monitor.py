import json
import logging
from dataclasses import dataclass
import anthropic
from app.config import settings

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


async def classify_event(
    why_own_it: str,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
    ai_summary: str | None,
    event_description: str,
) -> ClassificationResult | None:
    prompt = CLASSIFY_PROMPT.format(
        why_own_it=why_own_it,
        must_remain_true=must_remain_true or "Not specified",
        what_would_change_my_mind=what_would_change_my_mind or "Not specified",
        ai_summary=ai_summary or "Not available",
        event_description=event_description,
    )
    try:
        if not settings.anthropic_api_key:
            return ClassificationResult(
                severity="warning",
                analysis="Something changed that appears relevant to the user's thesis. Review the position to confirm whether the original reason still holds.",
            )
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=512, messages=[{"role": "user", "content": prompt}])
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        return ClassificationResult(severity=data["severity"], analysis=data["analysis"])
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        return None
