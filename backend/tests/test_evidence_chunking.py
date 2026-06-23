import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.evidence_chunk import EvidenceChunk
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password
from app.services.evidence_chunking import (
    build_candidate_chunks,
    persist_candidate_evidence_chunks,
)


async def _setup_thesis_and_holding(db):
    user = User(
        email=f"chunk{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=2,
        average_cost_basis=100,
        current_price=150,
        current_value=300,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI demand remains strong.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.commit()
    return thesis, holding


def test_build_candidate_chunks_from_transcript():
    candidate = {
        "event_type": "earnings_call_transcript",
        "evidence": {
            "transcript_id": "transcript:Q1",
            "full_transcript": (
                "Demand remains very strong across hyperscalers. "
                "Management said Blackwell supply is improving this quarter. "
                "Customers are ramping deployments faster than expected."
            ),
        },
    }

    chunks = build_candidate_chunks(candidate)

    assert chunks
    assert chunks[0][0] == "transcript_window"
    assert any("Blackwell supply is improving" in chunk_text for _chunk_type, chunk_text in chunks)


@pytest.mark.asyncio
async def test_persist_candidate_evidence_chunks_dedupes_by_source_and_index(db):
    thesis, holding = await _setup_thesis_and_holding(db)
    candidate = {
        "event_type": "edgar_8k",
        "description": "SEC 8-K filed by NVDA: earnings release",
        "evidence": {
            "edgar_accession": "0001-0001",
            "description": "earnings release",
            "extracted": {
                "key_quote": "Demand exceeded supply in the quarter.",
                "verdict_rationale": "Demand commentary was stronger than expected.",
            },
        },
    }

    with patch(
        "app.services.evidence_chunking.embed_text_map",
        new=AsyncMock(
            return_value={
                "Demand exceeded supply in the quarter.": [0.1, 0.2],
                "Demand commentary was stronger than expected.": [0.3, 0.4],
            }
        ),
    ) as mock_embed:
        inserted = await persist_candidate_evidence_chunks(
            db,
            thesis=thesis,
            holding=holding,
            candidates=[candidate],
        )
        await db.commit()

    assert inserted == 2
    mock_embed.assert_awaited_once()

    rows = (
        await db.execute(
            select(EvidenceChunk).where(
                EvidenceChunk.thesis_id == thesis.id,
                EvidenceChunk.holding_id == holding.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 2
    assert all(row.embedding is not None for row in rows)

    inserted_again = await persist_candidate_evidence_chunks(
        db,
        thesis=thesis,
        holding=holding,
        candidates=[candidate],
    )
    await db.commit()

    assert inserted_again == 0
    rows_after = (
        await db.execute(
            select(EvidenceChunk).where(
                EvidenceChunk.thesis_id == thesis.id,
                EvidenceChunk.holding_id == holding.id,
            )
        )
    ).scalars().all()
    assert len(rows_after) == 2
