from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evidence_chunk import EvidenceChunk
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.services.evidence_chunking import _GENERIC_NEWS_MIN_RELEVANCE


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_type: str
    source_id: str | None
    chunk_type: str
    score: float
    chunk_text: str
    embedded_at: datetime | None
    created_at: datetime


@dataclass
class ClaimRetrievalResult:
    claim_id: uuid.UUID
    claim_text: str
    embedding_text: str | None
    hits: list[RetrievedChunk] = field(default_factory=list)


@dataclass
class ThesisRetrievalReport:
    thesis_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    claim_results: list[ClaimRetrievalResult] = field(default_factory=list)
    chunk_pool_size: int = 0
    no_decomposition: bool = False


def _chunk_is_retrieval_eligible(chunk: EvidenceChunk) -> bool:
    metadata = chunk.metadata_json or {}
    if chunk.source_type != "news_or_earnings_candidate":
        return True
    if not isinstance(metadata, dict):
        return False

    source = str(metadata.get("source") or "").strip().lower()
    relevance = str(metadata.get("relevance") or "").strip().lower()
    grounded = bool(metadata.get("is_grounded"))
    relevant_signals = metadata.get("relevant_signals")
    matched_signal_ids = metadata.get("matched_signal_ids")
    matched_topics = metadata.get("matched_topics")
    topic_context = str(metadata.get("topic_context") or "").strip()
    ticker_relevance = metadata.get("ticker_relevance")
    try:
        ticker_relevance_value = float(ticker_relevance) if ticker_relevance is not None else None
    except (TypeError, ValueError):
        ticker_relevance_value = None

    explicitly_bound = bool(isinstance(relevant_signals, list) and relevant_signals)
    semantically_bound = bool(isinstance(matched_signal_ids, list) and matched_signal_ids)
    topic_shaped = bool(isinstance(matched_topics, list) and matched_topics) or bool(topic_context)
    trusted_source = source == "gemini_search" or grounded
    strong_relevance = relevance == "high" or (
        ticker_relevance_value is not None and ticker_relevance_value >= _GENERIC_NEWS_MIN_RELEVANCE
    )
    return explicitly_bound or semantically_bound or topic_shaped or trusted_source or strong_relevance


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _load_confirmed_claims(
    db: AsyncSession,
    thesis_id: uuid.UUID,
) -> list[ThesisClaim]:
    result = await db.execute(
        select(ThesisDecomposition)
        .where(
            ThesisDecomposition.thesis_id == thesis_id,
            ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
        )
        .order_by(ThesisDecomposition.version.desc())
        .limit(1)
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
    )
    decomposition = result.scalar_one_or_none()
    if decomposition is None:
        return []
    return list(decomposition.claims)


async def retrieve_similar_chunks_for_thesis(
    db: AsyncSession,
    thesis_id: uuid.UUID,
    *,
    top_k_per_claim: int = 10,
    window_days: int = 30,
) -> ThesisRetrievalReport:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    claims = await _load_confirmed_claims(db, thesis_id)
    report = ThesisRetrievalReport(
        thesis_id=thesis_id,
        window_start=window_start,
        window_end=now,
        no_decomposition=not claims,
    )

    base_chunk_query = (
        select(EvidenceChunk)
        .where(
            EvidenceChunk.thesis_id == thesis_id,
            EvidenceChunk.created_at >= window_start,
        )
        .order_by(EvidenceChunk.created_at.desc())
    )
    chunk_result = await db.execute(base_chunk_query)
    chunks = [
        chunk
        for chunk in chunk_result.scalars().all()
        if chunk.embedding and _chunk_is_retrieval_eligible(chunk)
    ]
    report.chunk_pool_size = len(chunks)
    if not claims:
        return report
    use_postgres_vector = db.bind is not None and db.bind.dialect.name == "postgresql"

    for claim in claims:
        result = ClaimRetrievalResult(
            claim_id=claim.id,
            claim_text=claim.claim_text,
            embedding_text=claim.embedding_text,
        )
        if claim.embedding:
            if use_postgres_vector:
                distance_expr = EvidenceChunk.embedding.op("<=>")(claim.embedding)
                pg_result = await db.execute(
                    select(EvidenceChunk, distance_expr.label("distance"))
                    .where(
                        EvidenceChunk.thesis_id == thesis_id,
                        EvidenceChunk.created_at >= window_start,
                        EvidenceChunk.embedding.is_not(None),
                    )
                    .order_by(distance_expr.asc())
                    .limit(top_k_per_claim)
                )
                result.hits = [
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        source_type=chunk.source_type,
                        source_id=chunk.source_id,
                        chunk_type=chunk.chunk_type,
                        score=max(0.0, 1.0 - float(distance or 0.0)),
                        chunk_text=chunk.chunk_text,
                        embedded_at=chunk.embedded_at,
                        created_at=chunk.created_at,
                    )
                    for chunk, distance in pg_result.all()
                    if _chunk_is_retrieval_eligible(chunk)
                ]
            else:
                scored: list[RetrievedChunk] = []
                for chunk in chunks:
                    score = _cosine_similarity(claim.embedding, chunk.embedding or [])
                    if score <= 0:
                        continue
                    scored.append(
                        RetrievedChunk(
                            chunk_id=chunk.id,
                            source_type=chunk.source_type,
                            source_id=chunk.source_id,
                            chunk_type=chunk.chunk_type,
                            score=score,
                            chunk_text=chunk.chunk_text,
                            embedded_at=chunk.embedded_at,
                            created_at=chunk.created_at,
                        )
                    )
                scored.sort(key=lambda item: item.score, reverse=True)
                result.hits = scored[:top_k_per_claim]
        report.claim_results.append(result)

    return report
