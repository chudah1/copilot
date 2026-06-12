from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.monitoring_pipeline import (
    _build_transcript_windows,
    _relevant_transcript_highlights,
    _thesis_aware_highlights,
)


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
