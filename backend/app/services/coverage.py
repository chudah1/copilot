"""Per-signal coverage diagnostics.

The first-class question this service answers:

    For each active signal on a thesis, was it touched by any monitoring event
    in the recent window? If not, why might that be?

It reads what's already there — active signals + persisted events with
matched_signal_ids — and turns it into a structured per-signal report.
Codex flagged this as the missing piece that turns "thin coverage" from a
feeling into a debugging system. We start with the on-the-fly query approach
(no new persistence) so we can ship value today and add trend tables later
when we know what trends matter.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.coverage_pass import CoveragePass
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal


# Default window: a typical user expects "did we hear about this signal
# recently?" not "did we ever hear about it." Seven days matches the digest
# cadence so coverage reflects the same window the user gets a summary for.
DEFAULT_COVERAGE_WINDOW_DAYS = 7

# Confidence floor for treating a binding as "explicit/strong." Below this
# the match was inferred by embeddings + LLM adjudicator; the signal is
# touched but the user should know we're guessing.
STRONG_BINDING_CONFIDENCE_FLOOR = 0.80


@dataclass
class SignalCoverage:
    signal_id: uuid.UUID
    signal_label: str | None
    signal_type: str | None
    claim_id: uuid.UUID
    claim_text: str
    matched_event_count: int = 0
    last_matched_at: datetime | None = None
    last_event_id: uuid.UUID | None = None
    last_event_severity: str | None = None
    # max confidence we saw on any matching event; absent for events bound
    # explicitly (Gemini label match, pre-bound) — that's high-confidence
    # implicit, so we render it as 1.0.
    max_confidence: float | None = None

    @property
    def covered(self) -> bool:
        return self.matched_event_count > 0

    @property
    def is_strong_binding(self) -> bool:
        return self.max_confidence is None or self.max_confidence >= STRONG_BINDING_CONFIDENCE_FLOOR


@dataclass
class ThesisCoverageReport:
    thesis_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    signals: list[SignalCoverage] = field(default_factory=list)
    inactive_signal_count: int = 0  # signals exist but were turned off by user
    no_decomposition: bool = False  # thesis has no confirmed decomposition

    @property
    def covered_count(self) -> int:
        return sum(1 for s in self.signals if s.covered)

    @property
    def uncovered_count(self) -> int:
        return sum(1 for s in self.signals if not s.covered)


async def _load_active_signals(
    db: AsyncSession, thesis_id: uuid.UUID
) -> tuple[list[tuple[ThesisClaim, ThesisSignal]], int, bool]:
    """Return (active claim-signal pairs, inactive count, no_decomposition flag)."""
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
    decomp = result.scalar_one_or_none()
    if decomp is None:
        return [], 0, True

    active: list[tuple[ThesisClaim, ThesisSignal]] = []
    inactive = 0
    for claim in decomp.claims:
        for entity in claim.entities:
            for signal in entity.signals:
                if signal.active:
                    active.append((claim, signal))
                else:
                    inactive += 1
    return active, inactive, False


def _evidence_for_event(event: MonitoringEvent) -> dict[str, Any]:
    raw = event.raw_data or {}
    if isinstance(raw, dict):
        ev = raw.get("evidence")
        if isinstance(ev, dict):
            return ev
    return {}


def _bound_signal_ids(event: MonitoringEvent) -> set[str]:
    """All signal ids this event touches — multi-binding list if present, else
    fall back to the primary signal_id."""
    evidence = _evidence_for_event(event)
    matched = evidence.get("matched_signal_ids")
    bound: set[str] = set()
    if isinstance(matched, list):
        for value in matched:
            try:
                bound.add(str(uuid.UUID(str(value))))
            except (ValueError, TypeError):
                continue
    if not bound and event.signal_id is not None:
        bound.add(str(event.signal_id))
    return bound


def _confidence_for_signal(event: MonitoringEvent, signal_id_str: str) -> float | None:
    evidence = _evidence_for_event(event)
    conf_map = evidence.get("match_confidence_by_signal")
    if not isinstance(conf_map, dict):
        return None
    value = conf_map.get(signal_id_str)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def compute_thesis_coverage(
    db: AsyncSession,
    thesis_id: uuid.UUID,
    *,
    window_days: int = DEFAULT_COVERAGE_WINDOW_DAYS,
    now: datetime | None = None,
) -> ThesisCoverageReport:
    """Build per-signal coverage for the thesis over the recent window.

    For each active signal: did any monitoring event in the window have it in
    matched_signal_ids (or its primary signal_id for older events)? If yes —
    record latest event, severity, max confidence. If no — record as
    uncovered (the launch-readiness signal Codex wanted instrumented).
    """
    reference_now = now or datetime.now(timezone.utc)
    window_start = reference_now - timedelta(days=window_days)

    active_pairs, inactive_count, no_decomp = await _load_active_signals(db, thesis_id)

    report = ThesisCoverageReport(
        thesis_id=thesis_id,
        window_start=window_start,
        window_end=reference_now,
        inactive_signal_count=inactive_count,
        no_decomposition=no_decomp,
    )
    if not active_pairs:
        return report

    coverages: dict[str, SignalCoverage] = {}
    for claim, signal in active_pairs:
        sid = str(signal.id)
        coverages[sid] = SignalCoverage(
            signal_id=signal.id,
            signal_label=signal.signal_label,
            signal_type=signal.signal_type,
            claim_id=claim.id,
            claim_text=claim.claim_text,
        )

    # Pull events in the window, newest first so the "last matched" is correct
    # on first hit per signal.
    event_result = await db.execute(
        select(MonitoringEvent)
        .where(
            MonitoringEvent.thesis_id == thesis_id,
            MonitoringEvent.created_at >= window_start,
        )
        .order_by(MonitoringEvent.created_at.desc())
    )
    events = event_result.scalars().all()
    for event in events:
        bound_ids = _bound_signal_ids(event)
        for sid in bound_ids:
            coverage = coverages.get(sid)
            if coverage is None:
                continue
            coverage.matched_event_count += 1
            if coverage.last_matched_at is None or event.created_at > coverage.last_matched_at:
                coverage.last_matched_at = event.created_at
                coverage.last_event_id = event.id
                coverage.last_event_severity = event.severity
            confidence = _confidence_for_signal(event, sid)
            if confidence is not None:
                if coverage.max_confidence is None or confidence > coverage.max_confidence:
                    coverage.max_confidence = confidence

    report.signals = list(coverages.values())
    return report


# Pipeline stage names — defined as constants so call sites match exactly and
# we can render diffs ("after_relevance_filter dropped 6") without grepping.
STAGE_CANDIDATES_GENERATED = "candidates_generated"
STAGE_AFTER_MATCH = "after_match"
STAGE_AFTER_EMBEDDING_ENRICH = "after_embedding_enrich"
STAGE_AFTER_LLM_ADJUDICATION = "after_llm_adjudication"
STAGE_AFTER_RELEVANCE_FILTER = "after_relevance_filter"
STAGE_AFTER_THESIS_FLOOR = "after_thesis_floor"
STAGE_AFTER_NOISE_FILTER = "after_noise_filter"
STAGE_AFTER_CLASSIFICATION = "after_classification"
STAGE_AFTER_SAME_EVENT_MERGE = "after_same_event_merge"
STAGE_EVENTS_PERSISTED = "events_persisted"


@dataclass
class CoveragePassBuilder:
    """Collects source query results and stage counts during a single pipeline
    pass, persists once at the end. Designed to be cheap on the hot path —
    record_source / record_stage are O(1) dict / list inserts."""

    thesis_id: uuid.UUID
    holding_id: uuid.UUID
    run_id: str
    triggered_by: str  # "check_now" | "monitoring_run" | "edgar_watch" | "historical_audit"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_counts: list[tuple[str, int]] = field(default_factory=list)
    events_persisted: int = 0
    # News-style candidates the LLM relevance filter reviewed and ruled out,
    # with the sentence it wrote to explain the drop. The digest and the
    # position page render a curated sample as "we looked at these and
    # decided they didn't touch your thesis" — quiet products only feel
    # informed if the reviewed-but-dropped items are visible.
    reviewed_but_dropped: list[dict[str, Any]] = field(default_factory=list)

    def record_source(
        self,
        name: str,
        *,
        queried: bool = True,
        candidates_returned: int | None = None,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {"queried": queried}
        if candidates_returned is not None:
            entry["candidates_returned"] = candidates_returned
        if error:
            entry["error"] = str(error)[:500]
        if details:
            entry["details"] = details
        # Multiple calls for the same source name (e.g. EDGAR queried twice
        # over the pass) are merged by keeping the worst error and summing
        # candidates so the funnel matches reality.
        existing = self.sources.get(name)
        if existing is None:
            self.sources[name] = entry
            return
        merged = dict(existing)
        merged["queried"] = bool(existing.get("queried") or queried)
        if "candidates_returned" in entry or "candidates_returned" in existing:
            merged["candidates_returned"] = int(existing.get("candidates_returned", 0)) + int(entry.get("candidates_returned", 0))
        if "error" in entry:
            merged["error"] = entry["error"]
        if "details" in entry:
            merged_details = dict(existing.get("details") or {})
            merged_details.update(entry["details"])
            merged["details"] = merged_details
        self.sources[name] = merged

    def record_stage(self, stage: str, count: int) -> None:
        self.stage_counts.append((stage, int(count)))

    def record_events_persisted(self, count: int) -> None:
        self.events_persisted = int(count)

    def record_reviewed_but_dropped(self, drops: list[Any]) -> None:
        """Store the DroppedCandidate dataclasses (or dicts) from the
        thesis-relevance filter into the pass payload. Cap at 20 per pass —
        the digest only ever samples 2-3 and we don't need the payload to
        blow up on a noisy news day."""
        if not drops:
            return
        remaining = max(0, 20 - len(self.reviewed_but_dropped))
        if remaining == 0:
            return
        for drop in drops[:remaining]:
            if hasattr(drop, "__dict__"):
                entry = dict(drop.__dict__)
            elif isinstance(drop, dict):
                entry = dict(drop)
            else:
                continue
            self.reviewed_but_dropped.append(entry)

    async def persist(self, db: AsyncSession, *, error: str | None = None) -> None:
        finished_at = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sources": self.sources,
            "stages": [[name, count] for name, count in self.stage_counts],
            "events_persisted": self.events_persisted,
            "reviewed_but_dropped": self.reviewed_but_dropped,
        }
        if error:
            # Truncated so a runaway traceback can't bloat the coverage row.
            payload["error"] = error[:500]
        row = CoveragePass(
            thesis_id=self.thesis_id,
            holding_id=self.holding_id,
            run_id=self.run_id,
            triggered_by=self.triggered_by,
            started_at=self.started_at,
            finished_at=finished_at,
            payload=payload,
        )
        db.add(row)


async def latest_coverage_passes(
    db: AsyncSession, thesis_id: uuid.UUID, *, limit: int = 10
) -> list[CoveragePass]:
    """Return the most recent coverage passes for the thesis, newest first.
    Limit defaults to 10 — enough to see a few daily runs + the user's manual
    re-checks without flooding the UI."""
    result = await db.execute(
        select(CoveragePass)
        .where(CoveragePass.thesis_id == thesis_id)
        .order_by(CoveragePass.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
