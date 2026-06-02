"""Guardrail: monitoring must stay fail-closed at the source.

The product fights noise with several downstream suppression layers; the cheapest
way to keep signal sharp is to not fire in the first place when the AI judge is
uncertain. These tests lock that in: a qualitative candidate the judge can't
confidently classify is dropped, while an objective threshold breach (which the
user defined) still fires without the LLM. If someone makes the pipeline
fire-on-uncertainty, this turns red.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.thesis import Thesis
from app.services.monitoring_pipeline import classify_candidates_for_thesis

_PIPE = "app.services.monitoring_pipeline"


def _thesis():
    return Thesis(
        thesis_kind="company", why_own_it="Durable moat.", must_remain_true="Margins hold.",
        what_would_change_my_mind="Margins compress.", confidence="high",
        review_cadence_days=7, interpretation={"watch_hints": []}, source="user",
    )


def _news_candidate():
    return {"event_type": "gemini_news", "description": "Some industry headline.", "evidence": {}}


def _price_candidate():
    return {"event_type": "price_move", "description": "Price moved 12%.", "evidence": {}}


async def test_qualitative_candidate_dropped_when_judge_returns_none():
    with patch(f"{_PIPE}.classify_event", new_callable=AsyncMock, return_value=None):
        classified = await classify_candidates_for_thesis(_thesis(), [_news_candidate()])
    assert classified == []  # uncertain news must not fire


async def test_qualitative_candidate_dropped_on_skip_verdict():
    skip = SimpleNamespace(severity="skip", analysis=None)
    with patch(f"{_PIPE}.classify_event", new_callable=AsyncMock, return_value=skip):
        classified = await classify_candidates_for_thesis(_thesis(), [_news_candidate()])
    assert classified == []


async def test_objective_breach_still_fires_without_the_llm():
    # A price move past threshold is objective — it must not depend on the judge.
    with patch(f"{_PIPE}.classify_event", new_callable=AsyncMock, return_value=None):
        classified = await classify_candidates_for_thesis(_thesis(), [_price_candidate()])
    assert len(classified) == 1
    assert classified[0][0]["event_type"] == "price_move"


async def test_confident_qualitative_verdict_does_fire():
    verdict = SimpleNamespace(severity="warning", analysis="This touches the moat.")
    with patch(f"{_PIPE}.classify_event", new_callable=AsyncMock, return_value=verdict):
        classified = await classify_candidates_for_thesis(_thesis(), [_news_candidate()])
    assert len(classified) == 1
    assert classified[0][1] == "warning"
