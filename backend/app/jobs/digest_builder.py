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
from app.services.adjacency import (
    curate_reviewed_but_dropped,
    load_reviewed_but_dropped,
    source_label_for_reader,
)
from app.services.email import send_digest_email
from app.config import settings

logger = logging.getLogger(__name__)
InvestorProfile = str | None

# --- Digest visual language (aligned with penKeep brand tokens) ---
_DZ = {
    "paper": "#ECE7DB",   # outer page — parchment
    "card": "#F5F0E8",    # the digest sheet
    "ink": "#161510",     # primary text — deep ink
    "muted": "#6B6258",   # secondary text
    "faint": "#9A8A78",   # labels / footer
    "line": "#C8BBA8",    # hairline
    "quote": "#EDE5DB",   # quote rule + soft fill
    "accent": "#1E5C3A",  # forest green (brand)
    "accent_deep": "#174D31",  # deep forest green
    "warning": "#C1492A",  # rust — reserved for danger/warning semantics
}
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
_MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"

# Verdict → (text colour, soft background, label)
_VERDICT_STYLE = {
    "threatens": ("#C1492A", "#F0E3DC", "Threatens this reason"),
    "supports": ("#3D6B41", "#E3EDE4", "Supports this reason"),
    "review": ("#9C6A1E", "#F0E8D8", "Worth reviewing"),
    "neutral": ("#6B6258", "#EDE5DB", "Neutral"),
}


def _section_label(text: str) -> str:
    """A small uppercase mono section header — the editorial label used throughout."""
    return (
        f'<div style="font-family:{_MONO};font-size:10px;letter-spacing:0.18em;'
        f'text-transform:uppercase;color:{_DZ["accent"]};margin:26px 0 10px;">{escape(text)}</div>'
    )


def _wrap_email_shell(body_html: str, *, headline: str, preheader: str = "") -> str:
    """Wrap the digest body in a centred, branded email frame. Applied only on the
    email send path so the in-app embed keeps using the bare body fragment."""
    pre = escape((preheader or headline) or "")[:140]
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light only">'
        f'</head><body style="margin:0;padding:0;background:{_DZ["paper"]};font-family:{_SERIF};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{pre}&nbsp;</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_DZ["paper"]};"><tr><td align="center" style="padding:48px 16px 64px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">'
        # Top brand rule
        f'<tr><td style="background-color:{_DZ["accent_deep"]};height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        # Card open
        f'<tr><td style="background:{_DZ["card"]};border-left:1px solid {_DZ["line"]};border-right:1px solid {_DZ["line"]};">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        # Masthead
        f'<tr><td style="padding:28px 36px 22px;border-bottom:1px solid {_DZ["line"]};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td><p style="margin:0;font-family:{_MONO};font-size:11px;letter-spacing:0.22em;text-transform:uppercase;color:{_DZ["accent_deep"]};">penKeep</p></td>'
        f'<td align="right"><p style="margin:0;font-family:{_MONO};font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:{_DZ["faint"]};">Weekly digest</p></td>'
        '</tr></table></td></tr>'
        # Body
        f'<tr><td style="padding:8px 36px 4px;font-family:{_SERIF};font-size:15px;line-height:1.62;color:{_DZ["ink"]};">{body_html}</td></tr>'
        # Footer
        f'<tr><td style="padding:22px 36px 28px;border-top:1px solid {_DZ["line"]};">'
        f'<p style="margin:0;font-family:{_MONO};font-size:11px;line-height:1.7;color:{_DZ["faint"]};">'
        f'penKeep &middot; <a href="https://penkeep.io" style="color:{_DZ["faint"]};text-decoration:none;">penkeep.io</a><br>'
        f'<a href="{settings.frontend_url}/settings" style="color:{_DZ["muted"]};text-decoration:underline;">Change digest schedule</a>'
        '</p></td></tr>'
        '</table></td></tr>'
        # Bottom hairline
        f'<tr><td style="background:{_DZ["line"]};height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _normalize_datetime(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


