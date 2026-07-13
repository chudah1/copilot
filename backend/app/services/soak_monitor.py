from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage_pass import CoveragePass
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.monitoring_soak_report import MonitoringSoakReport
from app.models.thesis import Thesis
from app.services.coverage import (
    STAGE_AFTER_CLASSIFICATION,
    STAGE_AFTER_NOISE_FILTER,
    STAGE_AFTER_SAME_EVENT_MERGE,
    STAGE_CANDIDATES_GENERATED,
    STAGE_EVENTS_PERSISTED,
)

DEFAULT_SOAK_CONFIG_PATH = Path(__file__).resolve().parents[2] / "docs" / "monitoring_soak.json"


@dataclass(frozen=True)
class SoakBasketEntry:
    label: str
    ticker: str | None = None
    holding_id: uuid.UUID | None = None


@dataclass(frozen=True)
class SoakRecentEvent:
    created_at: datetime
    severity: str
    event_type: str
    title: str


@dataclass(frozen=True)
class SoakHoldingSummary:
    label: str
    holding_id: uuid.UUID
    ticker: str
    holding_name: str
    thesis_id: uuid.UUID | None
    thesis_status: str | None
    latest_triggered_by: str | None
    latest_pass_started_at: datetime | None
    latest_stage_counts: dict[str, int]
    latest_events_persisted: int
    pass_count: int
    total_events_persisted: int
    total_same_event_merges: int
    source_error_count: int
    partial_failure_count: int
    recent_event_count: int
    recent_events: list[SoakRecentEvent]
    assessment: str
    assessment_reason: str


@dataclass(frozen=True)
class SoakUnresolvedEntry:
    label: str
    reason: str


@dataclass(frozen=True)
class SoakReport:
    start_at: datetime
    end_at: datetime
    timezone_name: str
    summaries: list[SoakHoldingSummary]
    unresolved: list[SoakUnresolvedEntry]


def soak_basket_payload(entries: list[SoakBasketEntry]) -> dict:
    return {
        "holdings": [
            {
                "label": entry.label,
                "ticker": entry.ticker,
                "holding_id": str(entry.holding_id) if entry.holding_id is not None else None,
            }
            for entry in entries
        ]
    }


def load_soak_basket_config(path: str | Path) -> list[SoakBasketEntry]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    holdings = raw.get("holdings")
    if not isinstance(holdings, list):
        raise ValueError("soak basket config must contain a 'holdings' list")

    entries: list[SoakBasketEntry] = []
    for idx, item in enumerate(holdings):
        if not isinstance(item, dict):
            raise ValueError(f"holding entry {idx} must be an object")
        ticker_raw = str(item.get("ticker") or "").strip().upper() or None
        holding_id_raw = str(item.get("holding_id") or "").strip() or None
        label = str(item.get("label") or ticker_raw or holding_id_raw or f"holding-{idx + 1}").strip()
        if not ticker_raw and not holding_id_raw:
            raise ValueError(f"holding entry {idx} must include ticker or holding_id")
        holding_id = uuid.UUID(holding_id_raw) if holding_id_raw else None
        entries.append(SoakBasketEntry(label=label, ticker=ticker_raw, holding_id=holding_id))
    return entries


def load_default_soak_basket() -> list[SoakBasketEntry]:
    return load_soak_basket_config(DEFAULT_SOAK_CONFIG_PATH)


