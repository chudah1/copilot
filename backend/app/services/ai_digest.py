import logging
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

DIGEST_PROMPT = """You are writing a weekly investment digest for a retail investor. Write like a sharp analyst memo — direct, no fluff, no greetings.

Portfolio holdings and their theses:
{holdings_section}

Events this week:
{events_section}

Stable holdings this week:
{stable_section}

Portfolio-level observations:
{observations_section}

Write the digest as HTML email content. Use <h3> for holding names, <p> for text, <span style="color: red"> for thesis-breaking, <span style="color: orange"> for warnings.
Output only the HTML body content, no <html> or <body> tags."""


def _fallback_digest(holdings_with_theses: list[dict], events: list[dict], observations: dict) -> str:
    parts = ["<h2>Weekly Thesis Review</h2>"]

    if events:
        for event in events:
            parts.append(f"<h3>{event['ticker']}</h3>")
            parts.append(f"<p><strong>{event['title']}</strong>: {event['summary']}</p>")
            if event.get("ai_analysis"):
                parts.append(f"<p>{event['ai_analysis']}</p>")
    else:
        parts.append("<p>No material thesis events this week.</p>")

    stable_holdings = observations.get("stable_holdings", [])
    if stable_holdings:
        parts.append("<h3>Stable Holdings</h3>")
        for stable in stable_holdings:
            if stable.get("stale"):
                parts.append(
                    f"<p>{stable['ticker']}: No material thesis changes this week, but this thesis is stale and deserves a review.</p>"
                )
            else:
                parts.append(f"<p>{stable['ticker']}: No material changes against your thesis this week.</p>")

    for holding in holdings_with_theses:
        parts.append(f"<h3>{holding['ticker']} ({holding['name']})</h3>")
        parts.append(f"<p>Why you own it: {holding.get('why_own_it', 'No thesis recorded.')}</p>")
        if holding.get("must_remain_true"):
            parts.append(f"<p>Must remain true: {holding['must_remain_true']}</p>")
        if holding.get("what_would_change_my_mind"):
            parts.append(f"<p>Change-my-mind trigger: {holding['what_would_change_my_mind']}</p>")

    if observations.get("stale_theses"):
        parts.append(f"<p>Stale theses (>90 days): {', '.join(observations['stale_theses'])}</p>")
    if observations.get("missing_theses"):
        parts.append(f"<p>Positions without an active thesis: {', '.join(observations['missing_theses'])}</p>")
    if observations.get("concentration_warnings"):
        parts.append(f"<p>Concentration warning: {observations['concentration_warnings']}</p>")

    return "".join(parts)


async def generate_digest_content(holdings_with_theses: list[dict], events: list[dict], observations: dict) -> str | None:
    holdings_section = ""
    for h in holdings_with_theses:
        holdings_section += (
            f"\n- {h['ticker']} ({h['name']}): Why own it: {h.get('why_own_it', 'No thesis')}; "
            f"Must remain true: {h.get('must_remain_true', 'Not specified')}; "
            f"What would change my mind: {h.get('what_would_change_my_mind', 'Not specified')}; "
            f"AI summary: {h.get('ai_summary', 'None')}"
        )

    events_section = ""
    if events:
        for e in events:
            events_section += f"\n- [{e['severity'].upper()}] {e['ticker']}: {e['title']} — {e['summary']} — {e.get('ai_analysis', '')}"
    else:
        events_section = "No events this week."

    stable_section = ""
    stable_holdings = observations.get("stable_holdings", [])
    if stable_holdings:
        for stable in stable_holdings:
            if stable.get("stale"):
                stable_section += (
                    f"\n- {stable['ticker']} ({stable['name']}): No material changes this week, "
                    "but the thesis is stale and should be reviewed."
                )
            else:
                stable_section += f"\n- {stable['ticker']} ({stable['name']}): No material changes against the thesis this week."
    else:
        stable_section = "None."

    obs_parts = []
    if observations.get("concentration_warnings"):
        obs_parts.append(f"Concentration: {observations['concentration_warnings']}")
    if observations.get("stale_theses"):
        obs_parts.append(f"Stale theses (>90 days): {', '.join(observations['stale_theses'])}")
    if observations.get("missing_theses"):
        obs_parts.append(f"Positions without theses: {', '.join(observations['missing_theses'])}")
    observations_section = "\n".join(obs_parts) if obs_parts else "None."

    prompt = DIGEST_PROMPT.format(
        holdings_section=holdings_section,
        events_section=events_section,
        stable_section=stable_section,
        observations_section=observations_section,
    )

    try:
        if not settings.anthropic_api_key:
            return _fallback_digest(holdings_with_theses, events, observations)
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(model="claude-sonnet-4-20250514", max_tokens=2048, messages=[{"role": "user", "content": prompt}])
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        return _fallback_digest(holdings_with_theses, events, observations)
