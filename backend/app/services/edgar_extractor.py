"""8-K enrichment for monitoring candidates.

For earnings 8-Ks (item 2.02), fetch the EX-99.1 press release exhibit and use
Claude Haiku to extract key metrics and thesis impact.

For other material 8-Ks, fetch the filing body itself and extract concise
item-level summaries from the relevant sections so the monitoring pipeline sees
actual filing facts rather than only the generic item label.

Falls back gracefully — any failure returns the original candidate unchanged so
the pipeline continues with the basic "8-K filed" event.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.models.thesis import Thesis

logger = logging.getLogger(__name__)

_CONTENT_LIMIT = 6000  # chars of press release text passed to Claude

_SECTION_RE = re.compile(
    r"(?i)\b(results\s+of\s+operations|financial\s+highlights?|revenue\s+highlights?|"
    r"operating\s+results|business\s+highlights?|quarterly\s+highlights?|"
    r"outlook|guidance|full[\s\-]year|fourth\s+quarter|third\s+quarter|"
    r"second\s+quarter|first\s+quarter|q[1-4]\s+20\d{2})\b"
)

_ITEM_HEADING_RE = re.compile(r"(?i)\bitem\s+(\d\.\d{2})\b")
_ITEM_SUMMARY_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _extract_relevant_sections(text: str) -> str:
    """Return the most relevant slice of a press release for LLM analysis.

    Tries to start from the first results/guidance heading rather than from
    char 0 (which is typically boilerplate and safe-harbor text).
    Falls back to the first financial figure occurrence, then raw truncation.
    """
    match = _SECTION_RE.search(text)
    if match:
        return text[match.start(): match.start() + _CONTENT_LIMIT]

    dollar = re.search(r"\$[\d,]+", text)
    if dollar:
        start = max(0, dollar.start() - 200)
        return text[start: start + _CONTENT_LIMIT]

    return text[:_CONTENT_LIMIT]

_EXTRACTION_PROMPT = """\
Extract key financial metrics from this earnings press release and assess whether \
the results confirm or threaten the investment thesis.

Investment thesis:
- Why owned: {why_own_it}
- Must remain true: {must_remain_true}
- What would change mind: {what_would_change_my_mind}

Press release (results/guidance section, up to {limit} chars):
{content}

