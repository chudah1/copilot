import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.noise_filter import (
    _apply_evidence_dedup,
    _apply_minimum_relevance,
    _apply_signal_cooldown,
    _apply_sibling_specificity_suppression,
    _load_recent_evidence_keys,
    apply_priority_suppression,
    filter_candidates,
    record_signal_fired,
)
from app.models.monitoring_event import MonitoringEvent


def _make_signal(signal_id: str, last_fired_at: datetime | None = None) -> MagicMock:
    signal = MagicMock()
    signal.id = uuid.UUID(signal_id)
    signal.last_fired_at = last_fired_at
    signal.consecutive_ignores = 0
    return signal


# ---------------------------------------------------------------------------
# Rule 1: Evidence dedup (scoped by evidence_type + source_id)
# ---------------------------------------------------------------------------


def test_evidence_dedup_skips_existing_article():
    existing = {("news", "article-123")}
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "article-123", "headline": "Old news"}},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "article-456", "headline": "New news"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 1
    assert result[0]["evidence"]["article_id"] == "article-456"


def test_evidence_dedup_skips_existing_transaction():
    existing = {("insider", "txn-abc")}
    candidates = [
        {"event_type": "insider_transaction", "evidence": {"transaction_id": "txn-abc"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 0


def test_evidence_dedup_skips_existing_transcript():
    existing = {("earnings", "transcript:2026Q1")}
    candidates = [
        {"event_type": "earnings_call_transcript", "evidence": {"transcript_id": "transcript:2026Q1"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 0


def test_evidence_dedup_keeps_candidates_without_source_id():
    existing: set[tuple[str, str]] = set()
    candidates = [
        {"event_type": "price_move", "evidence": {"current_price": 150.0}},
        {"event_type": "metric_threshold", "evidence": {"metric": "pe_ratio"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 2


def test_evidence_dedup_deduplicates_within_batch():
    existing: set[tuple[str, str]] = set()
    candidates = [
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "same-article"}},
        {"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "same-article"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    assert len(result) == 1


def test_evidence_dedup_allows_same_source_different_evidence_type():
    """Same article_id but different evidence_type should NOT be deduped."""
    existing = {("news", "shared-id")}
    candidates = [
        {"event_type": "earnings_call_transcript", "evidence": {"article_id": "shared-id"}},
    ]
    result = _apply_evidence_dedup(candidates, existing)
    # "earnings" != "news", so this should survive
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
    signal_map: dict = {}
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


def test_signal_cooldown_handles_naive_last_fired_at():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    signal_id = str(uuid.uuid4())
    signal = _make_signal(signal_id, last_fired_at=datetime(2026, 5, 16, 8, 0))
    signal_map = {signal_id: signal}

    candidates = [
        {"event_type": "price_move", "evidence": {"signal_id": signal_id, "current_price": 150}},
    ]
    result = _apply_signal_cooldown(candidates, signal_map, now)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Rule 3: Priority suppression (operates on classified tuples)
# ---------------------------------------------------------------------------


def test_priority_suppression_drops_lower_severity_same_source():
    classified = [
        ({"event_type": "price_move", "evidence": {"article_id": "src-1"}}, "thesis_breaking"),
        ({"event_type": "metric_threshold", "evidence": {"article_id": "src-1"}}, "warning"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 1
    assert result[0][1] == "thesis_breaking"


def test_priority_suppression_keeps_different_sources():
    classified = [
        ({"event_type": "price_move", "evidence": {"article_id": "src-1"}}, "thesis_breaking"),
        ({"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "src-2"}}, "warning"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 2


def test_priority_suppression_no_breaking_keeps_all():
    classified = [
        ({"event_type": "price_move", "evidence": {"article_id": "src-1"}}, "warning"),
        ({"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "src-1"}}, "info"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 2


def test_priority_suppression_no_source_id_kept():
    classified = [
        ({"event_type": "price_move", "evidence": {"current_price": 150}}, "thesis_breaking"),
        ({"event_type": "metric_threshold", "evidence": {"metric": "pe"}}, "warning"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 2


def test_sibling_specificity_prefers_transcript_over_upcoming_for_same_claim():
    claim_id = str(uuid.uuid4())
    classified = [
        ({"event_type": "upcoming_earnings", "evidence": {"claim_id": claim_id}}, "warning"),
        ({"event_type": "earnings_call_transcript", "evidence": {"claim_id": claim_id}}, "warning"),
    ]
    result = _apply_sibling_specificity_suppression(classified)
    assert len(result) == 1
    assert result[0][0]["event_type"] == "earnings_call_transcript"


def test_sibling_specificity_prefers_higher_severity_even_if_less_specific():
    claim_id = str(uuid.uuid4())
    classified = [
        ({"event_type": "earnings_call_transcript", "evidence": {"claim_id": claim_id}}, "warning"),
        ({"event_type": "news_or_earnings_candidate", "evidence": {"claim_id": claim_id}}, "thesis_breaking"),
    ]
    result = _apply_sibling_specificity_suppression(classified)
    assert len(result) == 1
    assert result[0][0]["event_type"] == "news_or_earnings_candidate"
    assert result[0][1] == "thesis_breaking"


def test_sibling_specificity_keeps_different_families():
    claim_id = str(uuid.uuid4())
    classified = [
        ({"event_type": "earnings_call_transcript", "evidence": {"claim_id": claim_id}}, "warning"),
        ({"event_type": "insider_transaction", "evidence": {"claim_id": claim_id}}, "warning"),
    ]
    result = _apply_sibling_specificity_suppression(classified)
    assert len(result) == 2


def test_apply_priority_suppression_also_applies_sibling_specificity():
    claim_id = str(uuid.uuid4())
    classified = [
        ({"event_type": "upcoming_earnings", "evidence": {"claim_id": claim_id}}, "warning"),
        ({"event_type": "news_or_earnings_candidate", "evidence": {"claim_id": claim_id}}, "warning"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 1
    assert result[0][0]["event_type"] == "news_or_earnings_candidate"


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
    signal_map: dict = {}
    await record_signal_fired(None, signal_map)


@pytest.mark.asyncio
async def test_record_signal_fired_noop_for_unknown_signal():
    signal_map: dict = {}
    await record_signal_fired(str(uuid.uuid4()), signal_map)


# ---------------------------------------------------------------------------
# Integration: filter_candidates (rules 1, 2, 4) + priority suppression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_candidates_combines_rules_1_2_4():
    """Integration: rules 1, 2, 4 applied in filter_candidates."""
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

    with patch("app.services.noise_filter._load_recent_evidence_keys", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {("news", "old-article")}
        db_mock = AsyncMock()
        result = await filter_candidates(candidates, holding_id, signal_map, db_mock, now=now)

    assert len(result) == 1
    assert result[0]["event_type"] == "price_move"


@pytest.mark.asyncio
async def test_load_recent_evidence_keys_handles_legacy_events_without_evidence_type(db):
    holding_id = uuid.uuid4()
    article_id = "legacy-article"
    db.add(
        MonitoringEvent(
            id=uuid.uuid4(),
            holding_id=holding_id,
            thesis_id=uuid.uuid4(),
            event_type="news_or_earnings_candidate",
            evidence_type=None,
            severity="warning",
            title="Legacy event",
            summary="Legacy summary",
            raw_data={
                "candidate_type": "news_or_earnings_candidate",
                "evidence": {"article_id": article_id},
            },
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    keys = await _load_recent_evidence_keys(db, holding_id)

    assert ("news", article_id) in keys


def test_priority_suppression_end_to_end():
    """Priority suppression drops warning when thesis_breaking exists for same source."""
    classified = [
        ({"event_type": "price_move", "evidence": {"article_id": "src-1"}, "description": "Price moved"}, "thesis_breaking"),
        ({"event_type": "news_or_earnings_candidate", "evidence": {"article_id": "src-1"}, "description": "News"}, "warning"),
        ({"event_type": "earnings_surprise", "evidence": {"article_id": "src-2"}, "description": "Earnings"}, "warning"),
    ]
    result = apply_priority_suppression(classified)
    assert len(result) == 2
    event_types = [c["event_type"] for c, _ in result]
    assert "price_move" in event_types
    assert "earnings_surprise" in event_types
    assert "news_or_earnings_candidate" not in event_types


# ---------------------------------------------------------------------------
# skip_cooldown flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_candidates_skip_cooldown_bypasses_rule2():
    """With skip_cooldown=True, candidates whose signal is in cooldown still survive."""
    signal_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    fired_recently = datetime.now(timezone.utc) - timedelta(hours=1)
    signal = _make_signal(signal_id, last_fired_at=fired_recently)
    signal_map = {signal_id: signal}

    candidate = {
        "event_type": "news",
        "description": "Test news",
        "evidence": {"signal_id": signal_id, "source_id": "abc123"},
    }

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    # With skip_cooldown: candidate survives despite signal being in cooldown
    result = await filter_candidates(
        [candidate], uuid.uuid4(), signal_map, db, skip_cooldown=True
    )
    assert len(result) == 1

    # Without skip_cooldown: same candidate is filtered by Rule 2
    filtered = await filter_candidates(
        [candidate], uuid.uuid4(), signal_map, db, skip_cooldown=False
    )
    assert len(filtered) == 0
