"""Relevance instrumentation: measure whether monitoring fires sharp signal or noise.

Two layers, both built on data we already persist (no schema change):

1. Structured log lines at fire time and review time — a greppable real-time
   stream (`relevance_fired` / `relevance_reviewed`) you can tail or pipe while
   the first users are live.
2. compute_relevance_metrics — an aggregate read over a window: of the events
   users actually reviewed, what fraction did they mark "not relevant", broken
   down by event source so you can see *which* signal type is noisy.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_event import MonitoringEvent
from app.models.thesis_review import ThesisReview

logger = logging.getLogger("relevance")

# How a review verdict maps onto signal quality. "not_relevant" is the explicit
# noise marker; the "acted" set means the event actually moved the user's
# thinking. "ignored" is a soft dismissal — counted on its own, not as noise.
ACTION_NOISE = {"not_relevant"}
ACTION_ACTED = {"reaffirmed", "lowered_confidence", "invalidated"}
ACTION_SOFT = {"ignored"}


def _normalize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def log_event_fired(event: MonitoringEvent, *, ticker: str | None = None) -> None:
    """Emit one parseable line per fired event — captures everything, including
    events the user never reviews."""
    try:
        logger.info(
            "relevance_fired %s",
            json.dumps(
                {
                    "event_id": str(event.id),
                    "ticker": ticker,
                    "event_type": event.event_type,
                    "evidence_type": event.evidence_type,
                    "severity": event.severity,
                    "verdict": event.verdict,
                    "signal_linked": event.signal_id is not None,
                },
                default=str,
            ),
        )
    except Exception:  # logging must never break the pipeline
        logger.debug("relevance_fired log failed", exc_info=True)


def log_event_reviewed(
    event: MonitoringEvent,
    action: str,
    *,
    now: datetime | None = None,
) -> None:
    """Emit one parseable line per review — the human verdict on a fired event,
    plus how long it took them to get to it."""
    try:
        created = _normalize(event.created_at)
        review_at = _normalize(now) or datetime.now(timezone.utc)
        latency = (review_at - created).total_seconds() if created else None
        logger.info(
            "relevance_reviewed %s",
            json.dumps(
                {
                    "event_id": str(event.id),
                    "event_type": event.event_type,
                    "evidence_type": event.evidence_type,
                    "severity": event.severity,
                    "action": action,
                    "is_noise": action in ACTION_NOISE,
                    "latency_seconds": round(latency) if latency is not None else None,
                },
                default=str,
            ),
        )
    except Exception:
        logger.debug("relevance_reviewed log failed", exc_info=True)


@dataclass
class DimensionBreakdown:
    key: str
    fired: int = 0
    reviewed: int = 0
    not_relevant: int = 0
    acted: int = 0

    @property
    def noise_rate(self) -> float | None:
        return round(self.not_relevant / self.reviewed, 3) if self.reviewed else None


@dataclass
class RelevanceMetrics:
    window_days: int
    fired_total: int = 0
    reviewed_total: int = 0
    not_relevant: int = 0
    ignored: int = 0
    acted: int = 0
    by_event_type: list[dict] = field(default_factory=list)
    by_evidence_type: list[dict] = field(default_factory=list)
    by_severity: list[dict] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def review_rate(self) -> float | None:
        return round(self.reviewed_total / self.fired_total, 3) if self.fired_total else None

    @property
    def noise_rate(self) -> float | None:
        """Headline metric: of reviewed events, fraction marked not relevant."""
        return round(self.not_relevant / self.reviewed_total, 3) if self.reviewed_total else None

    @property
    def acted_rate(self) -> float | None:
        return round(self.acted / self.reviewed_total, 3) if self.reviewed_total else None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["review_rate"] = self.review_rate
        d["noise_rate"] = self.noise_rate
        d["acted_rate"] = self.acted_rate
        d["generated_at"] = self.generated_at.isoformat()
        return d


def _bump(table: dict[str, DimensionBreakdown], key: str | None) -> DimensionBreakdown:
    k = key or "unknown"
    if k not in table:
        table[k] = DimensionBreakdown(key=k)
    return table[k]


async def compute_relevance_metrics(
    db: AsyncSession,
    *,
    days: int = 14,
    now: datetime | None = None,
) -> RelevanceMetrics:
    """Aggregate fired events and their latest review verdict over the window.

    Global across all users — this is the founder's read on whether the product
    fires sharp signal. The latest review per event wins, so re-reviews don't
    double-count.
    """
    now = _normalize(now) or datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    events = list(
        (
            await db.execute(
                select(
                    MonitoringEvent.id,
                    MonitoringEvent.event_type,
                    MonitoringEvent.evidence_type,
                    MonitoringEvent.severity,
                )
                .where(MonitoringEvent.created_at >= since)
            )
        ).all()
    )
    event_ids = [row[0] for row in events]

    # Latest review action per event in the window.
    latest_action: dict = {}
    if event_ids:
        review_rows = (
            await db.execute(
                select(
                    ThesisReview.monitoring_event_id,
                    ThesisReview.action,
                    ThesisReview.created_at,
                )
                .where(ThesisReview.monitoring_event_id.in_(event_ids))
                .order_by(ThesisReview.created_at.asc())
            )
        ).all()
        for event_id, action, _created in review_rows:
            latest_action[event_id] = action  # asc order => last write wins

    metrics = RelevanceMetrics(window_days=days, generated_at=now)
    by_type: dict[str, DimensionBreakdown] = {}
    by_evidence: dict[str, DimensionBreakdown] = {}
    by_severity: dict[str, DimensionBreakdown] = {}

    for event_id, event_type, evidence_type, severity in events:
        metrics.fired_total += 1
        dims = [
            _bump(by_type, event_type),
            _bump(by_evidence, evidence_type),
            _bump(by_severity, severity),
        ]
        for d in dims:
            d.fired += 1

        action = latest_action.get(event_id)
        if action is None:
            continue

        metrics.reviewed_total += 1
        is_noise = action in ACTION_NOISE
        is_acted = action in ACTION_ACTED
        if is_noise:
            metrics.not_relevant += 1
        elif action in ACTION_SOFT:
            metrics.ignored += 1
        if is_acted:
            metrics.acted += 1

        for d in dims:
            d.reviewed += 1
            if is_noise:
                d.not_relevant += 1
            if is_acted:
                d.acted += 1

    def _sorted(table: dict[str, DimensionBreakdown]) -> list[dict]:
        rows = []
        for d in table.values():
            row = asdict(d)
            row["noise_rate"] = d.noise_rate
            rows.append(row)
        # Noisiest (then most-fired) first so the worst offenders surface on top.
        return sorted(rows, key=lambda r: (-(r["noise_rate"] or 0), -r["fired"]))

    metrics.by_event_type = _sorted(by_type)
    metrics.by_evidence_type = _sorted(by_evidence)
    metrics.by_severity = _sorted(by_severity)
    return metrics
