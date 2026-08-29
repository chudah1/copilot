from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm.exc import DetachedInstanceError

from app.services.monitoring_pipeline import (
    _build_transcript_windows,
    _expand_transcript_candidates_for_watches,
    _relevant_transcript_highlights,
    _thesis_aware_highlights,
    expand_transcript_candidates_for_signals,
)
from app.services.news_watch import NewsWatch


def test_build_transcript_windows_keeps_question_with_answer():
    transcript = (
        "Analyst: How is the new healthcare hardware line performing? "
        "CEO: It is accelerating rapidly and margins are crushing it."
    )

    windows = _build_transcript_windows(transcript)

    assert len(windows) == 2
    assert windows[1][0] == "CEO: It is accelerating rapidly and margins are crushing it."
    assert "How is the new healthcare hardware line performing?" in windows[1][1]
    assert "It is accelerating rapidly and margins are crushing it." in windows[1][1]


@pytest.mark.asyncio
async def test_thesis_aware_highlights_uses_context_window_for_anaphoric_answer(monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        "test-key",
        raising=False,
    )

    transcript = (
        "Analyst: How is the new healthcare hardware line performing? "
        "CEO: It is accelerating rapidly and margins are crushing it."
    )

    async def fake_create(*, model, input):
        vectors = []
        for text in input:
            if text == "Apple's healthcare hardware push must keep scaling.":
                vectors.append([1.0, 0.0])
            elif "How is the new healthcare hardware line performing?" in text and "It is accelerating rapidly" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])

    fake_client = MagicMock()
    fake_client.embeddings.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        highlights = await _thesis_aware_highlights(
            transcript,
            "Apple's healthcare hardware push must keep scaling.",
            None,
            None,
        )

    assert highlights is not None
    assert "CEO: It is accelerating rapidly and margins are crushing it." in highlights


