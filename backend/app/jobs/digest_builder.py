import logging
import uuid
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select

from app.database import async_session
from app.models.digest import Digest
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.email import send_digest_email

logger = logging.getLogger(__name__)


def _age_in_days(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - normalized).days


def _digest_headline(events_count: int, stale_count: int, missing_count: int, stable_count: int) -> str:
    if events_count > 0:
        verb = "needs" if events_count == 1 else "need"
        return f"{events_count} of your reasons {verb} review this week."
    if stale_count > 0:
        return f"{stale_count} thesis{'es' if stale_count != 1 else ''} went stale this week."
    if missing_count > 0:
        return f"{missing_count} holding{'s' if missing_count != 1 else ''} still lack a thesis."
    if stable_count > 0:
        return f"{stable_count} of your reasons held up this week."
    return "No material portfolio changes this week."


def _digest_subject(events_count: int, stable_count: int) -> str:
    if events_count > 0:
        verb = "needs" if events_count == 1 else "need"
        return f"{events_count} of your reasons {verb} review this week"
    if stable_count > 0:
        return f"{stable_count} of your reasons held up this week"
    return "0 of your reasons changed this week"


def _digest_summary_points(events_data: list[dict], observations: dict) -> list[str]:
    points: list[str] = []
    if events_data:
        first = events_data[0]
        points.append(f"{first['ticker']}: {first['summary']}")
    if observations.get("stale_theses"):
        points.append(f"Stale theses: {', '.join(observations['stale_theses'][:3])}")
    if observations.get("missing_theses"):
        points.append(f"Missing theses: {', '.join(observations['missing_theses'][:3])}")
    if observations.get("concentration_warnings"):
        points.append(f"Concentration: {observations['concentration_warnings']}")
    stable = observations.get("stable_holdings", [])
    if stable and not points:
        points.append(f"Stable holdings: {', '.join(item['ticker'] for item in stable[:3])}")
    return points[:3]


def _event_rank(event: dict) -> tuple[int, int]:
    verdict_rank = {
        "threatens": 0,
        "review": 1,
        "supports": 2,
        "neutral": 3,
        None: 4,
    }
    severity_rank = {
        "thesis_breaking": 0,
        "warning": 1,
        "info": 2,
    }
    return (
        verdict_rank.get(event.get("verdict"), 4),
        severity_rank.get(event.get("severity"), 3),
    )


def _signal_status_text(intact_count: int, weakening_count: int) -> str:
    if intact_count == 0 and weakening_count == 0:
        return ""
    if weakening_count == 0:
        return f"All {intact_count} intact" if intact_count > 1 else "Signal intact"
    return f"{weakening_count} weakening, {intact_count} intact"


def _tldr_lines(events_data: list[dict]) -> list[str]:
    lines = []
    for event in events_data[:3]:
        ticker = event["ticker"]
        verdict = event.get("verdict")
        summary = event.get("evidence_summary") or event.get("summary", "")
        if verdict == "threatens":
            lines.append(f"{ticker}: {summary} Worth reviewing against your reason.")
        elif verdict == "supports":
            lines.append(f"{ticker}: {summary} Aligns with your reason for holding.")
        else:
            lines.append(f"{ticker}: {summary}")
    return lines


def _monitoring_receipt(
    holdings_count: int,
    events_count: int,
    stable_count: int,
    upcoming_earnings_count: int = 0,
) -> str:
    base = (
        f"We checked {holdings_count} holding{'s' if holdings_count != 1 else ''} with current reasons. "
        f"{events_count} produced material evidence. {stable_count} stayed calm."
    )
    if upcoming_earnings_count > 0:
        noun = "holding" if upcoming_earnings_count == 1 else "holdings"
        verb = "reports" if upcoming_earnings_count == 1 else "report"
        base += f" {upcoming_earnings_count} {noun} {verb} earnings soon."
    return base


def _oldest_reason_nudge(theses: list[dict]) -> str | None:
    candidates = [item for item in theses if item.get("why_own_it") and item.get("thesis_updated_at")]
    if not candidates:
        return None
    oldest = max(candidates, key=lambda item: item["reason_age_days"])
    if oldest["reason_age_days"] < 90:
        return None
    return (
        f'You wrote your reason for holding {oldest["name"]} {oldest["reason_age_days"]} days ago. '
        f'Would you still buy it today for the same reason?'
    )


