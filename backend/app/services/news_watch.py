"""Qualitative ``news_watch`` signals: evaluate incoming news/filings against a
user's natural-language watch condition.

A news_watch signal stores ``{watch_for, direction}`` — e.g. "AMD lands a major
data-center design win" / "threatens". This module decides which incoming
news/8-K candidates satisfy which watch conditions, in two stages:

  1. a cheap EMBEDDING pre-filter (only consider semantically close pairs), then
  2. an LLM JUDGE on the close pairs ("does this news actually satisfy the
     condition?") that returns a severity.

Both stages are injected into ``match_news_watches`` so the orchestration is
pure and unit-testable; the real embedding/judge implementations live here too
and degrade gracefully (no key → no qualitative firing, never a crash).
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.config import settings
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)

# Candidate event types that carry news/filing prose worth matching.
NEWS_LIKE_EVENT_TYPES = {
    "news_or_earnings_candidate",
    "gemini_news",
    "news_keyword_match",
    "edgar_8k",
}

# Cosine similarity floor for the embedding pre-filter (unit vectors → dot = cos).
# We do not use one flat threshold:
# - structured filing text can clear a slightly lower bar because it is rarer
#   and more information-dense;
# - noisy keyword/news candidates need a stricter bar so they do not fan out
#   into unnecessary judge calls.
DEFAULT_SIMILARITY_THRESHOLD = 0.45
EVENT_TYPE_SIMILARITY_THRESHOLDS = {
    "edgar_8k": 0.38,
    "news_or_earnings_candidate": 0.45,
    "gemini_news": 0.50,
    "news_keyword_match": 0.58,
}
# Hard cap on judge LLM calls per thesis per run, so a busy news day can't fan
# out into an unbounded number of paid calls.
MAX_JUDGE_CALLS = 25
_EMBED_MODEL = "text-embedding-3-small"


@dataclass
class NewsWatch:
    signal_id: str | None
    claim_id: str | None
    watch_for: str
    direction: str  # "threatens" | "supports"
    label: str | None = None


@dataclass
class NewsWatchVerdict:
    matches: bool
    severity: str  # info | warning | thesis_breaking
    reason: str


def candidate_text(candidate: dict[str, Any]) -> str:
    """The prose to match a candidate against — headline + summary if present."""
    evidence = candidate.get("evidence") or {}
    headline = (evidence.get("headline") or "").strip()
    summary = (evidence.get("summary") or evidence.get("description") or "").strip()
    if headline or summary:
        return f"{headline}. {summary}".strip(". ").strip()
    return (candidate.get("description") or "").strip()


def _word_overlap_similarity(a: str, b: str) -> float:
    """Cheap fallback similarity when embeddings are unavailable."""
    wa = {w for w in _norm_words(a)}
    wb = {w for w in _norm_words(b)}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _norm_words(text: str) -> list[str]:
    import re

    return [w for w in re.findall(r"\w{3,}", text.lower())]


async def build_embedding_similarity(texts: list[str]) -> Callable[[str, str], float]:
    """Pre-embed ``texts`` once and return a sync ``similarity(a, b)``.

    Uses OpenAI embeddings (unit vectors → dot product is cosine). On any failure
    or missing key, falls back to word-overlap similarity so the pre-filter still
    works (the LLM judge is the precision gate anyway).
    """
    unique = sorted({t for t in texts if t and t.strip()})
    if not unique or not settings.openai_api_key:
        return _word_overlap_similarity

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.embeddings.create(model=_EMBED_MODEL, input=unique)
        vecs = {t: d.embedding for t, d in zip(unique, resp.data)}
    except Exception as exc:  # pragma: no cover - network/SDK failure path
        logger.warning("news_watch embedding failed, falling back to word overlap: %s", exc)
        return _word_overlap_similarity

    def _similarity(a: str, b: str) -> float:
        va, vb = vecs.get(a), vecs.get(b)
        if va is None or vb is None:
            return _word_overlap_similarity(a, b)
        return sum(x * y for x, y in zip(va, vb))

    return _similarity


_JUDGE_SYSTEM = """You decide whether a news item satisfies a specific condition an investor is watching for.

The investor is watching for a discrete, recognisable event. Be strict: only say it matches if the news clearly reports that the specific event has actually occurred (or is officially confirmed) — not merely that it is related, rumoured, or could happen.

Important disqualifiers:
- If the article says the event was denied, did NOT happen, was only rumoured, was speculative, is merely being considered, is in talks, could happen, may happen, or lacks official confirmation, then matches=false.
- Pay close attention to negation and inversion. "denies partnership", "rules out acquisition", "no formal agreement", and "rumors of a ban" are NOT matches for the positive event.
- Related context is not enough. The article must report the watched event itself, not just discuss the same topic.