def soak_window_for_days(*, days: int, timezone_name: str, today: date | None = None) -> tuple[datetime, datetime]:
    if days <= 0:
        raise ValueError("days must be positive")
    zone = ZoneInfo(timezone_name)
    anchor_day = today or datetime.now(zone).date()
    end_at = datetime.combine(anchor_day + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    start_at = end_at - timedelta(days=days)
    return start_at, end_at


def _stage_count_map(payload: dict) -> dict[str, int]:
    stages = payload.get("stages")
    counts: dict[str, int] = {}
    if not isinstance(stages, list):
        return counts
    for item in stages:
        if not isinstance(item, list | tuple) or len(item) != 2:
            continue
        stage_name = str(item[0])
        try:
            counts[stage_name] = int(item[1])
        except (TypeError, ValueError):
            continue
    return counts


def _same_event_merges_for_pass(payload: dict) -> int:
    counts = _stage_count_map(payload)
    before = counts.get(STAGE_AFTER_CLASSIFICATION)
    after = counts.get(STAGE_AFTER_SAME_EVENT_MERGE)
    if before is None or after is None:
        return 0
    return max(before - after, 0)


def _source_error_count(payload: dict) -> int:
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        return 0
    count = 0
    for entry in sources.values():
        if isinstance(entry, dict) and entry.get("error"):
            count += 1
    return count


def _pick_relevant_thesis(theses: list[Thesis]) -> Thesis | None:
    if not theses:
        return None
    active = [thesis for thesis in theses if thesis.invalidated_at is None and thesis.status in {"active", "ready"}]
    if active:
        active.sort(key=lambda thesis: thesis.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return active[0]
    theses.sort(key=lambda thesis: thesis.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return theses[0]


def _assessment_for_summary(summary: SoakHoldingSummary) -> tuple[str, str]:
    if summary.partial_failure_count > 0:
        return ("failing", f"{summary.partial_failure_count} pass(es) recorded a pipeline error.")
    if summary.pass_count == 0:
        return ("unmonitored", "No coverage passes were recorded in the selected window.")
    if summary.latest_events_persisted >= 5:
        return ("noisy", f"Latest pass persisted {summary.latest_events_persisted} events.")
    if summary.total_same_event_merges == 0 and summary.total_events_persisted >= 8:
        return ("review", "High event volume with no same-event merges suggests duplicate leakage.")
    if summary.total_events_persisted == 0:
        return ("quiet", "Window was quiet and no pass-level failures were recorded.")
    return ("healthy", "Pass volume and persisted events look within the current soak band.")


async def build_soak_report(
    db: AsyncSession,
    *,
    basket: list[SoakBasketEntry],
    start_at: datetime,
    end_at: datetime,
    timezone_name: str,
    recent_event_limit: int = 5,
) -> SoakReport:
    holding_rows = await db.execute(select(Holding))
    all_holdings = list(holding_rows.scalars().all())

    thesis_rows = await db.execute(select(Thesis))
    all_theses = list(thesis_rows.scalars().all())
    theses_by_holding: dict[uuid.UUID, list[Thesis]] = {}
    for thesis in all_theses:
        theses_by_holding.setdefault(thesis.holding_id, []).append(thesis)

    resolved: list[tuple[SoakBasketEntry, Holding, Thesis | None]] = []
    unresolved: list[SoakUnresolvedEntry] = []

    for entry in basket:
        if entry.holding_id is not None:
            matched = [holding for holding in all_holdings if holding.id == entry.holding_id]
        else:
            matched = [holding for holding in all_holdings if holding.ticker.upper() == (entry.ticker or "").upper()]
        if not matched:
            unresolved.append(SoakUnresolvedEntry(label=entry.label, reason="No holding matched this basket entry."))
            continue
        if len(matched) > 1:
            unresolved.append(
                SoakUnresolvedEntry(
                    label=entry.label,
                    reason="Ticker matched multiple holdings; use holding_id to disambiguate.",
                )
            )
            continue
        holding = matched[0]
        thesis = _pick_relevant_thesis(theses_by_holding.get(holding.id, []))
        resolved.append((entry, holding, thesis))

    thesis_ids = [thesis.id for _entry, _holding, thesis in resolved if thesis is not None]
    holding_ids = [holding.id for _entry, holding, _thesis in resolved]

    coverage_by_thesis: dict[uuid.UUID, list[CoveragePass]] = {}
    if thesis_ids:
        coverage_rows = await db.execute(
            select(CoveragePass)
            .where(
                CoveragePass.thesis_id.in_(thesis_ids),
                CoveragePass.started_at >= start_at,
                CoveragePass.started_at < end_at,
            )
            .order_by(CoveragePass.started_at.desc())
        )
        for row in coverage_rows.scalars().all():
            coverage_by_thesis.setdefault(row.thesis_id, []).append(row)

    events_by_holding: dict[uuid.UUID, list[SoakRecentEvent]] = {}
    if holding_ids:
        event_rows = await db.execute(
            select(
                MonitoringEvent.holding_id,
                MonitoringEvent.created_at,
                MonitoringEvent.severity,
                MonitoringEvent.event_type,
                MonitoringEvent.title,
            )
            .where(
                MonitoringEvent.holding_id.in_(holding_ids),
                MonitoringEvent.created_at >= start_at,
                MonitoringEvent.created_at < end_at,
            )
            .order_by(MonitoringEvent.created_at.desc())
        )
        for holding_id, created_at, severity, event_type, title in event_rows.all():
            events_by_holding.setdefault(holding_id, []).append(
                SoakRecentEvent(
                    created_at=created_at,
                    severity=severity,
                    event_type=event_type,
                    title=title,
                )
            )

    summaries: list[SoakHoldingSummary] = []
    for entry, holding, thesis in resolved:
        passes = coverage_by_thesis.get(thesis.id, []) if thesis is not None else []
        latest_pass = passes[0] if passes else None
        latest_payload = latest_pass.payload if latest_pass and isinstance(latest_pass.payload, dict) else {}
        latest_stage_counts = _stage_count_map(latest_payload)
        latest_events_persisted = int(latest_payload.get("events_persisted", 0) or 0)
        total_events_persisted = sum(int((coverage.payload or {}).get("events_persisted", 0) or 0) for coverage in passes)
        total_same_event_merges = sum(_same_event_merges_for_pass(coverage.payload or {}) for coverage in passes)
        source_error_count = sum(_source_error_count(coverage.payload or {}) for coverage in passes)
        partial_failure_count = sum(1 for coverage in passes if isinstance(coverage.payload, dict) and coverage.payload.get("error"))

        recent_events_raw = events_by_holding.get(holding.id, [])
        recent_events = recent_events_raw[:recent_event_limit]

        summary = SoakHoldingSummary(
            label=entry.label,
            holding_id=holding.id,
            ticker=holding.ticker,
            holding_name=holding.name,
            thesis_id=thesis.id if thesis is not None else None,
            thesis_status=thesis.status if thesis is not None else None,
            latest_triggered_by=latest_pass.triggered_by if latest_pass is not None else None,
            latest_pass_started_at=latest_pass.started_at if latest_pass is not None else None,
            latest_stage_counts=latest_stage_counts,
            latest_events_persisted=latest_events_persisted,
            pass_count=len(passes),
            total_events_persisted=total_events_persisted,
            total_same_event_merges=total_same_event_merges,
            source_error_count=source_error_count,
            partial_failure_count=partial_failure_count,
            recent_event_count=len(recent_events_raw),
            recent_events=recent_events,
            assessment="",
            assessment_reason="",
        )
        assessment, assessment_reason = _assessment_for_summary(summary)
        summaries.append(
            SoakHoldingSummary(
                **{**summary.__dict__, "assessment": assessment, "assessment_reason": assessment_reason}
            )
        )

    summaries.sort(key=lambda item: (item.assessment in {"failing", "noisy", "review"}, item.total_events_persisted, item.label), reverse=True)
    return SoakReport(
        start_at=start_at,
        end_at=end_at,
        timezone_name=timezone_name,
        summaries=summaries,
        unresolved=unresolved,
    )


def render_soak_report_markdown(report: SoakReport) -> str:
    zone = ZoneInfo(report.timezone_name)

    def fmt_dt(value: datetime | None) -> str:
        if value is None:
            return "n/a"
        return value.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")

    def stage_funnel(stage_counts: dict[str, int], events_persisted: int) -> str:
        if not stage_counts:
            return "n/a"
        values = [
            stage_counts.get(STAGE_CANDIDATES_GENERATED),
            stage_counts.get(STAGE_AFTER_NOISE_FILTER),
            stage_counts.get(STAGE_AFTER_CLASSIFICATION),
            stage_counts.get(STAGE_AFTER_SAME_EVENT_MERGE),
            stage_counts.get(STAGE_EVENTS_PERSISTED, events_persisted),
        ]
        compact = [str(value) for value in values if value is not None]
        return " -> ".join(compact) if compact else "n/a"

    lines = [
        "# Monitoring Soak Report",
        "",
        f"Window: {fmt_dt(report.start_at)} to {fmt_dt(report.end_at)}",
        f"Timezone: {report.timezone_name}",
        "",
        "## Summary",
        "",
        "| Holding | Assessment | Passes | Persisted | Same-event merges | Source errors | Latest funnel | Last pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for summary in report.summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{summary.label} (`{summary.ticker}`)",
                    summary.assessment,
                    str(summary.pass_count),
                    str(summary.total_events_persisted),
                    str(summary.total_same_event_merges),
                    str(summary.source_error_count),
                    stage_funnel(summary.latest_stage_counts, summary.latest_events_persisted),
                    fmt_dt(summary.latest_pass_started_at),
                ]
            )
            + " |"
        )

    if report.unresolved:
        lines.extend(["", "## Unresolved Basket Entries", ""])
        for item in report.unresolved:
            lines.append(f"- `{item.label}`: {item.reason}")

    lines.extend(["", "## Holdings", ""])
    for summary in report.summaries:
        lines.extend(
            [
                f"### {summary.label} (`{summary.ticker}`)",
                f"- Assessment: `{summary.assessment}` — {summary.assessment_reason}",
                f"- Holding ID: `{summary.holding_id}`",
                f"- Thesis: `{summary.thesis_id}` ({summary.thesis_status or 'n/a'})",
                f"- Last pass: {fmt_dt(summary.latest_pass_started_at)} via `{summary.latest_triggered_by or 'n/a'}`",
                f"- Latest funnel: {stage_funnel(summary.latest_stage_counts, summary.latest_events_persisted)}",
                f"- Window totals: {summary.pass_count} pass(es), {summary.total_events_persisted} persisted event(s), {summary.total_same_event_merges} same-event merge(s), {summary.partial_failure_count} failing pass(es)",
                f"- Source errors in window: {summary.source_error_count}",
                f"- Recent events in window: {summary.recent_event_count}",
            ]
        )
        if summary.recent_events:
            lines.append("- Recent event samples:")
            for event in summary.recent_events:
                lines.append(
                    f"  - {fmt_dt(event.created_at)} [{event.severity}] `{event.event_type}` {event.title}"
                )
        else:
            lines.append("- Recent event samples: none")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def soak_report_payload(report: SoakReport) -> dict:
    return {
        "start_at": report.start_at.isoformat(),
        "end_at": report.end_at.isoformat(),
        "timezone_name": report.timezone_name,
        "markdown": render_soak_report_markdown(report),
        "summaries": [
            {
                **summary.__dict__,
                "holding_id": str(summary.holding_id),
                "thesis_id": str(summary.thesis_id) if summary.thesis_id is not None else None,
                "latest_pass_started_at": summary.latest_pass_started_at.isoformat() if summary.latest_pass_started_at else None,
                "recent_events": [
                    {
                        "created_at": event.created_at.isoformat(),
                        "severity": event.severity,
                        "event_type": event.event_type,
                        "title": event.title,
                    }
                    for event in summary.recent_events
                ],
            }
            for summary in report.summaries
        ],
        "unresolved": [item.__dict__ for item in report.unresolved],
    }


async def persist_soak_report(
    db: AsyncSession,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    window_start: datetime,
    window_end: datetime,
    timezone_name: str,
    basket: list[SoakBasketEntry],
    report: SoakReport | None,
    status: str,
    error_message: str | None = None,
) -> MonitoringSoakReport:
    row = MonitoringSoakReport(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        window_start=window_start,
        window_end=window_end,
        timezone_name=timezone_name,
        status=status,
        basket_config=soak_basket_payload(basket),
        payload=soak_report_payload(report) if report is not None else None,
        error_message=(error_message[:2000] if error_message else None),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def latest_soak_reports(
    db: AsyncSession,
    *,
    limit: int = 10,
) -> list[MonitoringSoakReport]:
    result = await db.execute(
        select(MonitoringSoakReport)
        .order_by(MonitoringSoakReport.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