@pytest.mark.asyncio
async def test_relevant_transcript_highlights_supports_signal_focused_windows(monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        "test-key",
        raising=False,
    )

    transcript = (
        "Analyst: How is Blackwell deployment progressing with hyperscalers? "
        "CEO: It is ahead of plan and supply constraints are easing."
    )

    async def fake_create(*, model, input):
        vectors = []
        for text in input:
            if text == "Blackwell deployment":
                vectors.append([1.0, 0.0])
            elif "Blackwell deployment progressing" in text and "ahead of plan" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])

    fake_client = MagicMock()
    fake_client.embeddings.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        highlights = await _relevant_transcript_highlights(
            transcript,
            ["Blackwell deployment"],
        )

    assert highlights is not None
    assert "CEO: It is ahead of plan and supply constraints are easing." in highlights


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_watches_creates_topic_specific_candidates(monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        None,
        raising=False,
    )

    transcript = (
        "Analyst: How is MI350 demand trending with cloud customers? "
        "CEO: MI350 demand is strong and customer deployments are accelerating. "
        "Analyst: Any update on consumer GPUs? "
        "CEO: We remain disciplined there."
    )
    candidate = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {
            "quarter": "2026Q2",
            "full_transcript": transcript,
            "highlights": ["Generic highlight."],
        },
    }
    watch = NewsWatch(
        signal_id="sig1",
        claim_id="cl1",
        watch_for="AMD MI350 demand commentary",
        direction="supports",
        label="AMD MI350 demand commentary",
    )

    expanded = await _expand_transcript_candidates_for_watches([candidate], [watch])

    assert len(expanded) == 2
    watch_specific = expanded[1]
    assert watch_specific["description"].startswith("2026Q2 earnings call on AMD MI350 demand commentary:")
    assert "AMD MI350 demand commentary" in watch_specific["evidence"]["topic_context"]
    assert any(
        "MI350 demand is strong and customer deployments are accelerating." in highlight
        for highlight in watch_specific["evidence"]["highlights"]
    )


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_signals_creates_per_signal_candidates(monkeypatch):
    """Every active signal — not just news_watch ones — should get its own
    transcript candidate pre-bound to that signal. AMD-style segment-commentary
    theses with revenue_growth signals previously had effectively zero
    transcript coverage because only news_watches drove the expansion."""
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        None,
        raising=False,
    )

    transcript = (
        "Analyst: How is data center revenue trending this quarter? "
        "CEO: Data center revenue grew 50% year over year and demand keeps accelerating. "
        "Analyst: Any update on margins? "
        "CEO: Gross margin stayed above 75% on operating leverage."
    )
    transcript_candidate = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {
            "quarter": "2026Q2",
            "full_transcript": transcript,
        },
    }

    # Two active signals on one claim — revenue and margin. Both should
    # produce a transcript candidate keyed to that signal.
    rev_signal = SimpleNamespace(
        id="rev-sig",
        signal_label="NVDA data center revenue growth",
        rationale="Data center growth is the main pillar.",
        active=True,
    )
    margin_signal = SimpleNamespace(
        id="margin-sig",
        signal_label="NVDA gross margin trend",
        rationale="Margin compression would weaken the case.",
        active=True,
    )
    entity = SimpleNamespace(signals=[rev_signal, margin_signal])
    claim = SimpleNamespace(
        id="claim-1",
        claim_text="NVDA data center revenue grows above 20% YoY with margin holding above 70%",
        entities=[entity],
    )

    expanded = await expand_transcript_candidates_for_signals(
        [transcript_candidate], [claim]
    )

    assert len(expanded) == 3  # original + 2 signal-keyed
    revenue_specific = expanded[1]
    margin_specific = expanded[2]
    # Each new candidate carries the signal_id and a single-entry multi-binding
    # list so downstream coverage + cooldown attribute correctly.
    assert revenue_specific["evidence"]["signal_id"] == "rev-sig"
    assert revenue_specific["evidence"]["matched_signal_ids"] == ["rev-sig"]
    assert margin_specific["evidence"]["signal_id"] == "margin-sig"
    # The transcript excerpt for the revenue-focused candidate should be the
    # revenue-related sentence, not the margin one.
    assert "data center revenue" in revenue_specific["evidence"]["excerpt"].lower()
    assert "margin" in margin_specific["evidence"]["excerpt"].lower()


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_signals_does_not_lazy_load_detached_signal_entity(
    monkeypatch,
):
    """Direction inference must survive signals detached from the ORM session."""
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        None,
        raising=False,
    )

    class DetachedSignal:
        id = "threat-sig"
        signal_type = "transcript_topic"
        signal_label = "competitive pressure"
        rationale = "A competitor could weaken the case."
        active = True
        signal_config_json = None

        @property
        def entity(self):
            raise DetachedInstanceError("signal entity is detached")

    transcript_candidate = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {
            "quarter": "2026Q2",
            "full_transcript": "Management discussed competitive pressure and new entrants.",
            "highlights": ["Management discussed competitive pressure and new entrants."],
            "excerpt": "Management discussed competitive pressure and new entrants.",
        },
    }
    entity = SimpleNamespace(
        relation_type="threatened_by",
        signals=[DetachedSignal()],
    )
    claim = SimpleNamespace(
        id="claim-1",
        claim_text="The competitive position remains durable",
        entities=[entity],
    )

    expanded = await expand_transcript_candidates_for_signals([transcript_candidate], [claim])

    assert expanded[1]["evidence"]["signal_direction"] == "threatens"


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_signals_skips_inactive_signals(monkeypatch):
    """Inactive signals (user-rejected) should not produce transcript
    candidates — they don't bind to events anywhere else either."""
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        None,
        raising=False,
    )
    transcript_candidate = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {
            "quarter": "2026Q2",
            "full_transcript": "Revenue accelerated this quarter.",
        },
    }
    inactive = SimpleNamespace(
        id="inactive-sig",
        signal_label="X",
        rationale="",
        active=False,
    )
    entity = SimpleNamespace(signals=[inactive])
    claim = SimpleNamespace(id="c", claim_text="x", entities=[entity])

    expanded = await expand_transcript_candidates_for_signals(
        [transcript_candidate], [claim]
    )
    assert len(expanded) == 1


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_transcript_topic_falls_back_to_generic_highlights(monkeypatch):
    """If a transcript_topic signal can't find a tighter signal-specific
    window, keep the signal-bound candidate by reusing the generic transcript
    highlights instead of dropping to the unbound transcript event."""
    monkeypatch.setattr(
        "app.services.monitoring_pipeline.settings.openai_api_key",
        None,
        raising=False,
    )
    transcript_candidate = {
        "event_type": "earnings_call_transcript",
        "description": "Earnings call",
        "evidence": {
            "quarter": "2026Q2",
            "full_transcript": "Now let us turn to Services, which set an all-time revenue record with $31 billion.",
            "highlights": ["Now let us turn to Services, which set an all-time revenue record with $31 billion."],
            "excerpt": "Now let us turn to Services, which set an all-time revenue record with $31 billion.",
        },
    }
    support_signal = SimpleNamespace(
        id="support-sig",
        signal_type="transcript_topic",
        signal_label="AAPL ecosystem retention commentary",
        rationale="Management commentary should reinforce ecosystem durability.",
        active=True,
    )
    entity = SimpleNamespace(signals=[support_signal])
    claim = SimpleNamespace(
        id="claim-1",
        claim_text="AAPL ecosystem retention and engagement remain durable",
        entities=[entity],
    )

    expanded = await expand_transcript_candidates_for_signals([transcript_candidate], [claim])

    assert len(expanded) == 2
    signal_bound = expanded[1]
    assert signal_bound["evidence"]["signal_id"] == "support-sig"
    assert signal_bound["evidence"]["matched_signal_ids"] == ["support-sig"]
    assert signal_bound["evidence"]["excerpt"] == transcript_candidate["evidence"]["excerpt"]


@pytest.mark.asyncio
async def test_expand_transcript_candidates_for_signals_noop_without_transcripts():
    """If the candidate set has no transcripts, the expansion is a no-op
    (we can't extract from text that isn't there). Important so the
    pipeline can call this unconditionally without paying for embedding
    calls on news-only passes."""
    candidates = [{"event_type": "news_or_earnings_candidate", "evidence": {}}]
    claim = SimpleNamespace(
        id="c",
        claim_text="x",
        entities=[SimpleNamespace(signals=[SimpleNamespace(
            id="s", signal_label="X", rationale="", active=True,
        )])],
    )
    expanded = await expand_transcript_candidates_for_signals(candidates, [claim])
    assert expanded == candidates
