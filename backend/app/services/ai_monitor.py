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
- Bull case: {bull_case}
- Key metrics: {key_metrics}
- Risk factors: {risk_factors}

New data point:
{event_description}

Classify as: "info" | "warning" | "thesis_breaking"

Output valid JSON:
{{"severity": "info|warning|thesis_breaking", "analysis": "2-3 sentences."}}

Output ONLY valid JSON."""


async def classify_event(bull_case: str, key_metrics: list[dict], risk_factors: str, event_description: str) -> ClassificationResult | None:
    prompt = CLASSIFY_PROMPT.format(bull_case=bull_case, key_metrics=json.dumps(key_metrics), risk_factors=risk_factors, event_description=event_description)
    try:
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