def _age_in_days(timestamp: datetime, *, now: datetime) -> int:
    return (now - _normalize_datetime(timestamp)).days


def _digest_headline(reasons_flagged: int, stale_count: int, missing_count: int, stable_count: int) -> str:
    # reasons_flagged counts distinct holdings with events, not raw events — a
    # single position firing two signals is still one reason to review.
    if reasons_flagged > 0:
        verb = "needs" if reasons_flagged == 1 else "need"
        return f"{reasons_flagged} of your reasons {verb} review this week."
    if stale_count > 0:
        return f"{stale_count} thesis{'es' if stale_count != 1 else ''} went stale this week."
    if missing_count > 0:
        return f"{missing_count} holding{'s' if missing_count != 1 else ''} still lack a thesis."
    if stable_count > 0:
        return f"{stable_count} of your reasons held up this week."
    return "Quiet week — nothing touched what you're watching."


def _digest_subject(
    reasons_flagged: int,
    stable_count: int,
    *,
    upcoming_earnings: list[dict] | None = None,
    oldest_stale_name: str | None = None,
    oldest_stale_days: int | None = None,
    missing_count: int = 0,
) -> str:
    if reasons_flagged > 0:
        verb = "needs" if reasons_flagged == 1 else "need"
        return f"{reasons_flagged} of your reasons {verb} review this week"
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
        html_parts.append(f'<div style="border-left:2px solid {_DZ["quote"]};margin:8px 0;padding:1px 0 1px 12px;color:{_DZ["muted"]};font-style:italic;">&ldquo;{escape(you_said)}&rdquo;</div>')
    if we_watched:
        html_parts.append(f'<p style="font-size:12px;color:{_DZ["faint"]};margin:4px 0;">Signal: {escape(we_watched)}</p>')
    if what_happened:
        html_parts.append(f'<p style="margin:8px 0;">{escape(what_happened)}</p>')
    elif not html_parts:
        # No structured parts — fall back to raw summary
        html_parts.append(f'<p style="margin:8px 0;">{escape(event.get("summary", ""))}</p>')

    if event.get("ai_analysis"):
        html_parts.append(f'<p style="color:{_DZ["muted"]};margin:6px 0;">{escape(event["ai_analysis"])}</p>')

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


def _missing_section_label(*, investor_profile: InvestorProfile = None) -> str:
    if investor_profile == "thesis_driven":
        return "Missing theses"
    return "Missing reasons"


