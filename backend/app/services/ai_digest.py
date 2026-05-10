import logging
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

DIGEST_PROMPT = """You are writing a weekly investment digest for a retail investor. Write like a sharp analyst memo — direct, no fluff, no greetings.

Portfolio holdings and their theses:
{holdings_section}

Events this week:
{events_section}

Portfolio-level observations:
{observations_section}

Write the digest as HTML email content. Use <h3> for holding names, <p> for text, <span style="color: red"> for thesis-breaking, <span style="color: orange"> for warnings.
Output only the HTML body content, no <html> or <body> tags."""


async def generate_digest_content(holdings_with_theses: list[dict], events: list[dict], observations: dict) -> str | None:
    holdings_section = ""
    for h in holdings_with_theses:
        holdings_section += f"\n- {h['ticker']} ({h['name']}): Thesis: {h.get('bull_case', 'No thesis')}"

    events_section = ""
    if events:
        for e in events:
            events_section += f"\n- [{e['severity'].upper()}] {e['ticker']}: {e['title']} — {e['summary']}"
    else:
        events_section = "No events this week."

    obs_parts = []
    if observations.get("concentration_warnings"):
        obs_parts.append(f"Concentration: {observations['concentration_warnings']}")
    if observations.get("stale_theses"):
        obs_parts.append(f"Stale theses (>90 days): {', '.join(observations['stale_theses'])}")
    if observations.get("missing_theses"):
        obs_parts.append(f"Positions without theses: {', '.join(observations['missing_theses'])}")
    observations_section = "\n".join(obs_parts) if obs_parts else "None."

    prompt = DIGEST_PROMPT.format(holdings_section=holdings_section, events_section=events_section, observations_section=observations_section)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(model="claude-sonnet-4-20250514", max_tokens=2048, messages=[{"role": "user", "content": prompt}])
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        return None
