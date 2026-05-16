import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.noise_filter import (
    _apply_evidence_dedup,
    _apply_minimum_relevance,
    _apply_priority_suppression,
    _apply_signal_cooldown,
    record_signal_fired,
)


def _make_signal(signal_id: str, last_fired_at: datetime | None = None) -> MagicMock:
    signal = MagicMock()
    signal.id = uuid.UUID(signal_id)
    signal.last_fired_at = last_fired_at
    signal.consecutive_ignores = 0
    return signal


# ---------------------------------------------------------------------------
# Rule 1: Evidence dedup
# ---------------------------------------------------------------------------


def test_evidence_dedup_skips_existing_article():
    existing = {"article-123"}
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "article-123", "headline": "Old news"}},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "article-456", "headline": "New news"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 1
    assert result[0]["evidence"]["article_id"] == "article-456"


def test_evidence_dedup_skips_existing_transaction():
    existing = {"txn-abc"}
    candidates = [
        {"event_type": "insider_transaction", "evidence": {"transaction_id": "txn-abc"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 0


def test_evidence_dedup_skips_existing_transcript():
    existing = {"transcript:2026Q1"}
    candidates = [
        {"event_type": "earnings_call_transcript", "evidence": {"transcript_id": "transcript:2026Q1"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 0


def test_evidence_dedup_keeps_candidates_without_source_id():
    existing = set()
    candidates = [
        {"event_type": "price_move", "evidence": {"current_price": 150.0}},
        {"event_type": "metric_threshold", "evidence": {"metric": "pe_ratio"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 2


def test_evidence_dedup_deduplicates_within_batch():
    existing = set()
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "same-article"}},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "same-article"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Rule 2: Signal cooldown
# ---------------------------------------------------------------------------


def test_signal_cooldown_skips_recently_fired():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=now - timedelta(hours=6))
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"signal_id": signal_id, "article_id": "a1"}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map, now)
    # News cooldown is 48h, fired 6h ago → should be skipped
    assert len(result) == 0


def test_signal_cooldown_allows_after_window():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=now - timedelta(hours=50))
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"signal_id": signal_id, "article_id": "a2"}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map, now)
    # News cooldown is 48h, fired 50h ago → should pass
    assert len(result) == 1


def test_signal_cooldown_price_move_24h():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=now - timedelta(hours=25))
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "price_move", "evidence": {"signal_id": signal_id, "current_price": 150}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map, now)
    # Price cooldown is 24h, fired 25h ago → should pass
    assert len(result) == 1


def test_signal_cooldown_price_move_within_window():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=now - timedelta(hours=20))
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "price_move", "evidence": {"signal_id": signal_id, "current_price": 150}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map, now)
    # Price cooldown is 24h, fired 20h ago → should be skipped
    assert len(result) == 0


def test_signal_cooldown_allows_no_signal_id():
    signal_map = {}
    candidates = [
        {"event_type": "price_move", "evidence": {"current_price": 150}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map)
    assert len(result) == 1


def test_signal_cooldown_allows_never_fired():
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=None)
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"signal_id": signal_id}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Rule 3: Priority suppression
# ---------------------------------------------------------------------------


def test_priority_suppression_drops_lower_severity_same_source():
    candidates = [
        {"event_type": "price_move", "evidence": {"article_id": "src-1"}, "_severity": "thesis_breaking"},
        {"event_type": "metric_threshold", "evidence": {"article_id": "src-1"}, "_severity": "warning"},
    ]
    result = _apply_priority_suppression(candidates)
    assert len(result) == 1
    assert result[0]["_severity"] == "thesis_breaking"


def test_priority_suppression_keeps_different_sources():
    candidates = [
        {"event_type": "price_move", "evidence": {"article_id": "src-1"}, "_severity": "thesis_breaking"},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "src-2"}, "_severity": "warning"},
    ]
    result = _apply_priority_suppression(candidates)
    assert len(result) == 2


def test_priority_suppression_no_breaking_keeps_all():
    candidates = [
        {"event_type": "price_move", "evidence": {"article_id": "src-1"}, "_severity": "warning"},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "src-1"}, "_severity": "info"},
    ]
    result = _apply_priority_suppression(candidates)
    assert len(result) == 2


def test_priority_suppression_no_source_id_kept():
    candidates = [
        {"event_type": "price_move", "evidence": {"current_price": 150}, "_severity": "thesis_breaking"},
        {"event_type": "metric_threshold", "evidence": {"metric": "pe"}, "_severity": "warning"},
    ]
    result = _apply_priority_suppression(candidates)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Rule 4: Minimum relevance
# ---------------------------------------------------------------------------


def test_minimum_relevance_drops_unlinked_news():
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"headline": "AAPL mentioned"}},
    ]
    result = _apply_minimum_relevance(candidates)
    assert len(result) == 0


def test_minimum_relevance_keeps_news_with_signal():
    signal_id = str(uuid.uuid4())
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"signal_id": signal_id, "headline": "AAPL"}},
    ]
    result = _apply_minimum_relevance(candidates)
    assert len(result) == 1


def test_minimum_relevance_keeps_news_with_claim():
    claim_id = str(uuid.uuid4())
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"claim_id": claim_id, "headline": "AAPL"}},
    ]
    result = _apply_minimum_relevance(candidates)
    assert len(result) == 1


def test_minimum_relevance_ignores_non_news():
    candidates = [
        {"event_type": "price_move", "evidence": {"current_price": 150}},
        {"event_type": "earnings_surprise", "evidence": {"recent_earnings_surprise_pct": 5.0}},
    ]
    result = _apply_minimum_relevance(candidates)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# record_signal_fired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_signal_fired_updates_last_fired_at():
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id)
    signal_map = {signal_id: signal}
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)

    await record_signal_fired(signal_id, signal_map, now=now)

    assert signal.last_fired_at == now


@pytest.mark.asyncio
async def test_record_signal_fired_noop_for_none():
    signal_map = {}
    await record_signal_fired(None, signal_map)


@pytest.mark.asyncio
async def test_record_signal_fired_noop_for_unknown_signal():
    signal_map = {}
    await record_signal_fired(str(uuid.uuid4()), signal_map)


# ---------------------------------------------------------------------------
# Integration: filter_candidates with DB (evidence dedup)
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch

from app.services.noise_filter import filter_candidates


@pytest.mark.asyncio
async def test_filter_candidates_combines_all_rules():
    """Integration: all 4 rules applied in sequence."""
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    holding_id = uuid.uuid4()
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=now - timedelta(hours=2))
    signal_map = {signal_id: signal}

    candidates = [
        # Rule 1: existing evidence → dropped
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "old-article", "claim_id": "c1"}},
        # Rule 2: signal on cooldown (news = 48h, fired 2h ago) → dropped
        {"event_type": "news_or_earnings_candidate", "evidence": {"signal_id": signal_id, "article_id": "new-art", "claim_id": "c1"}},
        # Rule 4: unlinked news → dropped
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "another-art", "headline": "stuff"}},
        # Survives all rules
        {"event_type": "price_move", "evidence": {"current_price": 150}},
    ]

    with patch("app.services.noise_filter._load_recent_evidence_ids", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"old-article"}
        db_mock = AsyncMock()
        result = await filter_candidates(candidates, holding_id, signal_map, db_mock, now=now)

    assert len(result) == 1
    assert result[0]["event_type"] == "price_move"