def _render_digest_html(
    *,
    holdings_with_theses: list[dict],
    events_data: list[dict],
    observations: dict,
    headline: str,
    monitoring_receipt: str,
    quiet_nudge: str | None,
    upcoming_earnings: list[dict] | None = None,
) -> str:
    ranked_events = sorted(events_data, key=_event_rank)[:5]
    stable_holdings = observations.get("stable_holdings", [])[:3]

    parts = [
        f"<h2>{escape(headline)}</h2>",
    ]

    if ranked_events:
        # TLDR section
        tldr_lines = _tldr_lines(ranked_events)
        if tldr_lines:
            parts.append("<h3>TLDR</h3>")
            for line in tldr_lines:
                parts.append(f"<p>{escape(line)}</p>")
            parts.append("<hr>")

        # Per-holding event cards
        for event in ranked_events:
            reason_text = event.get("why_own_it") or "No reason recorded."
            ticker = event["ticker"]
            verdict = event.get("verdict")
            is_negative = verdict in ("threatens", "review")
            signal_text = event.get("signal_status_text") or ""

            parts.append(f"<h3>{escape(ticker)} — {escape(event.get('name') or ticker)}</h3>")
            parts.append(f"<p><strong>Your reason:</strong> {escape(reason_text)}</p>")
            parts.append(f"<p><strong>What changed:</strong> {escape(event.get('evidence_summary') or event['summary'])}</p>")
            if signal_text:
                parts.append(f"<p><strong>Signal status:</strong> {escape(signal_text)}</p>")
            if verdict:
                parts.append(f"<p><strong>Verdict:</strong> {escape(str(verdict).replace('_', ' '))}</p>")
            if event.get("ai_analysis"):
                parts.append(f"<p>{escape(event['ai_analysis'])}</p>")
            action_label = "Review this reason" if is_negative else "No action needed"
            parts.append(f'<p><a href="/dashboard/positions/{escape(ticker)}">→ {action_label}</a></p>')

        if stable_holdings:
            parts.append("<hr>")
            parts.append("<h3>Still intact</h3>")
            for stable in stable_holdings:
                parts.append(
                    f"<p><strong>{escape(stable['ticker'])}</strong>: {escape(stable['why_own_it'])}</p>"
                )
    else:
        parts.append("<p>Your holdings were quiet this week. No material evidence affected any of your monitored signals.</p>")
        if stable_holdings:
            parts.append("<h3>Reasons holding up</h3>")
            for stable in stable_holdings:
                stale_suffix = " This reason is getting stale." if stable.get("stale") else ""
                parts.append(
                    f"<p><strong>{escape(stable['ticker'])}</strong>: {escape(stable['why_own_it'])}.{escape(stale_suffix)}</p>"
                )

        if upcoming_earnings:
            earnings_parts = []
            for e in upcoming_earnings[:3]:
                days = e["days_until"]
                ticker = e["ticker"]
                if days == 0:
                    earnings_parts.append(f"{ticker} reports today")
                elif days == 1:
                    earnings_parts.append(f"{ticker} reports tomorrow")
                else:
                    earnings_parts.append(f"{ticker} reports in {days} days")
            parts.append(f"<p>Upcoming: {escape(', '.join(earnings_parts))}.</p>")

        if quiet_nudge:
            parts.append("<h3>Quick thought</h3>")
            parts.append(f"<p>{escape(quiet_nudge)}</p>")

    parts.append("<h3>Monitoring receipt</h3>")
    parts.append(f"<p>{escape(monitoring_receipt)}</p>")

    if observations.get("missing_theses"):
        parts.append(
            f"<p><strong>Missing reasons:</strong> {escape(', '.join(observations['missing_theses']))}</p>"
        )
    if observations.get("stale_theses"):
        parts.append(
            f"<p><strong>Stale reasons:</strong> {escape(', '.join(observations['stale_theses']))}</p>"
        )
    if observations.get("concentration_warnings"):
        parts.append(
            f"<p><strong>Concentration:</strong> {escape(observations['concentration_warnings'])}</p>"
        )

    parts.append('<p><a href="/dashboard">→ Open dashboard</a></p>')
    return "".join(parts)


async def _load_signal_counts(db, thesis_ids: list[uuid.UUID]) -> dict[str, tuple[int, int]]:
    """Returns {thesis_id_str: (intact_count, weakening_count)} for confirmed decompositions."""
    if not thesis_ids:
        return {}

    result = await db.execute(
        select(
            ThesisDecomposition.thesis_id,
            ThesisSignal.active,
            ThesisSignal.consecutive_ignores,
        )
        .select_from(ThesisSignal)
        .join(ThesisEntity, ThesisSignal.entity_id == ThesisEntity.id)
        .join(ThesisClaim, ThesisEntity.claim_id == ThesisClaim.id)
        .join(ThesisDecomposition, ThesisClaim.decomposition_id == ThesisDecomposition.id)
        .where(
            ThesisDecomposition.thesis_id.in_(thesis_ids),
            ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
            ThesisSignal.user_confirmed == True,
        )
    )
    rows = result.all()

    counts: dict[str, tuple[int, int]] = {}
    for row in rows:
        key = str(row.thesis_id)
        intact, weakening = counts.get(key, (0, 0))
        if row.active:
            if row.consecutive_ignores > 0:
                counts[key] = (intact, weakening + 1)
            else:
                counts[key] = (intact + 1, weakening)
    return counts


