"""Tests for qualitative news_watch matching (embed pre-filter + judge)."""
import re
from types import SimpleNamespace

import pytest

from app.services.news_watch import (
    EVENT_TYPE_SIMILARITY_THRESHOLDS,
    NewsWatch,
    NewsWatchVerdict,
    _JUDGE_SYSTEM,
    candidate_text,
    judge_news_watch,
    match_news_watches,
    similarity_threshold_for_candidate,
)
from app.services.monitoring_pipeline import extract_news_watches, extract_provisional_news_watches


def _kw_similarity(a: str, b: str) -> float:
    """Deterministic stand-in: 1.0 if the texts share a 4+ char word, else 0.0."""
    aw = set(re.findall(r"\w{4,}", a.lower()))
    bw = set(re.findall(r"\w{4,}", b.lower()))
    return 1.0 if (aw & bw) else 0.0


async def _judge_yes(text, watch_for, direction):
    return NewsWatchVerdict(matches=True, severity="thesis_breaking", reason="clearly occurred")


async def _judge_no(text, watch_for, direction):
    return NewsWatchVerdict(matches=False, severity="info", reason="not the event")


def _news(headline, summary="", event_type="news_or_earnings_candidate", signal_id=None):
    ev = {"headline": headline, "summary": summary, "article_id": "a1"}
    if signal_id:
        ev["signal_id"] = signal_id
    return {"event_type": event_type, "description": f"{headline} — {summary}", "evidence": ev}


_WATCH = NewsWatch(signal_id="sig1", claim_id="cl1", watch_for="AMD lands a major design win", direction="threatens")


def test_candidate_text_uses_headline_and_summary():
    txt = candidate_text({"evidence": {"headline": "Big news", "summary": "details here"}})
    assert "Big news" in txt and "details here" in txt


def test_candidate_text_uses_transcript_highlights_first():
    txt = candidate_text(
        {
            "event_type": "earnings_call_transcript",
            "evidence": {"highlights": ["Blackwell demand remains strong.", "Supply is improving."]},
        }
    )
    assert txt == "Blackwell demand remains strong."


@pytest.mark.asyncio
async def test_match_links_candidate_on_confirmed_match():
    cand = _news("AMD announces major design win with hyperscaler")
    matched = await match_news_watches([cand], [_WATCH], similarity=_kw_similarity, judge=_judge_yes)
    assert id(cand) in matched
    assert cand["evidence"]["signal_id"] == "sig1"
    assert cand["evidence"]["claim_id"] == "cl1"
    # threatens judge=thesis_breaking is capped to warning (no auto status flip)
    assert matched[id(cand)][1] == "warning"


def test_extract_news_watches_lifts_active_topic_signals():
    signal = SimpleNamespace(
        id="sig1",
        active=True,
        signal_type="transcript_topic",
        signal_label="NVDA Blackwell deployment",
        rationale="Blackwell rollout commentary matters.",
        signal_config_json={"topic": "Blackwell deployment"},
    )
    entity = SimpleNamespace(relation_type="validated_by", signals=[signal])
    claim = SimpleNamespace(id="cl1", entities=[entity])

    watches = extract_news_watches([claim])

    assert len(watches) == 1
    assert watches[0].watch_for == "Blackwell deployment"
    assert watches[0].direction == "supports"
    assert watches[0].signal_id == "sig1"
    assert watches[0].claim_id == "cl1"


@pytest.mark.asyncio
async def test_provisional_match_tags_claim_only_without_fake_signal_id():
    cand = _news("Regulators restrict compounded GLP-1 access")
    watch = NewsWatch(
        signal_id=None,
        claim_id="cl1",
        watch_for="the FDA restricts compounded GLP-1 and the company has no replacement path",
        direction="threatens",
    )

    matched = await match_news_watches([cand], [watch], similarity=lambda a, b: 1.0, judge=_judge_yes)

    assert id(cand) in matched
    assert "signal_id" not in cand["evidence"]
    assert cand["evidence"]["claim_id"] == "cl1"
    assert cand["evidence"]["news_watch_direction"] == "threatens"


@pytest.mark.asyncio
async def test_match_skips_below_similarity_threshold():
    cand = _news("Apple unveils new iPhone colors")
    matched = await match_news_watches([cand], [_WATCH], similarity=_kw_similarity, judge=_judge_yes)
    assert matched == {}
    assert "signal_id" not in cand["evidence"]


def test_similarity_threshold_uses_event_type_mapping():
    assert similarity_threshold_for_candidate({"event_type": "edgar_8k"}) == EVENT_TYPE_SIMILARITY_THRESHOLDS["edgar_8k"]
    assert similarity_threshold_for_candidate({"event_type": "news_keyword_match"}) == EVENT_TYPE_SIMILARITY_THRESHOLDS["news_keyword_match"]