def _stale_section_label(*, investor_profile: InvestorProfile = None) -> str:
    if investor_profile == "thesis_driven":
        return "Stale theses"
    return "Stale reasons"


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
                "event_type": event.event_type,
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
    mirror: dict | None = None,
    reviewed_but_dropped: list[dict] | None = None,
    now: datetime | None = None,
) -> str:
    # Supporting events are pulled out and rendered in a distinct 'Held up
    # this week' section instead of mixed into the ranked alerts — a
    # positive event styled like a threat card reads as "another thing to
    # deal with" instead of "your thesis was validated."
    held_up_events = _pick_held_up_events(events_data)
    held_up_ids = {id(event) for event in held_up_events}
    alert_events = [event for event in events_data if id(event) not in held_up_ids]
    ranked_events = sorted(alert_events, key=_event_rank)[:5]
    stable_holdings = observations.get("stable_holdings", [])[:3]

    parts = [
        f'<h2 style="font-family:{_SERIF};font-style:italic;font-weight:400;font-size:24px;'
        f'line-height:1.25;color:{_DZ["ink"]};margin:18px 0 2px;">{escape(headline)}</h2>',
    ]
    intro_line = _digest_intro_line(bool(ranked_events), investor_profile=investor_profile)
    if intro_line:
        parts.append(f'<p style="color:{_DZ["muted"]};margin:8px 0 4px;">{intro_line}</p>')

    if ranked_events:
        # TLDR section
        tldr_lines = _tldr_lines(ranked_events)
        if tldr_lines:
            parts.append(_section_label("TLDR"))
            for line in tldr_lines:
                parts.append(f'<p style="margin:6px 0;">{escape(line)}</p>')
            parts.append(f'<hr style="border:none;border-top:1px solid {_DZ["line"]};margin:22px 0;">')

        # Per-holding event cards
        for event in ranked_events:
            reason_text = event.get("why_own_it") or "No reason recorded."
            ticker = event["ticker"]
            clean_ticker = ticker.replace("_US_EQ", "").replace("_EQ", "")
            verdict = event.get("verdict")
            is_negative = verdict in ("threatens", "review")
            signal_text = event.get("signal_status_text") or ""

            v_color, v_bg, v_label = _VERDICT_STYLE.get(verdict or "", ("", "", ""))

            parts.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                f'style="margin:14px 0;background:{_DZ["card"]};border:1px solid {_DZ["line"]};'
                f'border-left:3px solid {_DZ["warning"] if is_negative else _DZ["line"]};">'
                '<tr><td style="padding:16px 18px;">'
            )
            parts.append(
                f'<div style="font-family:{_SERIF};font-size:17px;color:{_DZ["ink"]};margin:0 0 12px;">'
                f'{escape(clean_ticker)} <span style="color:{_DZ["faint"]};font-size:14px;">'
                f'{escape(event.get("name") or clean_ticker)}</span></div>'
            )
            parts.append(
                f'<div style="font-family:{_MONO};font-size:9px;letter-spacing:0.16em;'
                f'text-transform:uppercase;color:{_DZ["faint"]};margin:0 0 4px;">Your reason</div>'
            )
            parts.append(
                f'<div style="border-left:2px solid {_DZ["quote"]};padding:1px 0 1px 12px;'
                f'color:{_DZ["muted"]};font-style:italic;margin:0 0 12px;">&ldquo;{escape(reason_text)}&rdquo;</div>'
            )
            parts.append(_render_evidence_html(event))
            if signal_text:
                parts.append(f'<p style="font-size:12px;color:{_DZ["faint"]};margin:8px 0;">Signals: {escape(signal_text)}</p>')
            if v_label:
                parts.append(
                    f'<div style="margin:10px 0 2px;"><span style="display:inline-block;font-family:{_MONO};'
                    f'font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:{v_color};'
                    f'background:{v_bg};padding:4px 9px;">{escape(v_label)}</span></div>'
                )
            action_label = _event_action_label(is_negative=is_negative, investor_profile=investor_profile)
            parts.append(
                f'<p style="margin:13px 0 0;"><a href="{settings.frontend_url}/dashboard/positions/{escape(ticker)}" '
                f'style="color:{_DZ["accent"]};text-decoration:none;font-weight:600;">{escape(action_label)} &rarr;</a></p>'
            )
            parts.append('</td></tr></table>')

        if stable_holdings:
            parts.append(f'<hr style="border:none;border-top:1px solid {_DZ["line"]};margin:22px 0;">')
            parts.append(_section_label(_stable_section_title(investor_profile=investor_profile)))
            for stable in stable_holdings:
                parts.append(
                    f'<p style="margin:6px 0;"><strong style="color:{_DZ["ink"]};">{escape(stable["ticker"])}</strong>'
                    f'<span style="color:{_DZ["muted"]};">: {escape(stable["why_own_it"])}</span></p>'
                )
    else:
        parts.append(f'<p style="color:{_DZ["muted"]};margin:14px 0;">Your holdings were quiet this week. '
                     'Nothing landed that touched what you&apos;re watching.</p>')
        if stable_holdings:
            parts.append(_section_label(_stable_section_title(investor_profile=investor_profile)))
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
            parts.append(_section_label("Quick thought"))
            parts.append(f'<p style="margin:6px 0;">{escape(quiet_nudge)}</p>')

    # Held up this week — supporting evidence pulled out of the ranked-events
    # feed and rendered with distinct positive framing so users emotionally
    # register "my thesis was validated" instead of "another card to read."
    # Capped hard at one per position so it stays occasional; the goal is
    # balance, not a highlight reel.
    held_up_section = _render_held_up_section(
        held_up_events, investor_profile=investor_profile,
    )
    if held_up_section:
        parts.append(held_up_section)

    parts.append(_section_label("Monitoring receipt"))
    parts.append(f'<p style="color:{_DZ["muted"]};margin:6px 0;">{escape(monitoring_receipt)}</p>')

    # Reviewed-this-week block — the "we looked at these edge cases for you"
    # receipt. Sits right after the monitoring receipt so both quiet-work
    # proofs land together instead of getting scattered across the email.
    reviewed_section = _render_reviewed_but_dropped_section(
        reviewed_but_dropped or [],
        now=now or datetime.now(timezone.utc),
    )
    if reviewed_section:
        parts.append(reviewed_section)

    if observations.get("missing_theses"):
        parts.append(
            f'<p style="margin:6px 0;"><strong style="color:{_DZ["ink"]};">{_missing_section_label(investor_profile=investor_profile)}:</strong> '
            f'<span style="color:{_DZ["muted"]};">{escape(", ".join(observations["missing_theses"]))}</span></p>'
        )
    if observations.get("stale_theses"):
        parts.append(
            f'<p style="margin:6px 0;"><strong style="color:{_DZ["ink"]};">{_stale_section_label(investor_profile=investor_profile)}:</strong> '
            f'<span style="color:{_DZ["muted"]};">{escape(", ".join(observations["stale_theses"]))}</span></p>'
        )
    if observations.get("concentration_warnings"):
        parts.append(
            f'<p style="margin:6px 0;"><strong style="color:{_DZ["ink"]};">Concentration:</strong> '
            f'<span style="color:{_DZ["muted"]};">{escape(observations["concentration_warnings"])}</span></p>'
        )

    # How your calls are playing out — the mirror's weekly payoff, the thing that
    # turns "what changed" into "how your decisions are holding up".
    if mirror:
        reads = mirror.get("reads") or []
        open_bets = mirror.get("open_bets") or []
        if reads or open_bets:
            parts.append(_section_label("How your calls are playing out"))
            for r in reads:
                parts.append(f'<p style="margin:6px 0;">{escape(r["read"])}</p>')
            if open_bets:
                items = []
                for b in open_bets:
                    days = b.get("days_until")
                    when = f"next test in {days}d" if isinstance(days, int) and days >= 0 else "no test scheduled yet"
                    items.append(f"{escape(b['ticker'])} ({escape(when)})")
                parts.append(
                    f'<p style="margin:6px 0;"><strong style="color:{_DZ["ink"]};">Open bets:</strong> '
                    f'<span style="color:{_DZ["muted"]};">{", ".join(items)}</span></p>'
                )

    parts.append(
        f'<p style="margin:24px 0 4px;"><a href="{settings.frontend_url}/dashboard" '
        f'style="color:{_DZ["accent"]};text-decoration:none;font-weight:600;">Open dashboard &rarr;</a></p>'
    )
    return "".join(parts)