async def run_digest_builder():
    logger.info("Starting weekly digest builder")

    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)
    upcoming_window = now + timedelta(days=14)

    async with async_session() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        for user in users:
            try:
                prefs = user.preferences or {}
                if not prefs.get("email_enabled", True):
                    continue
                frequency = prefs.get("digest_frequency", "weekly")
                if frequency == "none":
                    continue

                # Fortnightly / monthly: skip if not enough time since last digest
                if frequency in ("fortnightly", "monthly"):
                    min_days = 13 if frequency == "fortnightly" else 27
                    last_digest_result = await db.execute(
                        select(Digest)
                        .where(Digest.user_id == user.id, Digest.status == "sent")
                        .order_by(Digest.period_end.desc())
                        .limit(1)
                    )
                    last_digest = last_digest_result.scalar_one_or_none()
                    if last_digest is not None and last_digest.period_end is not None:
                        last_end = last_digest.period_end
                        if not last_end.tzinfo:
                            last_end = last_end.replace(tzinfo=timezone.utc)
                        if (now - last_end).days < min_days:
                            continue

                holdings_result = await db.execute(
                    select(Holding).where(Holding.user_id == user.id)
                )
                holdings = holdings_result.scalars().all()
                if not holdings:
                    continue

                holdings_with_theses = []
                missing_theses = []
                stale_theses = []
                stable_holdings = []
                thesis_ids: list[uuid.UUID] = []

                for h in holdings:
                    theses_result = await db.execute(
                        select(Thesis)
                        .where(Thesis.holding_id == h.id, Thesis.status.in_(["draft", "active", "needs_review"]))
                        .order_by(Thesis.created_at.desc())
                        .limit(1)
                    )
                    thesis = theses_result.scalar_one_or_none()

                    entry = {"ticker": h.ticker, "name": h.name, "holding_id": str(h.id)}
                    if thesis:
                        entry["thesis_id"] = str(thesis.id)
                        entry["why_own_it"] = thesis.why_own_it
                        entry["must_remain_true"] = thesis.must_remain_true
                        entry["what_would_change_my_mind"] = thesis.what_would_change_my_mind
                        entry["ai_summary"] = thesis.ai_summary
                        entry["thesis_status"] = thesis.status
                        entry["thesis_updated_at"] = thesis.updated_at
                        entry["reason_age_days"] = _age_in_days(thesis.updated_at)
                        if entry["reason_age_days"] > 90:
                            stale_theses.append(h.ticker)
                        thesis_ids.append(thesis.id)
                    else:
                        missing_theses.append(h.ticker)

                    holdings_with_theses.append(entry)

                # Load signal counts per thesis in a single batch query
                signal_counts = await _load_signal_counts(db, thesis_ids)

                events_result = await db.execute(
                    select(MonitoringEvent)
                    .join(Holding)
                    .where(
                        Holding.user_id == user.id,
                        MonitoringEvent.created_at >= period_start,
                        MonitoringEvent.created_at <= period_end,
                    )
                    .order_by(MonitoringEvent.created_at.desc())
                )
                events = events_result.scalars().all()

                events_data = []
                event_holding_ids = set()
                for e in events:
                    holding = next((h for h in holdings if h.id == e.holding_id), None)
                    event_holding_ids.add(e.holding_id)
                    related_holding = holding
                    related_reason = None
                    thesis_id_str = None
                    if related_holding is not None:
                        matching_entry = next((item for item in holdings_with_theses if item["holding_id"] == str(related_holding.id)), None)
                        if matching_entry:
                            related_reason = matching_entry.get("why_own_it")
                            thesis_id_str = matching_entry.get("thesis_id")

                    intact, weakening = signal_counts.get(thesis_id_str or "", (0, 0))
                    events_data.append({
                        "ticker": holding.ticker if holding else "Unknown",
                        "name": holding.name if holding else "Unknown",
                        "severity": e.severity,
                        "title": e.title,
                        "summary": e.summary,
                        "ai_analysis": e.ai_analysis,
                        "why_own_it": related_reason,
                        "verdict": e.verdict,
                        "evidence_summary": e.evidence_summary,
                        "signal_status_text": _signal_status_text(intact, weakening),
                    })

                for entry in holdings_with_theses:
                    holding_id = entry["holding_id"]
                    if holding_id in {str(hid) for hid in event_holding_ids}:
                        continue
                    if entry.get("why_own_it"):
                        stable_holdings.append(
                            {
                                "ticker": entry["ticker"],
                                "name": entry["name"],
                                "thesis_status": entry.get("thesis_status", "draft"),
                                "stale": entry["ticker"] in stale_theses,
                                "why_own_it": entry["why_own_it"],
                            }
                        )

                # Load upcoming earnings for quiet week mode
                upcoming_earnings: list[dict] = []
                if not events_data:
                    tickers = [h.ticker for h in holdings]
                    earnings_result = await db.execute(
                        select(EarningsCalendar)
                        .where(
                            EarningsCalendar.ticker.in_(tickers),
                            EarningsCalendar.report_date >= now,
                            EarningsCalendar.report_date <= upcoming_window,
                        )
                        .order_by(EarningsCalendar.report_date)
                    )
                    for ec in earnings_result.scalars().all():
                        days_until = (ec.report_date.replace(tzinfo=timezone.utc) - now).days
                        upcoming_earnings.append({"ticker": ec.ticker, "days_until": max(0, days_until)})

                total_value = sum(float(h.current_value or 0) for h in holdings)
                concentration_warnings = ""
                if total_value > 0:
                    sector_pcts = {}
                    for h in holdings:
                        s = h.sector or "Unknown"
                        sector_pcts[s] = sector_pcts.get(s, 0) + float(h.current_value or 0) / total_value * 100
                    high_conc = {k: round(v, 1) for k, v in sector_pcts.items() if v > 30}
                    if high_conc:
                        concentration_warnings = ", ".join(f"{k}: {v}%" for k, v in high_conc.items())

                observations = {
                    "concentration_warnings": concentration_warnings,
                    "stale_theses": stale_theses,
                    "missing_theses": missing_theses,
                    "stable_holdings": stable_holdings,
                }
                headline = _digest_headline(
                    len(events_data),
                    len(stale_theses),
                    len(missing_theses),
                    len(stable_holdings),
                )
                subject = _digest_subject(len(events_data), len(stable_holdings))
                receipt = _monitoring_receipt(
                    len(holdings),
                    len(events_data),
                    len(stable_holdings),
                    upcoming_earnings_count=len(upcoming_earnings),
                )
                quiet_nudge = _oldest_reason_nudge(holdings_with_theses) if not events_data else None

                # Track consecutive quiet weeks and suggest frequency change
                prefs = dict(user.preferences) if user.preferences else {}
                quiet_streak = prefs.get("consecutive_quiet_weeks", 0)
                if not events_data:
                    quiet_streak += 1
                else:
                    quiet_streak = 0
                if prefs.get("consecutive_quiet_weeks") != quiet_streak:
                    prefs["consecutive_quiet_weeks"] = quiet_streak
                    user.preferences = prefs

                html_content = _render_digest_html(
                    holdings_with_theses=holdings_with_theses,
                    events_data=events_data,
                    observations=observations,
                    headline=headline,
                    monitoring_receipt=receipt,
                    quiet_nudge=quiet_nudge,
                    upcoming_earnings=upcoming_earnings if not events_data else None,
                )

                digest = Digest(
                    user_id=user.id,
                    period_start=period_start,
                    period_end=period_end,
                    content={
                        "html": html_content,
                        "digest_mode": "events" if events_data else "quiet_week",
                        "subject_line": subject,
                        "events_count": len(events_data),
                        "holdings_count": len(holdings),
                        "stable_holdings_count": len(stable_holdings),
                        "headline": headline,
                        "summary_points": _digest_summary_points(events_data, observations),
                        "missing_theses_count": len(missing_theses),
                        "stale_theses_count": len(stale_theses),
                        "concentration_warning": concentration_warnings,
                        "monitoring_receipt": receipt,
                        "quiet_nudge": quiet_nudge,
                        "consecutive_quiet_weeks": quiet_streak,
                    },
                    status="pending",
                )
                db.add(digest)
                await db.flush()

                for e in events:
                    e.included_in_digest_id = digest.id

                if html_content:
                    sent = await send_digest_email(
                        to_email=user.email,
                        subject=subject,
                        html_content=html_content,
                    )
                    digest.status = "sent" if sent else "failed"
                    digest.sent_at = datetime.now(timezone.utc) if sent else None
                    if sent:
                        from app.services.onboarding import mark_digest_received
                        await mark_digest_received(db, user.id)
                else:
                    digest.status = "failed"

                await db.commit()
                logger.info(f"Digest {'sent' if digest.status == 'sent' else 'failed'} for user {user.id}")

            except Exception as e:
                logger.error(f"Digest build failed for user {user.id}: {e}")
                continue

    logger.info("Weekly digest builder complete")