Output valid JSON: {"matches": true|false, "severity": "info|warning|thesis_breaking", "reason": "one short sentence"}
- matches=false → severity "info", reason explains why it doesn't satisfy the condition.
- matches=true → severity is "thesis_breaking" if the event clearly and fully occurred, "warning" if it is occurring/partial/early. Never "info" when matches=true.
Output ONLY valid JSON."""

_JUDGE_USER = """Condition the investor is watching for ({direction}): "{watch_for}"

News item:
{evidence_text}"""


async def judge_news_watch(evidence_text: str, watch_for: str, direction: str) -> NewsWatchVerdict:
    """LLM judge: does this news satisfy the watch condition? Conservative — with
    no API key it returns no-match (qualitative signals simply don't fire rather
    than guess)."""
    if not settings.anthropic_api_key:
        return NewsWatchVerdict(matches=False, severity="info", reason="judge unavailable")
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=256,
            system=_JUDGE_SYSTEM,
            messages=[{
                "role": "user",
                "content": _JUDGE_USER.format(direction=direction, watch_for=watch_for, evidence_text=evidence_text),
            }],
            timeout=30.0,
        )
        data = json.loads(strip_code_fences(resp.content[0].text.strip()))
        matches = bool(data.get("matches"))
        severity = data.get("severity")
        if severity not in {"info", "warning", "thesis_breaking"}:
            severity = "warning" if matches else "info"
        if matches and severity == "info":
            severity = "warning"
        return NewsWatchVerdict(matches=matches, severity=severity, reason=str(data.get("reason") or ""))
    except Exception as exc:
        logger.error("news_watch judge failed (%s): %s", type(exc).__name__, exc)
        return NewsWatchVerdict(matches=False, severity="info", reason="judge error")


SimilarityFn = Callable[[str, str], float]
JudgeFn = Callable[[str, str, str], Awaitable[NewsWatchVerdict]]


def similarity_threshold_for_candidate(
    candidate: dict[str, Any],
    *,
    threshold: float | None = None,
) -> float:
    """Return the cosine floor for this candidate.

    A custom threshold overrides the adaptive mapping and is used verbatim.
    """
    if threshold is not None:
        return threshold
    return EVENT_TYPE_SIMILARITY_THRESHOLDS.get(
        str(candidate.get("event_type") or ""),
        DEFAULT_SIMILARITY_THRESHOLD,
    )


async def match_news_watches(
    candidates: list[dict[str, Any]],
    watches: list[NewsWatch],
    *,
    similarity: SimilarityFn,
    judge: JudgeFn,
    threshold: float | None = None,
) -> dict[int, tuple[NewsWatch, str, str]]:
    """Tag news/filing candidates that satisfy a watch condition.

    For each news-like candidate, find the most similar watch (>= threshold), ask
    the judge to confirm, and on a confirmed match link the candidate to that
    signal (so it fires with attribution + cooldown). Returns a map of
    ``id(candidate) -> (watch, severity, reason)`` for confirmed matches; the
    caller uses the judge's severity directly instead of re-classifying.
    """
    matched: dict[int, tuple[NewsWatch, str, str]] = {}
    if not watches or not candidates:
        return matched

    judge_calls = 0
    for candidate in candidates:
        if candidate.get("event_type") not in NEWS_LIKE_EVENT_TYPES:
            continue
        evidence = candidate.get("evidence") or {}
        if evidence.get("signal_id"):
            continue  # already linked to a specific signal — leave it
        text = candidate_text(candidate)
        if not text:
            continue
        candidate_threshold = similarity_threshold_for_candidate(candidate, threshold=threshold)

        best: tuple[float, NewsWatch] | None = None
        for watch in watches:
            sim = similarity(text, watch.watch_for)
            if sim >= candidate_threshold and (best is None or sim > best[0]):
                best = (sim, watch)
        if best is None:
            continue

        if judge_calls >= MAX_JUDGE_CALLS:
            break
        judge_calls += 1
        watch = best[1]
        verdict = await judge(text, watch.watch_for, watch.direction)
        if not verdict.matches:
            continue

        # Two safety caps:
        #  - a "supports" watch firing is good news, not a threat → "info";
        #  - a "threatens" qualitative match is fuzzy (one embedding + one LLM
        #    judge), so cap it at "warning". We never let a single judge call
        #    declare "thesis_breaking" and auto-flip the thesis to needs_review;
        #    the user reviews it instead.
        if watch.direction == "supports":
            severity = "info"
        else:
            severity = "warning" if verdict.severity == "thesis_breaking" else verdict.severity

        evidence = candidate.setdefault("evidence", {})
        if watch.signal_id:
            evidence["signal_id"] = str(watch.signal_id)
        if watch.claim_id:
            evidence["claim_id"] = str(watch.claim_id)
        evidence["news_watch_direction"] = watch.direction
        matched[id(candidate)] = (watch, severity, verdict.reason)

    return matched