def _pick_held_up_events(events_data: list[dict], *, max_per_position: int = 1, max_total: int = 3) -> list[dict]:
    """Extract supporting-verdict events for the 'Held up this week' section.

    Same intent as the API's curate_supporting_items — caps per-position and
    total so the digest never turns into a green highlight reel. Prefers
    stronger severity + claim/signal-bound events."""
    supports = [event for event in events_data if event.get("verdict") == "supports"]
    if not supports:
        return []

    def _score(event: dict) -> tuple[int, int, int]:
        severity_rank = {"thesis_breaking": 3, "warning": 2, "info": 1}.get(event.get("severity") or "info", 0)
        bound = 1 if (event.get("evidence_summary") or event.get("signal_status_text")) else 0
        # Prefer more-recent items when other signals tie, using ticker as a
        # stable secondary — the digest doesn't have per-event created_at
        # sorted here beyond the source order.
        return (severity_rank, bound, 0)

    ordered = sorted(supports, key=_score, reverse=True)
    per_position: dict[str, int] = {}
    picked: list[dict] = []
    for event in ordered:
        if len(picked) >= max_total:
            break
        ticker = event.get("ticker") or ""
        if per_position.get(ticker, 0) >= max_per_position:
            continue
        picked.append(event)
        per_position[ticker] = per_position.get(ticker, 0) + 1
    return picked