@pytest.mark.asyncio
async def test_match_uses_lower_threshold_for_edgar_8k():
    cand = _news(
        "Company amends credit agreement for acquisition financing",
        event_type="edgar_8k",
    )

    matched = await match_news_watches(
        [cand],
        [NewsWatch(signal_id="sig1", claim_id="cl1", watch_for="credit agreement amended for acquisition financing", direction="threatens")],
        similarity=lambda a, b: 0.40,
        judge=_judge_yes,
    )

    assert id(cand) in matched


@pytest.mark.asyncio
async def test_match_uses_transcript_candidates_for_topic_watches():
    cand = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {"highlights": ["Blackwell deployment is ahead of plan."]},
    }
    watch = NewsWatch(
        signal_id="sig1",
        claim_id="cl1",
        watch_for="Blackwell deployment",
        direction="supports",
    )

    matched = await match_news_watches([cand], [watch], similarity=lambda a, b: 1.0, judge=_judge_yes)

    assert id(cand) in matched
    assert cand["evidence"]["signal_id"] == "sig1"
    assert cand["evidence"]["news_watch_direction"] == "supports"


@pytest.mark.asyncio
async def test_match_uses_stricter_threshold_for_keyword_news():
    cand = _news(
        "Blog speculates on a possible partnership",
        event_type="news_keyword_match",
    )

    matched = await match_news_watches(
        [cand],
        [NewsWatch(signal_id="sig1", claim_id="cl1", watch_for="company announces a major strategic partnership", direction="supports")],
        similarity=lambda a, b: 0.50,
        judge=_judge_yes,
    )

    assert matched == {}


@pytest.mark.asyncio
async def test_match_skips_when_judge_rejects():
    cand = _news("Speculation swirls about a possible AMD design effort")
    matched = await match_news_watches([cand], [_WATCH], similarity=_kw_similarity, judge=_judge_no)
    assert matched == {}
    assert "signal_id" not in cand["evidence"]


@pytest.mark.asyncio
async def test_match_ignores_non_news_event_types():
    cand = {"event_type": "price_move", "description": "AMD design win", "evidence": {}}
    matched = await match_news_watches([cand], [_WATCH], similarity=lambda a, b: 1.0, judge=_judge_yes)
    assert matched == {}


@pytest.mark.asyncio
async def test_match_skips_already_linked_candidate():
    cand = _news("AMD lands a major design win", signal_id="other")
    matched = await match_news_watches([cand], [_WATCH], similarity=lambda a, b: 1.0, judge=_judge_yes)
    assert matched == {}
    assert cand["evidence"]["signal_id"] == "other"


@pytest.mark.asyncio
async def test_match_picks_highest_similarity_watch():
    w1 = NewsWatch(signal_id="s1", claim_id=None, watch_for="regulatory ban on exports", direction="threatens")
    w2 = NewsWatch(signal_id="s2", claim_id=None, watch_for="AMD lands a major design win", direction="threatens")
    cand = _news("AMD lands a major design win with a top hyperscaler")

    def sim(a, b):
        return 0.9 if "design" in b else 0.5  # both above threshold; design is higher

    matched = await match_news_watches([cand], [w1, w2], similarity=sim, judge=_judge_yes)
    assert cand["evidence"]["signal_id"] == "s2"


@pytest.mark.asyncio
async def test_threatens_match_is_capped_to_warning():
    cand = _news("Regulators ban exports of the company's flagship chip")
    watch = NewsWatch(signal_id="s", claim_id=None, watch_for="export ban", direction="threatens")

    async def _judge_breaking(t, wf, d):
        return NewsWatchVerdict(matches=True, severity="thesis_breaking", reason="ban confirmed")

    matched = await match_news_watches([cand], [watch], similarity=lambda a, b: 1.0, judge=_judge_breaking)
    # a single fuzzy judge call must NOT produce thesis_breaking (no auto status flip)
    assert matched[id(cand)][1] == "warning"


def test_cross_source_dedup_keeps_signal_linked_candidate():
    from app.services.noise_filter import _apply_cross_source_dedup

    # Same story from two sources; the SECOND is news_watch-linked but lower
    # specificity. Dedup must keep the linked one (so the verdict/cooldown survive).
    unlinked = {"event_type": "gemini_news", "evidence": {"headline": "AMD lands a major design win today", "article_id": "g1"}}
    linked = {"event_type": "news_or_earnings_candidate",
              "evidence": {"headline": "AMD lands a major design win today", "article_id": "a1", "signal_id": "sig1"}}
    kept = _apply_cross_source_dedup([unlinked, linked])
    assert len(kept) == 1
    assert kept[0]["evidence"].get("signal_id") == "sig1"


@pytest.mark.asyncio
async def test_supports_watch_caps_severity_and_tags_direction():
    cand = _news("Company announces a major strategic partnership with a hyperscaler")
    watch = NewsWatch(signal_id="s", claim_id=None, watch_for="a major strategic partnership", direction="supports")

    async def _judge_strong(t, wf, d):
        return NewsWatchVerdict(matches=True, severity="thesis_breaking", reason="confirmed")

    matched = await match_news_watches([cand], [watch], similarity=lambda a, b: 1.0, judge=_judge_strong)
    assert matched[id(cand)][1] == "info"  # supports never fires as a threat
    assert cand["evidence"]["news_watch_direction"] == "supports"


