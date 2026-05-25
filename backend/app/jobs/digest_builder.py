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
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.email import send_digest_email

logger = logging.getLogger(__name__)
InvestorProfile = str | None


def _normalize_datetime(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


def _age_in_days(timestamp: datetime, *, now: datetime) -> int:
    return (now - _normalize_datetime(timestamp)).days


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
    return "Quiet week — nothing touched what you're watching."


def _digest_subject(
    events_count: int,
    stable_count: int,
    *,
    upcoming_earnings: list[dict] | None = None,
    oldest_stale_name: str | None = None,
    oldest_stale_days: int | None = None,
    missing_count: int = 0,
) -> str:
    if events_count > 0:
        verb = "needs" if events_count == 1 else "need"
        return f"{events_count} of your reasons {verb} review this week"
    # Quiet week — lead with something worth opening for
    if upcoming_earnings:
        next_e = upcoming_earnings[0]
        days = next_e["days_until"]
        ticker = next_e["ticker"].replace("_US_EQ", "").replace("_EQ", "")
        if days == 0:
            return f"{ticker} reports today — here's what to watch"
        if days == 1:
            return f"{ticker} reports tomorrow — here's what to watch"
        return f"{ticker} reports in {days} days — here's what to watch"
    if oldest_stale_name and oldest_stale_days and oldest_stale_days >= 90:
        return f"You haven't revisited your {oldest_stale_name} thesis in {oldest_stale_days} days"
    if missing_count > 0:
        noun = "holding" if missing_count == 1 else "holdings"
        return f"{missing_count} of your {noun} still {'has' if missing_count == 1 else 'have'} no reason attached"
    if stable_count > 0:
        return f"Your portfolio held up this week — {stable_count} reason{'s' if stable_count != 1 else ''} checked"
    return "Weekly portfolio check — nothing flagged this week"


def _digest_summary_points(
    events_data: list[dict],
    observations: dict,
    next_earnings: dict | None = None,
    *,
    investor_profile: InvestorProfile = None,
) -> list[str]:
    points: list[str] = []
    if events_data:
        first = events_data[0]
        clean = first["ticker"].replace("_US_EQ", "").replace("_EQ", "")
        points.append(f"{clean}: {_what_happened(first)}")
    if observations.get("stale_theses"):
        points.append(f"Stale theses: {', '.join(observations['stale_theses'][:3])}")
    if observations.get("missing_theses"):
        points.append(f"Missing theses: {', '.join(observations['missing_theses'][:3])}")
    if observations.get("concentration_warnings"):
        points.append(f"Concentration: {observations['concentration_warnings']}")
    stable = observations.get("stable_holdings", [])
    if stable and not points:
        prefix = "Stable theses" if investor_profile == "thesis_driven" else "Stable reasons"
        points.append(f"{prefix}: {', '.join(item['ticker'] for item in stable[:3])}")
    if next_earnings and len(points) < 3:
        days = next_earnings["days_until"]
        if days == 0:
            points.append(f"Upcoming: {next_earnings['ticker']} reports today")
        elif days == 1:
            points.append(f"Upcoming: {next_earnings['ticker']} reports tomorrow")
        else:
            points.append(f"Upcoming: {next_earnings['ticker']} reports in {days} days")
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


def _parse_evidence_parts(evidence_summary: str | None) -> dict[str, str]:
    """Extract keyed sections and trailing unlabeled lines from evidence summaries."""
    if not evidence_summary:
        return {}
    parts: dict[str, str] = {}
    body_lines: list[str] = []
    keyed_prefixes = (
        "You said",
        "We watched",
        "We were watching",
        "What happened",
        "Your reason",
        "Your thesis",
        "What the app was checking",
        "What changed",
        "Why this matters now",
        "Decision to consider",
    )
    for line in evidence_summary.split("\n"):
        matched = False
        for key in keyed_prefixes:
            prefix = f"{key}:"
            if line.startswith(prefix):
                parts[key] = line[len(prefix):].strip().strip('"')
                matched = True
                break
        if not matched and line.strip():
            body_lines.append(line.strip())
    if body_lines:
        parts["_body_0"] = body_lines[0]
        if len(body_lines) > 1:
            parts["_body_1"] = body_lines[1]
        if len(body_lines) > 2:
            parts["_body_2"] = body_lines[2]
    return parts


def _what_happened(event: dict) -> str:
    """One-line fact extracted from the event — suitable for TLDR or subject."""
    evidence = _parse_evidence_parts(event.get("evidence_summary"))
    return (
        evidence.get("What changed")
        or evidence.get("What happened")
        or evidence.get("_body_0")
        or event.get("summary", "")
    )


def _tldr_lines(events_data: list[dict]) -> list[str]:
    lines = []
    for event in events_data[:3]:
        ticker = event["ticker"].replace("_US_EQ", "").replace("_EQ", "")
        verdict = event.get("verdict")
        what = _what_happened(event)
        if verdict == "threatens":
            lines.append(f"{ticker}: {what} — worth a look against your reason.")
        elif verdict == "supports":
            lines.append(f"{ticker}: {what} Aligns with your reason for holding.")
        else:
            lines.append(f"{ticker}: {what}")
    return lines


def _render_evidence_html(event: dict) -> str:
    """Render the structured evidence_summary as clean HTML for the email card."""
    evidence_summary = event.get("evidence_summary")
    if not evidence_summary:
        return f"<p>{escape(event.get('summary', ''))}</p>"

    parts = _parse_evidence_parts(evidence_summary)
    html_parts = []

    you_said = parts.get("Your thesis") or parts.get("You said") or parts.get("Your reason")
    we_watched = parts.get("We were watching") or parts.get("What the app was checking") or parts.get("We watched")
    what_happened = parts.get("What changed") or parts.get("What happened") or parts.get("_body_0")

    if you_said:
        html_parts.append(f'<blockquote style="border-left:3px solid #ccc;margin:8px 0;padding:4px 12px;color:#555;">&ldquo;{escape(you_said)}&rdquo;</blockquote>')
    if we_watched:
        html_parts.append(f'<p style="font-size:12px;color:#888;margin:4px 0;">Signal: {escape(we_watched)}</p>')
    if what_happened:
        html_parts.append(f'<p style="margin:8px 0;">{escape(what_happened)}</p>')
    elif not html_parts:
        # No structured parts — fall back to raw summary
        html_parts.append(f"<p>{escape(event.get('summary', ''))}</p>")

    if event.get("ai_analysis"):
        html_parts.append(f'<p style="font-style:italic;color:#666;margin:4px 0;">{escape(event["ai_analysis"])}</p>')

    return "".join(html_parts)


def _monitoring_receipt(
    holdings_count: int,
    events_count: int,
    stable_count: int,
    upcoming_earnings_count: int = 0,
    *,
    investor_profile: InvestorProfile = None,
) -> str:
    noun = "holding" if holdings_count == 1 else "holdings"
    if events_count > 0:
        flagged = f"{events_count} flagged"
        if investor_profile == "thesis_driven":
            base = f"Checked {holdings_count} {noun} against your written assumptions — {flagged}."
        elif investor_profile == "hearsay_driven":
            base = f"Checked {holdings_count} {noun} against your reasons — {flagged}."
        else:
            base = f"Checked {holdings_count} {noun} — {flagged}."
    else:
        if investor_profile == "thesis_driven":
            base = f"Checked {holdings_count} {noun} against your written assumptions — all quiet."
        elif investor_profile == "hearsay_driven":
            base = f"Checked {holdings_count} {noun} against your reasons — all quiet."
        else:
            base = f"Checked {holdings_count} {noun} — all quiet."
    if upcoming_earnings_count > 0:
        enoun = "holding" if upcoming_earnings_count == 1 else "holdings"
        verb = "reports" if upcoming_earnings_count == 1 else "report"
        base += f" {upcoming_earnings_count} {enoun} {verb} earnings soon."
    return base


def _oldest_reason_nudge(theses: list[dict], *, investor_profile: InvestorProfile = None) -> str | None:
    candidates = [item for item in theses if item.get("why_own_it") and item.get("thesis_updated_at")]
    if not candidates:
        return None
    oldest = max(candidates, key=lambda item: item["reason_age_days"])
    if oldest["reason_age_days"] < 90:
        return None
    if investor_profile == "thesis_driven":
        return (
            f'You wrote your reason for holding {oldest["name"]} {oldest["reason_age_days"]} days ago. '
            f"Would you still own it today for the same core assumption?"
        )
    if investor_profile == "hearsay_driven":
        return (
            f'You wrote your reason for holding {oldest["name"]} {oldest["reason_age_days"]} days ago. '
            f"Would the same story still convince you today, or does it need a sharper reason?"
        )
    return (
        f'You wrote your reason for holding {oldest["name"]} {oldest["reason_age_days"]} days ago. '
        f'Would you still buy it today for the same reason?'
    )


def _digest_intro_line(has_events: bool, *, investor_profile: InvestorProfile = None) -> str | None:
    if investor_profile == "thesis_driven":
        return (
            "This week&apos;s evidence is framed against the assumptions you wrote down."
            if has_events
            else "None of your monitored assumptions moved meaningfully this week."
        )
    if investor_profile == "hearsay_driven":
        return (
            "This week&apos;s evidence tests whether the original story still holds up as a real reason."
            if has_events
            else "Nothing this week challenged the reasons you wrote down."
        )
    return None


def _event_action_label(*, is_negative: bool, investor_profile: InvestorProfile = None) -> str:
    if not is_negative:
        return "View position"
    if investor_profile == "thesis_driven":
        return "Review this thesis"
    if investor_profile == "hearsay_driven":
        return "Revisit this reason"
    return "Review this reason"


def _stable_section_title(*, investor_profile: InvestorProfile = None) -> str:
    if investor_profile == "thesis_driven":
        return "Assumptions still holding"
    if investor_profile == "hearsay_driven":
        return "Reasons still holding up"
    return "Reasons holding up"


async def _load_investor_profile(db, user_id: uuid.UUID) -> InvestorProfile:
    result = await db.execute(
        select(OnboardingState.investor_profile).where(OnboardingState.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _should_skip_user_digest(db, user: User, *, now: datetime) -> bool:
    prefs = user.preferences or {}
    if not prefs.get("email_enabled", True):
        return True

    frequency = prefs.get("digest_frequency", "weekly")
    if frequency == "none":
        return True

    if frequency not in {"fortnightly", "monthly"}:
        return False

    min_days = 13 if frequency == "fortnightly" else 27
    last_digest_result = await db.execute(
        select(Digest)
        .where(Digest.user_id == user.id, Digest.status == "sent")
        .order_by(Digest.period_end.desc())
        .limit(1)
    )
    last_digest = last_digest_result.scalar_one_or_none()
    if last_digest is None or last_digest.period_end is None:
        return False

    last_end = _normalize_datetime(last_digest.period_end)
    return (now - last_end).days < min_days


async def _load_user_holdings(db, user_id: uuid.UUID) -> list[Holding]:
    holdings_result = await db.execute(select(Holding).where(Holding.user_id == user_id))
    return list(holdings_result.scalars().all())


async def _load_latest_theses_by_holding(db, holding_ids: list[uuid.UUID]) -> dict[str, Thesis]:
    if not holding_ids:
        return {}

    all_theses_result = await db.execute(
        select(Thesis)
        .where(
            Thesis.holding_id.in_(holding_ids),
            Thesis.status.in_(["draft", "active", "needs_review"]),
        )
        .order_by(Thesis.created_at.desc())
    )

    thesis_by_holding: dict[str, Thesis] = {}
    for thesis in all_theses_result.scalars().all():
        thesis_by_holding.setdefault(str(thesis.holding_id), thesis)
    return thesis_by_holding


def _build_holding_snapshots(
    holdings: list[Holding],
    thesis_by_holding: dict[str, Thesis],
    *,
    now: datetime,
) -> tuple[list[dict], list[str], list[str], list[uuid.UUID], dict[str, dict]]:
    snapshots: list[dict] = []
    missing_theses: list[str] = []
    stale_theses: list[str] = []
    thesis_ids: list[uuid.UUID] = []

    for holding in holdings:
        thesis = thesis_by_holding.get(str(holding.id))
        snapshot = {
            "ticker": holding.ticker,
            "name": holding.name,
            "holding_id": str(holding.id),
        }
        if thesis:
            reason_age_days = _age_in_days(thesis.updated_at, now=now)
            snapshot.update(
                {
                    "thesis_id": str(thesis.id),
                    "why_own_it": thesis.why_own_it,
                    "must_remain_true": thesis.must_remain_true,
                    "what_would_change_my_mind": thesis.what_would_change_my_mind,
                    "ai_summary": thesis.ai_summary,
                    "thesis_status": thesis.status,
                    "thesis_updated_at": thesis.updated_at,
                    "reason_age_days": reason_age_days,
                }
            )
            if reason_age_days > 90:
                stale_theses.append(holding.ticker)
            thesis_ids.append(thesis.id)
        else:
            missing_theses.append(holding.ticker)

        snapshots.append(snapshot)

    snapshot_by_holding_id = {snapshot["holding_id"]: snapshot for snapshot in snapshots}
    return snapshots, missing_theses, stale_theses, thesis_ids, snapshot_by_holding_id


async def _load_events_data(
    db,
    *,
    user_id: uuid.UUID,
    holdings_by_id: dict[uuid.UUID, Holding],
    snapshot_by_holding_id: dict[str, dict],
    signal_counts: dict[str, tuple[int, int]],
    period_start: datetime,
    period_end: datetime,
) -> tuple[list[MonitoringEvent], list[dict], set[str]]:
    events_result = await db.execute(
        select(MonitoringEvent)
        .join(Holding)
        .where(
            Holding.user_id == user_id,
            MonitoringEvent.created_at >= period_start,
            MonitoringEvent.created_at <= period_end,
        )
        .order_by(MonitoringEvent.created_at.desc())
    )
    events = list(events_result.scalars().all())
    event_holding_ids: set[str] = set()
    events_data: list[dict] = []

    for event in events:
        holding = holdings_by_id.get(event.holding_id)
        holding_id_str = str(event.holding_id)
        event_holding_ids.add(holding_id_str)
        snapshot = snapshot_by_holding_id.get(holding_id_str, {})
        thesis_id_str = snapshot.get("thesis_id")
        intact, weakening = signal_counts.get(str(thesis_id_str or ""), (0, 0))

        events_data.append(
            {
                "ticker": holding.ticker if holding else "Unknown",
                "name": holding.name if holding else "Unknown",
                "severity": event.severity,
                "title": event.title,
                "summary": event.summary,
                "ai_analysis": event.ai_analysis,
                "why_own_it": snapshot.get("why_own_it"),
                "verdict": event.verdict,
                "evidence_summary": event.evidence_summary,
                "signal_status_text": _signal_status_text(intact, weakening),
            }
        )

    return events, events_data, event_holding_ids


def _build_stable_holdings(
    holdings_with_theses: list[dict],
    *,
    event_holding_ids: set[str],
    stale_tickers: set[str],
) -> list[dict]:
    stable_holdings: list[dict] = []
    for snapshot in holdings_with_theses:
        if snapshot["holding_id"] in event_holding_ids or not snapshot.get("why_own_it"):
            continue
        stable_holdings.append(
            {
                "ticker": snapshot["ticker"],
                "name": snapshot["name"],
                "thesis_status": snapshot.get("thesis_status", "draft"),
                "stale": snapshot["ticker"] in stale_tickers,
                "why_own_it": snapshot["why_own_it"],
            }
        )
    return stable_holdings


async def _load_upcoming_earnings(
    db,
    *,
    tickers: list[str],
    now: datetime,
    upcoming_window: datetime,
) -> list[dict]:
    if not tickers:
        return []

    earnings_result = await db.execute(
        select(EarningsCalendar)
        .where(
            EarningsCalendar.ticker.in_(tickers),
            EarningsCalendar.report_date >= now,
            EarningsCalendar.report_date <= upcoming_window,
        )
        .order_by(EarningsCalendar.report_date)
    )

    upcoming_earnings: list[dict] = []
    for earnings in earnings_result.scalars().all():
        report_date = _normalize_datetime(earnings.report_date)
        days_until = (report_date - now).days
        upcoming_earnings.append(
            {
                "ticker": earnings.ticker,
                "report_date": report_date.isoformat(),
                "days_until": max(0, days_until),
            }
        )
    return upcoming_earnings


def _concentration_warning(holdings: list[Holding]) -> str:
    total_value = sum(float(holding.current_value or 0) for holding in holdings)
    if total_value <= 0:
        return ""

    sector_pcts: dict[str, float] = {}
    for holding in holdings:
        sector = holding.sector or "Unknown"
        sector_pcts[sector] = sector_pcts.get(sector, 0.0) + float(holding.current_value or 0) / total_value * 100

    high_conc = {sector: round(pct, 1) for sector, pct in sector_pcts.items() if pct > 30}
    if not high_conc:
        return ""
    return ", ".join(f"{sector}: {pct}%" for sector, pct in high_conc.items())


def _update_quiet_streak(user: User, *, has_events: bool) -> int:
    prefs = dict(user.preferences) if user.preferences else {}
    quiet_streak = prefs.get("consecutive_quiet_weeks", 0)
    quiet_streak = 0 if has_events else quiet_streak + 1
    if prefs.get("consecutive_quiet_weeks") != quiet_streak:
        prefs["consecutive_quiet_weeks"] = quiet_streak
        user.preferences = prefs
    return quiet_streak


def _render_digest_html(
    *,
    holdings_with_theses: list[dict],
    events_data: list[dict],
    observations: dict,
    headline: str,
    monitoring_receipt: str,
    quiet_nudge: str | None,
    upcoming_earnings: list[dict] | None = None,
    investor_profile: InvestorProfile = None,
) -> str:
    ranked_events = sorted(events_data, key=_event_rank)[:5]
    stable_holdings = observations.get("stable_holdings", [])[:3]

    parts = [
        f"<h2>{escape(headline)}</h2>",
    ]
    intro_line = _digest_intro_line(bool(ranked_events), investor_profile=investor_profile)
    if intro_line:
        parts.append(f"<p>{intro_line}</p>")

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
            clean_ticker = ticker.replace("_US_EQ", "").replace("_EQ", "")
            verdict = event.get("verdict")
            is_negative = verdict in ("threatens", "review")
            signal_text = event.get("signal_status_text") or ""

            verdict_color = {"threatens": "#b91c1c", "supports": "#15803d", "review": "#b45309"}.get(verdict or "", "#555")
            verdict_label = {"threatens": "Threatens this reason", "supports": "Supports this reason", "review": "Worth reviewing", "neutral": "Neutral"}.get(verdict or "", "")

            parts.append(f'<div style="border:1px solid #e5e7eb;border-radius:6px;padding:16px;margin:12px 0;">')
            parts.append(f'<p style="margin:0 0 8px;font-weight:600;">{escape(clean_ticker)} — {escape(event.get("name") or clean_ticker)}</p>')
            parts.append(f'<p style="font-size:12px;color:#888;margin:0 0 8px;">Your reason:</p>')
            parts.append(f'<blockquote style="border-left:3px solid #d1d5db;margin:0 0 12px;padding:4px 12px;color:#374151;">&ldquo;{escape(reason_text)}&rdquo;</blockquote>')
            parts.append(_render_evidence_html(event))
            if signal_text:
                parts.append(f'<p style="font-size:12px;color:#888;margin:8px 0;">Signals: {escape(signal_text)}</p>')
            if verdict_label:
                parts.append(f'<p style="color:{verdict_color};font-weight:500;margin:8px 0;">{escape(verdict_label)}</p>')
            action_label = _event_action_label(is_negative=is_negative, investor_profile=investor_profile)
            parts.append(f'<p style="margin:12px 0 0;"><a href="/dashboard/positions/{escape(ticker)}" style="color:#1d4ed8;">→ {action_label}</a></p>')
            parts.append("</div>")

        if stable_holdings:
            parts.append("<hr>")
            parts.append(f"<h3>{escape(_stable_section_title(investor_profile=investor_profile))}</h3>")
            for stable in stable_holdings:
                parts.append(
                    f"<p><strong>{escape(stable['ticker'])}</strong>: {escape(stable['why_own_it'])}</p>"
                )
    else:
        parts.append("<p>Your holdings were quiet this week. Nothing landed that touched what you&apos;re watching.</p>")
        if stable_holdings:
            parts.append(f"<h3>{escape(_stable_section_title(investor_profile=investor_profile))}</h3>")
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
    import time
    started = time.monotonic()
    logger.info("Starting weekly digest builder")

    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)
    upcoming_window = now + timedelta(days=14)

    async with async_session() as db:
        users_result = await db.execute(select(User.id))
        user_ids = list(users_result.scalars().all())

        for user_id in user_ids:
            user = await db.get(User, user_id)
            if user is None:
                continue
            try:
                if await _should_skip_user_digest(db, user, now=now):
                    continue

                holdings = await _load_user_holdings(db, user_id)
                if not holdings:
                    continue

                holdings_by_id = {holding.id: holding for holding in holdings}
                thesis_by_holding = await _load_latest_theses_by_holding(db, list(holdings_by_id))
                holdings_with_theses, missing_theses, stale_theses, thesis_ids, snapshot_by_holding_id = _build_holding_snapshots(
                    holdings,
                    thesis_by_holding,
                    now=now,
                )
                signal_counts = await _load_signal_counts(db, thesis_ids)
                investor_profile = await _load_investor_profile(db, user_id)
                events, events_data, event_holding_ids = await _load_events_data(
                    db,
                    user_id=user_id,
                    holdings_by_id=holdings_by_id,
                    snapshot_by_holding_id=snapshot_by_holding_id,
                    signal_counts=signal_counts,
                    period_start=period_start,
                    period_end=period_end,
                )
                stable_holdings = _build_stable_holdings(
                    holdings_with_theses,
                    event_holding_ids=event_holding_ids,
                    stale_tickers=set(stale_theses),
                )

                upcoming_earnings = []
                if not events_data:
                    upcoming_earnings = await _load_upcoming_earnings(
                        db,
                        tickers=[holding.ticker for holding in holdings],
                        now=now,
                        upcoming_window=upcoming_window,
                    )

                concentration_warnings = _concentration_warning(holdings)

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
                _stale_nudge_item = max(
                    [item for item in holdings_with_theses if item.get("why_own_it") and item.get("reason_age_days", 0) >= 90],
                    key=lambda item: item["reason_age_days"],
                    default=None,
                )
                subject = _digest_subject(
                    len(events_data),
                    len(stable_holdings),
                    upcoming_earnings=upcoming_earnings or None,
                    oldest_stale_name=_stale_nudge_item["name"] if _stale_nudge_item else None,
                    oldest_stale_days=_stale_nudge_item["reason_age_days"] if _stale_nudge_item else None,
                    missing_count=len(missing_theses),
                )
                receipt = _monitoring_receipt(
                    len(holdings),
                    len(events_data),
                    len(stable_holdings),
                    upcoming_earnings_count=len(upcoming_earnings),
                    investor_profile=investor_profile,
                )
                quiet_nudge = _oldest_reason_nudge(holdings_with_theses, investor_profile=investor_profile) if not events_data else None
                next_earnings = upcoming_earnings[0] if upcoming_earnings else None

                quiet_streak = _update_quiet_streak(user, has_events=bool(events_data))

                html_content = _render_digest_html(
                    holdings_with_theses=holdings_with_theses,
                    events_data=events_data,
                    observations=observations,
                    headline=headline,
                    monitoring_receipt=receipt,
                    quiet_nudge=quiet_nudge,
                    upcoming_earnings=upcoming_earnings if not events_data else None,
                    investor_profile=investor_profile,
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
                        "summary_points": _digest_summary_points(
                            events_data,
                            observations,
                            next_earnings,
                            investor_profile=investor_profile,
                        ),
                        "missing_theses_count": len(missing_theses),
                        "stale_theses_count": len(stale_theses),
                        "concentration_warning": concentration_warnings,
                        "monitoring_receipt": receipt,
                        "quiet_nudge": quiet_nudge,
                        "consecutive_quiet_weeks": quiet_streak,
                        "next_earnings": next_earnings,
                        "investor_profile": investor_profile,
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
                        await mark_digest_received(db, user_id)
                else:
                    digest.status = "failed"

                await db.commit()
                logger.info("Digest %s for user %s", "sent" if digest.status == "sent" else "failed", user_id)

            except Exception:
                await db.rollback()
                logger.exception("Digest build failed for user %s", user_id)
                continue

    elapsed = time.monotonic() - started
    logger.info("Weekly digest builder complete in %.1fs", elapsed)