def _render_held_up_section(items: list[dict], *, investor_profile: InvestorProfile = None) -> str:
    """Render the 'Held up this week' block. Distinctly positive framing —
    small green accent, no threatening border, no 'Review this reason' CTA."""
    if not items:
        return ""
    header_copy = (
        "This week your thesis was reinforced by:"
        if investor_profile != "hearsay_driven"
        else "This week your reason was reinforced by:"
    )
    parts: list[str] = []
    parts.append(_section_label("Held up this week"))
    parts.append(f'<p style="color:{_DZ["muted"]};margin:6px 0 12px;">{header_copy}</p>')
    positive_border = "#3D6B41"  # same green used in _VERDICT_STYLE["supports"]
    positive_soft = "#E3EDE4"
    for event in items:
        ticker = event["ticker"].replace("_US_EQ", "").replace("_EQ", "")
        assumption = event.get("signal_status_text") or event.get("why_own_it") or ""
        what_happened = event.get("evidence_summary") or event.get("ai_analysis") or event.get("summary") or event.get("title") or ""
        parts.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:10px 0;background:{positive_soft};'
            f'border-left:3px solid {positive_border};">'
            '<tr><td style="padding:12px 14px;">'
        )
        parts.append(
            f'<div style="font-family:{_SERIF};font-size:15px;color:{_DZ["ink"]};margin:0 0 4px;">'
            f'<strong>{escape(ticker)}</strong>'
            f' &mdash; {escape(event.get("title") or "").strip() or "your thesis was reinforced"}'
            f'</div>'
        )
        if what_happened:
            parts.append(
                f'<p style="margin:2px 0 0;color:{_DZ["muted"]};font-size:13px;line-height:1.5;">'
                f'{escape(str(what_happened)[:280])}'
                f'</p>'
            )
        if assumption:
            parts.append(
                f'<p style="margin:6px 0 0;font-family:{_MONO};font-size:10px;letter-spacing:0.1em;'
                f'text-transform:uppercase;color:{_DZ["faint"]};">{escape(str(assumption))}</p>'
            )
        parts.append('</td></tr></table>')
    return "".join(parts)


def _render_reviewed_but_dropped_section(
    items: list[dict],
    *,
    now: datetime,
) -> str:
    """Render the 'reviewed this week' block. Kept intentionally short and
    quiet so it reads as a receipt, not a to-do list. Source labels come
    from services.adjacency.source_label_for_reader so we never leak the
    raw event_type enum (e.g. 'gemini_news') into the email body."""
    if not items:
        return ""
    parts: list[str] = []
    parts.append(_section_label("Reviewed this week"))
    parts.append(
        f'<p style="color:{_DZ["muted"]};margin:6px 0 12px;">'
        "We looked at these against your thesis and decided they didn&apos;t rise to an alert:"
        "</p>"
    )
    for item in items:
        ticker = item["ticker"].replace("_US_EQ", "").replace("_EQ", "")
        published = item.get("published_at")
        when_txt = ""
        if isinstance(published, str) and published:
            try:
                published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
                delta = now - published_dt
                days = delta.days
                if days <= 0:
                    when_txt = "today"
                elif days == 1:
                    when_txt = "yesterday"
                else:
                    when_txt = f"{days}d ago"
            except ValueError:
                when_txt = ""
        source_label = item.get("source_label") or source_label_for_reader(
            item.get("source"), item.get("url"),
        )
        meta_line = source_label + (f" &middot; {when_txt}" if when_txt else "")
        headline_html = f'<span style="color:{_DZ["ink"]};">{escape(item["headline"])}</span>'
        parts.append(
            f'<div style="margin:12px 0 14px;">'
            f'<p style="margin:0 0 3px;font-family:{_SERIF};font-size:14px;">'
            f'<strong>{escape(ticker)}</strong> &mdash; {headline_html}'
            f'</p>'
            f'<p style="margin:0 0 6px;font-family:{_MONO};font-size:10px;letter-spacing:0.1em;'
            f'text-transform:uppercase;color:{_DZ["faint"]};">{escape(meta_line)}</p>'
            f'<p style="margin:0;color:{_DZ["muted"]};font-style:italic;">&ldquo;{escape(item["reason"])}&rdquo;</p>'
            f'</div>'
        )
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