def test_determine_verdict_respects_news_watch_direction():
    from app.services.signal_matching import determine_verdict

    supports = {"event_type": "news_or_earnings_candidate", "evidence": {"news_watch_direction": "supports"}}
    threatens = {"event_type": "news_or_earnings_candidate", "evidence": {"news_watch_direction": "threatens"}}
    assert determine_verdict("info", supports) == "supports"
    assert determine_verdict("warning", threatens) == "threatens"


@pytest.mark.asyncio
async def test_match_no_watches_is_noop():
    cand = _news("AMD lands a major design win")
    matched = await match_news_watches([cand], [], similarity=lambda a, b: 1.0, judge=_judge_yes)
    assert matched == {}


@pytest.mark.asyncio
async def test_judge_returns_no_match_without_api_key(monkeypatch):
    import app.services.news_watch as nw

    monkeypatch.setattr(nw.settings, "anthropic_api_key", "", raising=False)
    verdict = await judge_news_watch("some news", "AMD design win", "threatens")
    assert verdict.matches is False


def test_judge_prompt_calls_out_negation_and_rumors():
    lowered = _JUDGE_SYSTEM.lower()
    assert "denied" in lowered
    assert "rumoured" in lowered or "rumored" in lowered
    assert "speculative" in lowered
    assert "negation" in lowered


class _FakeThesis:
    why_own_it = "AI demand"
    must_remain_true = None
    what_would_change_my_mind = None
    ai_summary = None


@pytest.mark.asyncio
async def test_classify_uses_news_watch_verdict_and_skips_generic_classifier(monkeypatch):
    from app.services import monitoring_pipeline as mp

    calls = {"classify": 0}

    async def _fake_classify(**kwargs):
        calls["classify"] += 1
        return None

    monkeypatch.setattr(mp, "classify_event", _fake_classify)

    cand = _news("AMD lands a major design win")
    nw_matched = {id(cand): (_WATCH, "thesis_breaking", "AMD confirmed a design win")}

    classified = await mp.classify_candidates_for_thesis(_FakeThesis(), [cand], nw_matched=nw_matched)

    assert len(classified) == 1
    assert classified[0][1] == "thesis_breaking"
    assert classified[0][2] == "AMD confirmed a design win"
    assert calls["classify"] == 0  # matched candidate bypasses the generic classifier


@pytest.mark.asyncio
async def test_match_thesis_news_watches_tags_before_filtering(monkeypatch):
    from app.services import monitoring_pipeline as mp
    import app.services.news_watch as nw

    monkeypatch.setattr(mp, "judge_news_watch", _judge_yes)
    monkeypatch.setattr(nw.settings, "openai_api_key", "", raising=False)  # force word-overlap similarity

    cand = _news("AMD lands a major design win with a top hyperscaler")
    result = await mp.match_thesis_news_watches([cand], [_WATCH])

    assert id(cand) in result
    assert cand["evidence"]["signal_id"] == "sig1"


@pytest.mark.asyncio
async def test_match_thesis_news_watches_rewrites_transcript_highlights_for_signal_focus(monkeypatch):
    from app.services import monitoring_pipeline as mp
    import app.services.news_watch as nw

    monkeypatch.setattr(mp, "judge_news_watch", _judge_yes)
    monkeypatch.setattr(nw.settings, "openai_api_key", "", raising=False)

    cand = {
        "event_type": "earnings_call_transcript",
        "description": "Latest earnings call signaled: generic demand commentary",
        "evidence": {
            "highlights": ["Generic demand commentary."],
            "full_transcript": (
                "Analyst: How is Blackwell deployment progressing with hyperscalers? "
                "CEO: It is ahead of plan and supply constraints are easing."
            ),
        },
    }
    watch = NewsWatch(
        signal_id="sig1",
        claim_id="cl1",
        watch_for="Blackwell deployment",
        direction="supports",
    )

    result = await mp.match_thesis_news_watches([cand], [watch])

    assert id(cand) in result
    assert cand["evidence"]["signal_id"] == "sig1"
    assert "ahead of plan" in " ".join(cand["evidence"]["highlights"])


def test_extract_provisional_news_watches_from_interpretation():
    watches = extract_provisional_news_watches(
        {
            "watch_hints": [
                {
                    "kind": "news_watch",
                    "watch_for": "a regulatory restriction hits compounded GLP-1 and management has no replacement path by next earnings",
                    "direction": "threatens",
                    "rationale": "This would hit the main growth driver.",
                }
            ]
        }
    )

    assert len(watches) == 1
    assert watches[0].signal_id is None
    assert watches[0].claim_id is None
    assert "compounded GLP-1" in watches[0].watch_for
