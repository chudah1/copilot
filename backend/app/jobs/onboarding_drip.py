import logging
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select

from app.database import async_session
from app.models.holding import Holding
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.user import User
from app.services.email import send_onboarding_email

logger = logging.getLogger(__name__)

CURRENT_THESIS_STATUSES = ["draft", "active", "needs_review"]


def _day1_html(holding_name: str, signal_count: int, uncovered_count: int, earnings_date: str | None) -> str:
    parts = [
        f"<h2>Your reason for {escape(holding_name)} is now being monitored</h2>",
        f"<p>We're watching <strong>{signal_count} signal{'s' if signal_count != 1 else ''}</strong> "
        f"for your {escape(holding_name)} position.</p>",
    ]
    if earnings_date:
        parts.append(f"<p>Next earnings date: <strong>{escape(earnings_date)}</strong>.</p>")
    if uncovered_count > 0:
        noun = "holding" if uncovered_count == 1 else "holdings"
        parts.append(
            f"<p>You have <strong>{uncovered_count} {noun}</strong> without a reason. "
            f"Holdings without a thesis are blind spots — monitoring can't tell you what matters for them.</p>"
        )
    parts.append('<p><a href="/dashboard">→ Open dashboard</a></p>')
    return "".join(parts)


def _day5_html(uncovered_tickers: list[str]) -> str:
    parts = [
        "<h2>Some of your holdings have no reason — here's why that matters</h2>",
        "<p>Without a thesis, monitoring can't tell you what matters for each position. "
        "You're flying blind on these holdings:</p>",
        "<ul>",
    ]
    for ticker in uncovered_tickers[:6]:
        parts.append(f"<li><strong>{escape(ticker)}</strong></li>")
    parts.append("</ul>")
    parts.append(
        "<p>Writing a reason takes two minutes. It tells you — and the system — "
        "exactly what would make you sell.</p>"
    )
    parts.append('<p><a href="/dashboard">→ Add a reason now</a></p>')
    return "".join(parts)


async def run_onboarding_drip():
    logger.info("Starting onboarding drip job")
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    async with async_session() as db:
        states_result = await db.execute(
            select(OnboardingState).where(OnboardingState.onboarding_completed_at.is_(None))
        )
        states = states_result.scalars().all()

        for state in states:
            try:
                if state.portfolio_connected_at is None:
                    continue

                user_result = await db.execute(select(User).where(User.id == state.user_id))
                user = user_result.scalar_one_or_none()
                if user is None:
                    continue
                if not (user.preferences or {}).get("email_enabled", True):
                    continue

                holdings_result = await db.execute(
                    select(Holding).where(Holding.user_id == state.user_id)
                )
                holdings = holdings_result.scalars().all()
                holdings_count = len(holdings)
                if holdings_count == 0:
                    continue

                theses_result = await db.execute(
                    select(Thesis).where(
                        Thesis.user_id == state.user_id,
                        Thesis.status.in_(CURRENT_THESIS_STATUSES),
                    )
                )
                theses = theses_result.scalars().all()
                thesis_holding_ids = {str(t.holding_id) for t in theses}

                uncovered = [h for h in holdings if str(h.id) not in thesis_holding_ids]
                coverage = len(theses) / holdings_count

                days_since_connected = (now - state.portfolio_connected_at.replace(tzinfo=timezone.utc)).days

                # Max 1 email per day
                if state.last_email_sent_at is not None:
                    last_sent = state.last_email_sent_at.replace(tzinfo=timezone.utc)
                    if last_sent >= day_ago:
                        continue

                sent = False

                # Day 1: first reason is being monitored
                if (
                    not sent
                    and state.day1_email_sent_at is None
                    and state.first_reason_written_at is not None
                    and days_since_connected >= 1
                ):
                    first_thesis = next(iter(theses), None)
                    if first_thesis is not None:
                        first_holding = next(
                            (h for h in holdings if h.id == first_thesis.holding_id), None
                        )
                        # Count confirmed signals for this thesis
                        signal_count = 0
                        decomp_result = await db.execute(
                            select(ThesisDecomposition).where(
                                ThesisDecomposition.thesis_id == first_thesis.id,
                                ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
                            )
                        )
                        decomp = decomp_result.scalar_one_or_none()
                        if decomp is not None:
                            from sqlalchemy import func as sqlfunc
                            from app.models.thesis_claim import ThesisClaim
                            from app.models.thesis_entity import ThesisEntity
                            from app.models.thesis_signal import ThesisSignal
                            count_result = await db.execute(
                                select(sqlfunc.count()).select_from(ThesisSignal)
                                .join(ThesisEntity, ThesisSignal.entity_id == ThesisEntity.id)
                                .join(ThesisClaim, ThesisEntity.claim_id == ThesisClaim.id)
                                .where(
                                    ThesisClaim.decomposition_id == decomp.id,
                                    ThesisSignal.user_confirmed == True,
                                    ThesisSignal.active == True,
                                )
                            )
                            signal_count = count_result.scalar() or 0

                        holding_name = first_holding.name if first_holding else "your holding"
                        subject = f"Your reason for {holding_name} is now being monitored"
                        html = _day1_html(
                            holding_name=holding_name,
                            signal_count=signal_count,
                            uncovered_count=len(uncovered),
                            earnings_date=None,
                        )
                        ok = await send_onboarding_email(user.email, subject, html)
                        if ok:
                            state.day1_email_sent_at = now
                            state.last_email_sent_at = now
                            sent = True

                # Day 5: nudge to add more reasons (only if <50% coverage)
                if (
                    not sent
                    and state.day5_email_sent_at is None
                    and days_since_connected >= 5
                    and coverage < 0.5
                    and uncovered
                ):
                    uncovered_tickers = [h.ticker for h in uncovered]
                    uncovered_count = len(uncovered_tickers)
                    noun = "holdings" if uncovered_count != 1 else "holding"
                    subject = f"{uncovered_count} of your {noun} {'have' if uncovered_count != 1 else 'has'} no reason — here's why that matters"
                    html = _day5_html(uncovered_tickers)
                    ok = await send_onboarding_email(user.email, subject, html)
                    if ok:
                        state.day5_email_sent_at = now
                        state.last_email_sent_at = now
                        sent = True

                # Mark complete if coverage ≥ 50%
                if coverage >= 0.5 and state.onboarding_completed_at is None:
                    state.onboarding_completed_at = now

                await db.commit()

            except Exception as exc:
                logger.error(f"Onboarding drip failed for user {state.user_id}: {exc}")
                continue

    logger.info("Onboarding drip job complete")