async def build_and_persist_user_digest(
    db,
    user: User,
    *,
    now: datetime,
    period_start: datetime,
    period_end: datetime,
    send_email: bool = True,
    update_streak: bool = True,
) -> "Digest | None":
    """Build, persist, and optionally email one user's digest.

    Shared by the weekly job and the on-demand first digest after onboarding.
    Returns the Digest (added + flushed to the session) or None if the user has
    no holdings. The caller owns commit/rollback so failures can be isolated.

    update_streak should be left True only for the weekly cadence run, which owns
    the consecutive-quiet-weeks counter; on-demand/first builds pass False so they
    don't inflate it.
    """
    user_id = user.id
    upcoming_window = now + timedelta(days=14)

    holdings = await _load_user_holdings(db, user_id)
    if not holdings:
        return None

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
    # Count distinct holdings with alert-shaped events, not raw events — so a
    # position that fired two signals reads as one reason to review, not two.
    # Supporting-verdict events are excluded here: they're rendered separately
    # as reassurance, so counting them as "reasons that need review" would
    # flatly contradict the emotional framing.
    reasons_flagged = len({
        e.get("holding_id") or e.get("ticker")
        for e in events_data
        if e.get("verdict") != "supports"
    })
    headline = _digest_headline(
        reasons_flagged,
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
        reasons_flagged,
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

    # Reviewed-this-week block: items the LLM relevance filter looked at and
    # ruled out. Only meaningful with claims/decompositions, so silently absent
    # when the pipeline hasn't produced any drops. Curation dedupes and picks
    # the strongest 1-2 items, one per holding, skipping tickers already
    # covered by a live alert.
    ticker_by_thesis = {
        str(item["thesis_id"]): item["ticker"]
        for item in holdings_with_theses
        if item.get("thesis_id") and item.get("ticker")
    }
    holding_id_by_thesis = {
        str(item["thesis_id"]): uuid.UUID(item["holding_id"])
        for item in holdings_with_theses
        if item.get("thesis_id") and item.get("holding_id")
    }
    raw_reviewed_drops = await load_reviewed_but_dropped(
        db,
        thesis_ids=thesis_ids,
        ticker_by_thesis=ticker_by_thesis,
        holding_id_by_thesis=holding_id_by_thesis,
        period_start=period_start,
        period_end=period_end,
    )
    reviewed_drops = curate_reviewed_but_dropped(
        raw_reviewed_drops,
        holdings_covered={e["ticker"] for e in events_data},
    )

    if update_streak:
        quiet_streak = _update_quiet_streak(user, has_events=bool(events_data))
    else:
        prefs = user.preferences or {}
        quiet_streak = prefs.get("consecutive_quiet_weeks", 0)

    # Decision mirror — the week's reads + open conviction bets.
    from app.services.decision_mirror import get_mirror_for_digest

    mirror = await get_mirror_for_digest(
        db, user_id, period_start=period_start, period_end=period_end, now=now
    )

    html_content = _render_digest_html(
        holdings_with_theses=holdings_with_theses,
        events_data=events_data,
        observations=observations,
        headline=headline,
        monitoring_receipt=receipt,
        quiet_nudge=quiet_nudge,
        upcoming_earnings=upcoming_earnings if not events_data else None,
        investor_profile=investor_profile,
        mirror=mirror,
        reviewed_but_dropped=reviewed_drops,
        now=now,
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
            "decision_mirror": mirror,
            "reviewed_but_dropped": reviewed_drops,
            "held_up_events": [
                {
                    "ticker": event.get("ticker"),
                    "title": event.get("title"),
                    "evidence_summary": event.get("evidence_summary"),
                    "ai_analysis": event.get("ai_analysis"),
                    "severity": event.get("severity"),
                    "event_type": event.get("event_type"),
                    "signal_status_text": event.get("signal_status_text"),
                }
                for event in _pick_held_up_events(events_data)
            ],
        },
        status="pending",
    )
    db.add(digest)
    await db.flush()

    for e in events:
        e.included_in_digest_id = digest.id

    if html_content and send_email:
        # A graceful failure returns False and we persist a "failed" digest below.
        # A raised exception means we can't trust this user's half-built state, so we
        # let it propagate to the outer handler, which rolls back and moves on.
        sent = await send_digest_email(
            to_email=user.email,
            subject=subject,
            html_content=_wrap_email_shell(html_content, headline=headline, preheader=subject),
        )
        digest.status = "sent" if sent else "failed"
        digest.sent_at = datetime.now(timezone.utc) if sent else None
        if sent:
            from app.services.onboarding import mark_digest_received
            await mark_digest_received(db, user_id)
    elif html_content:
        # Persisted for in-app viewing without sending an email.
        digest.status = "ready"
    else:
        digest.status = "failed"

    return digest


