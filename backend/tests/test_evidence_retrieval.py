import uuid

import pytest

from app.models.evidence_chunk import EvidenceChunk
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.auth import hash_password
from app.services.evidence_retrieval import retrieve_similar_chunks_for_thesis


async def _setup_retrieval_fixture(db, *, user: User | None = None):
    if user is None:
        user = User(
            email=f"retrieval{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
        )
        db.add(user)
        await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="ORCL",
        name="Oracle",
        quantity=3,
        average_cost_basis=100,
        current_price=150,
        current_value=450,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="OCI demand and backlog remain strong.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=1,
        status="confirmed",
        monitorability="medium",
    )
    db.add(decomposition)
    await db.flush()

    claim = ThesisClaim(
        decomposition_id=decomposition.id,
        claim_text="OCI backlog and signed demand remain strong",
        claim_type="growth",
        position=1,
        embedding_text="OCI backlog and signed demand remain strong",
        embedding=[1.0, 0.0],
    )
    db.add(claim)
    await db.flush()

    entity = ThesisEntity(
        claim_id=claim.id,
        entity_name="Oracle",
        entity_ticker="ORCL",
        entity_type="held_company",
        user_confirmed=True,
    )
    db.add(entity)
    await db.flush()

    signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="news_topic",
        signal_label="ORCL backlog commentary",
        signal_config_json={"topic": "ORCL backlog commentary"},
        confidence=0.9,
        confirmation_required=False,
        user_confirmed=True,
        active=True,
    )
    db.add(signal)
    await db.flush()

    db.add_all(
        [
            EvidenceChunk(
                thesis_id=thesis.id,
                holding_id=holding.id,
                ticker=holding.ticker,
                source_type="edgar_8k",
                source_id="8k-1",
                chunk_type="edgar_item_summary",
                chunk_index=0,
                chunk_text="Oracle said backlog and signed demand continue to grow.",
                embedding=[0.9, 0.1],
            ),
            EvidenceChunk(
                thesis_id=thesis.id,
                holding_id=holding.id,
                ticker=holding.ticker,
                source_type="gemini_news",
                source_id="news-1",
                chunk_type="news_summary",
                chunk_index=0,
                chunk_text="A generic AI market roundup.",
                embedding=[0.1, 0.9],
            ),
        ]
    )
    await db.commit()
    return thesis, claim, signal


@pytest.mark.asyncio
async def test_retrieve_similar_chunks_orders_by_score(db):
    thesis, claim, _signal = await _setup_retrieval_fixture(db)

    report = await retrieve_similar_chunks_for_thesis(db, thesis.id, top_k_per_claim=5, window_days=30)

    assert report.no_decomposition is False
    assert report.chunk_pool_size == 2
    assert len(report.claim_results) == 1
    result = report.claim_results[0]
    assert result.claim_id == claim.id
    assert len(result.hits) == 2
    assert result.hits[0].source_id == "8k-1"
    assert result.hits[0].score > result.hits[1].score


@pytest.mark.asyncio
async def test_retrieval_endpoint_returns_shadow_hits(client, auth_headers, db, test_user):
    thesis, _claim, _signal = await _setup_retrieval_fixture(db, user=test_user)

    response = await client.get(
        f"/api/monitoring/theses/{thesis.id}/coverage/retrieval",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["thesis_id"] == str(thesis.id)
    assert data["chunk_pool_size"] == 2
    assert len(data["claim_results"]) == 1
    assert data["claim_results"][0]["hits"][0]["source_id"] == "8k-1"


@pytest.mark.asyncio
async def test_retrieval_compare_endpoint_merges_coverage_and_hits(client, auth_headers, db, test_user):
    thesis, claim, signal = await _setup_retrieval_fixture(db, user=test_user)
    db.add(
        MonitoringEvent(
            holding_id=thesis.holding_id,
            thesis_id=thesis.id,
            event_type="news_or_earnings_candidate",
            severity="warning",
            title="Oracle backlog signal",
            summary="Backlog remains strong.",
            raw_data={
                "evidence": {
                    "matched_signal_ids": [str(signal.id)],
                }
            },
            claim_id=claim.id,
            signal_id=signal.id,
            evidence_type="news",
            evidence_summary="Backlog remains strong.",
            verdict="supports",
        )
    )
    await db.commit()

    response = await client.get(
        f"/api/monitoring/theses/{thesis.id}/coverage/retrieval/compare",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["chunk_pool_size"] == 2
    assert data["claim_results"][0]["retrieval_hit_count"] == 2
    assert data["claim_results"][0]["matched_event_count"] == 1
