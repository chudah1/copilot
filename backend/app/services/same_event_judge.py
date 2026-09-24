from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)

SAME_EVENT_MODEL = settings.openai_fast_model
MAX_BUCKET_CANDIDATES = 5


@dataclass(frozen=True)
class SameEventCandidate:
    candidate_id: str
    headline: str
    summary: str = ""
    source_domain: str = ""
    signal_label: str = ""
    matched_topics: str = ""
    topic_context: str = ""


@dataclass(frozen=True)
class SameEventJudgment:
    left_id: str
    right_id: str
    same_event: bool
    confidence: float
    reason: str


_SAME_EVENT_SYSTEM = """You decide whether pairs of finance news items describe the same underlying real-world event.

Return same_event=true only when the two items are two tellings of the same concrete event.

Examples of same_event=true:
- the same analyst note retold by different publishers
- the same filing or earnings release covered by multiple outlets
- the same financing, partnership, guidance change, product launch, or regulatory action rewritten by multiple sites

Examples of same_event=false:
- same company but different analyst firms
- same thesis signal but different reports or developments
- commentary pieces or roundups on a similar theme
- one article about a broader topic and another about a specific event

Be conservative. If uncertain, return same_event=false with lower confidence.

Output ONLY valid JSON:
{"judgments":[{"left_id":"a","right_id":"b","same_event":true,"confidence":0.91,"reason":"short phrase"}]}
Return one judgment for every supplied pair."""


def _candidate_payload(candidate: SameEventCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "headline": candidate.headline[:200],
        "summary": candidate.summary[:400],
        "source_domain": candidate.source_domain[:120],
        "signal_label": candidate.signal_label[:200],
        "matched_topics": candidate.matched_topics[:200],
        "topic_context": candidate.topic_context[:200],
    }


def _pair_key(left_id: str, right_id: str) -> tuple[str, str]:
    return (left_id, right_id) if left_id <= right_id else (right_id, left_id)


def _coerce_same_event_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return bool(value)


def _normalize_judgments(
    parsed: dict[str, Any],
    *,
    expected_pairs: list[tuple[str, str]],
) -> list[SameEventJudgment]:
    raw_items = parsed.get("judgments")
    if not isinstance(raw_items, list):
        raw_items = []

    normalized: dict[tuple[str, str], SameEventJudgment] = {}
    expected_set = {_pair_key(left, right) for left, right in expected_pairs}

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        left_id = str(item.get("left_id") or "").strip()
        right_id = str(item.get("right_id") or "").strip()
        if not left_id or not right_id or left_id == right_id:
            continue
        key = _pair_key(left_id, right_id)
        if key not in expected_set or key in normalized:
            continue
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        normalized[key] = SameEventJudgment(
            left_id=key[0],
            right_id=key[1],
            same_event=_coerce_same_event_flag(item.get("same_event")),
            confidence=max(0.0, min(1.0, confidence)),
            reason=str(item.get("reason") or "").strip()[:200],
        )

    judgments: list[SameEventJudgment] = []
    for left_id, right_id in expected_pairs:
        key = _pair_key(left_id, right_id)
        judgment = normalized.get(key)
        if judgment is None:
            judgment = SameEventJudgment(
                left_id=key[0],
                right_id=key[1],
                same_event=False,
                confidence=0.0,
                reason="missing_judgment",
            )
        judgments.append(judgment)
    return judgments


async def judge_same_event_bucket(
    candidates: list[SameEventCandidate],
) -> list[SameEventJudgment]:
    """Judge all unordered pairs in one same-signal bucket.

    Fail-open: on missing API key, provider failure, timeout, or parse error,
    return an empty list so the caller performs no extra suppression.
    """
    if len(candidates) < 2 or not settings.openai_api_key:
        return []

    candidates = candidates[:MAX_BUCKET_CANDIDATES]
    pair_ids: list[tuple[str, str]] = []
    for idx, left in enumerate(candidates):
        for right in candidates[idx + 1 :]:
            pair_ids.append((left.candidate_id, right.candidate_id))
    if not pair_ids:
        return []

    prompt_payload = {
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
        "pairs": [
            {"left_id": left_id, "right_id": right_id}
            for left_id, right_id in pair_ids
        ],
    }

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=SAME_EVENT_MODEL,
            messages=[
                {"role": "system", "content": _SAME_EVENT_SYSTEM},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=True)},
            ],
            max_completion_tokens=1200,
            extra_body={"reasoning_effort": "low"},
            response_format={"type": "json_object"},
            timeout=20.0,
        )
        raw = strip_code_fences((response.choices[0].message.content or "").strip())
        parsed = json.loads(raw)
        return _normalize_judgments(parsed, expected_pairs=pair_ids)
    except Exception as exc:
        logger.warning("Same-event judge failed (%s): %s", type(exc).__name__, exc)
        return []