async def run_digest_builder():
    import time
    started = time.monotonic()
    logger.info("Starting weekly digest builder")

    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)

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

                digest = await build_and_persist_user_digest(
                    db,
                    user,
                    now=now,
                    period_start=period_start,
                    period_end=period_end,
                    send_email=True,
                )
                if digest is None:
                    continue

                await db.commit()
                logger.info("Digest %s for user %s", "sent" if digest.status == "sent" else "failed", user_id)

            except Exception:
                await db.rollback()
                logger.exception("Digest build failed for user %s", user_id)
                continue

    elapsed = time.monotonic() - started
    logger.info("Weekly digest builder complete in %.1fs", elapsed)


async def build_first_digest_for_user(user_id: uuid.UUID) -> None:
    """Build a user's first digest on demand, right after onboarding, so they see
    the curated weekly summary in their first session instead of waiting up to a
    week for the Sunday job. This is the product's core value artifact — delaying
    it by days is the difference between "this is useful" and a churned user.

    Background-task safe: opens its own session, only fires if the user has no
    digest yet (truly the first), and never raises. Expects to run AFTER the first
    monitoring pulse so the week's events are already in place.
    """
    try:
        async with async_session() as db:
            user = await db.get(User, user_id)
            if user is None:
                return

            existing = (
                await db.execute(select(Digest.id).where(Digest.user_id == user_id).limit(1))
            ).scalar_one_or_none()
            if existing is not None:
                return  # already has a digest — not the first

            now = datetime.now(timezone.utc)
            digest = await build_and_persist_user_digest(
                db,
                user,
                now=now,
                period_start=now - timedelta(days=7),
                period_end=now,
                send_email=True,  # their first digest: deliver it and validate email
                update_streak=False,  # the weekly job owns the quiet-streak counter
            )
            if digest is not None:
                await db.commit()
                logger.info("First digest %s for user %s", digest.status, user_id)
    except Exception:
        logger.exception("First digest build failed for user %s", user_id)