Return ONLY valid JSON — no markdown, no prose:
{{
  "headline_metric": "single most important number, e.g. 'Revenue $44.1B +69% YoY'",
  "revenue": "total revenue and YoY growth",
  "gross_margin": "gross margin percentage",
  "segment_revenue": "key segment revenue if mentioned (e.g. Data Center $X)",
  "guidance": "next quarter revenue / margin guidance",
  "thesis_verdict": "confirms" or "threatens" or "neutral",
  "verdict_rationale": "1-2 sentences connecting these numbers to the thesis conditions above",
  "key_quote": "most relevant verbatim quote from the press release (max 160 chars)"
}}
"""


def _cik_from_url(url: str) -> str | None:
    match = re.search(r"/edgar/data/(\d+)/", url)
    return match.group(1) if match else None


async def _find_exhibit_url(cik: str, accession: str) -> str | None:
    """Find the EX-99.1 press release URL from the EDGAR filing index page."""
    accession_clean = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}"
        f"/{accession_clean}/{accession}-index.htm"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                index_url,
                headers={"User-Agent": settings.edgar_user_agent},
                timeout=15,
            )
            if resp.status_code != 200:
                return None
            html = resp.text
    except Exception as exc:
        logger.debug("Filing index fetch failed (%s): %s", accession, exc)
        return None

    # Parse table rows to find the EX-99.1 exhibit
    rows = re.findall(r"<tr[^>]*>.*?</tr>", html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        if not re.search(r"EX-99\.?1\b", row, re.IGNORECASE):
            continue
        # Prefer direct archive links, skip iXBRL viewer (/ix?doc=...)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', row, re.IGNORECASE)
        for href in hrefs:
            if "/ix?" in href or href.endswith((".xsd", ".xml", ".jpg", ".png")):
                continue
            if href.startswith("/Archives"):
                return f"https://www.sec.gov{href}"
            if href.startswith("http"):
                return href
            # Relative filename — resolve against filing directory
            if re.match(r"[^/]+\.htm[l]?$", href, re.IGNORECASE):
                return (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}"
                    f"/{accession_clean}/{href}"
                )
    return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    for entity, replacement in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                                  ("&gt;", ">"), ("&#8220;", '"'), ("&#8221;", '"'),
                                  ("&#8212;", "—"), ("&#8213;", "—"), ("&#58;", ":"),
                                  ("&#8226;", "•")]:
        text = text.replace(entity, replacement)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def _fetch_text(url: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"User-Agent": settings.edgar_user_agent},
                timeout=20,
            )
            resp.raise_for_status()
            return _strip_html(resp.text)
    except Exception as exc:
        logger.debug("Exhibit fetch failed (%s): %s", url, exc)
        return None


def _extract_item_sections(text: str) -> dict[str, str]:
    """Extract the longest substantive section for each 8-K item heading.

    SEC filings often repeat item headings in a table of contents before the
    real section. Choosing the longest slice per item is a cheap way to prefer
    the actual body over the TOC stub.
    """
    matches = list(_ITEM_HEADING_RE.finditer(text))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        item = match.group(1)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = re.sub(r"\s+", " ", text[match.end():next_start]).strip()
        if not section:
            continue
        current = sections.get(item, "")
        if len(section) > len(current):
            sections[item] = section
    return sections


def _summarize_item_section(section: str, *, max_sentences: int = 2, max_chars: int = 320) -> str | None:
    sentences = [
        sentence.strip()
        for sentence in _ITEM_SUMMARY_SENTENCE_RE.split(section)
        if len(sentence.strip()) > 35
    ]
    if not sentences:
        return None

    summary_parts: list[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        if lower.startswith("the information in item"):
            continue
        if lower.startswith("forward-looking statements"):
            continue
        if len(sentence.split()) <= 8 and not re.search(r"\d", sentence):
            continue
        candidate = " ".join(summary_parts + [sentence]).strip()
        if len(candidate) > max_chars and summary_parts:
            break
        summary_parts.append(sentence)
        if len(summary_parts) >= max_sentences:
            break

    if not summary_parts:
        return None
    return " ".join(summary_parts).strip()


def _summarize_material_items(text: str, items: list[str]) -> tuple[str | None, dict[str, str]]:
    sections = _extract_item_sections(text)
    if not sections:
        return None, {}

    item_summaries: dict[str, str] = {}
    for item in items:
        section = sections.get(item)
        if not section:
            continue
        summary = _summarize_item_section(section)
        if summary:
            item_summaries[item] = summary

    if not item_summaries:
        return None, {}

    ordered = [item_summaries[item] for item in items if item in item_summaries]
    combined = " ".join(ordered[:2]).strip()
    return combined[:360].rstrip(), item_summaries


async def _extract_with_claude(content: str, thesis: Thesis) -> dict[str, Any] | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        relevant = _extract_relevant_sections(content)
        prompt = _EXTRACTION_PROMPT.format(
            why_own_it=thesis.why_own_it or "",
            must_remain_true=thesis.must_remain_true or "Not specified",
            what_would_change_my_mind=thesis.what_would_change_my_mind or "Not specified",
            content=relevant,
            limit=len(relevant),
        )
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=20,
        )
        text = (response.content[0].text if response.content else "").strip()
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        return json.loads(text)
    except Exception as exc:
        logger.warning("Claude earnings extraction failed: %s", exc)
        return None


async def enrich_earnings_candidates(
    candidates: list[dict[str, Any]],
    thesis: Thesis,
) -> list[dict[str, Any]]:
    """Enrich 8-K candidates with either earnings or material filing detail."""
    result = []
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        if candidate.get("event_type") != "edgar_8k":
            result.append(candidate)
            continue

        if "2.02" in evidence.get("items", []):
            candidate = await _enrich_single(candidate, thesis)
        else:
            candidate = await _enrich_material_filing(candidate)
        result.append(candidate)
    return result


async def _enrich_single(
    candidate: dict[str, Any], thesis: Thesis
) -> dict[str, Any]:
    evidence = candidate.get("evidence", {})
    doc_url = evidence.get("url", "")
    accession = evidence.get("edgar_accession", "")

    cik = _cik_from_url(doc_url)
    if not cik or not accession:
        return candidate

    exhibit_url = await _find_exhibit_url(cik, accession)
    if not exhibit_url:
        logger.debug("No EX-99.1 found for %s", accession)
        return candidate

    text = await _fetch_text(exhibit_url)
    if not text or len(text) < 200:
        return candidate

    extraction = await _extract_with_claude(text, thesis)
    if not extraction:
        return candidate

    headline = extraction.get("headline_metric", "")
    rationale = extraction.get("verdict_rationale", "")
    ticker = evidence.get("description", "earnings").replace("Earnings Release", "").strip(" —:")

    enriched = {**candidate}
    if headline:
        enriched["description"] = f"Earnings: {headline}. {rationale}".strip()

    enriched["evidence"] = {
        **evidence,
        "url": exhibit_url,  # point to the press release, not the 8-K wrapper
        "extracted": {
            "revenue": extraction.get("revenue"),
            "gross_margin": extraction.get("gross_margin"),
            "segment_revenue": extraction.get("segment_revenue"),
            "guidance": extraction.get("guidance"),
            "thesis_verdict": extraction.get("thesis_verdict"),
            "verdict_rationale": rationale,
            "key_quote": extraction.get("key_quote"),
        },
    }
    return enriched


async def _enrich_material_filing(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence", {})
    doc_url = evidence.get("url", "")
    items = evidence.get("items", [])
    if not doc_url or not isinstance(items, list):
        return candidate

    text = await _fetch_text(doc_url)
    if not text or len(text) < 200:
        return candidate

    summary, item_summaries = _summarize_material_items(text, items)
    if not summary:
        return candidate

    enriched = {**candidate}
    enriched["description"] = summary
    enriched["evidence"] = {
        **evidence,
        "extracted": {
            "item_summary": summary,
            "item_summaries": item_summaries,
        },
    }
    return enriched
