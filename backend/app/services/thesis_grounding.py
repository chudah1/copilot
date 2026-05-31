"""Hype-buyer 'climb': turn a vague thesis into a grounded, measurable one.

This is the connective tissue for Step 3. It runs the vagueness gate and, only
when grounding is warranted, stress-tests the position so the onboarding UI gets
a single payload: the verdict, the Socratic follow-ups to ask, and the bear case
+ what-to-watch that turn chatter into something monitorable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.ai_thesis import assess_thesis_vagueness
from app.services.market_data import _normalize_ticker, fetch_company_data
from app.services.stress_test import CandidateSignal, run_stress_test

logger = logging.getLogger(__name__)


@dataclass
class GroundingPayload:
    needs_grounding: bool
    reasons: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    bear_case: str | None = None
    key_risks: list[str] = field(default_factory=list)
    what_to_watch: list[str] = field(default_factory=list)
    candidate_signals: list[CandidateSignal] = field(default_factory=list)


async def build_grounding_payload(
    *,
    ticker: str,
    why_own_it: str | None,
    what_would_change_my_mind: str | None = None,
    investor_profile: str | None = None,
    company_name: str | None = None,
) -> GroundingPayload:
    """Assess a thesis and, only if it's too vague to monitor, ground it via the
    stress-test. A sharp thesis returns needs_grounding=False and does no extra
    work (no stress-test call)."""
    assessment = assess_thesis_vagueness(
        why_own_it,
        what_would_change_my_mind=what_would_change_my_mind,
        investor_profile=investor_profile,
        company=company_name or ticker,
    )
    if not assessment.is_vague:
        return GroundingPayload(needs_grounding=False)

    # Don't spend a paid LLM stress-test on an empty/blank thesis — there's
    # nothing to stress-test yet. Return the verdict + Socratic questions so the
    # UI can prompt the user to actually write a reason first.
    if not (why_own_it or "").strip():
        return GroundingPayload(
            needs_grounding=True,
            reasons=assessment.reasons,
            suggested_questions=assessment.suggested_questions,
        )

    # Vague — ground it. The stress-test has its own no-key fallback, and
    # run_stress_test/generate_stress_test_analysis wrap their LLM call in a
    # try/except returning that fallback, so this cannot raise on a key/LLM
    # failure — the climb never hard-fails. (fetch_company_data is best-effort;
    # we swallow its errors and pass None.)
    company_data = None
    try:
        company_data = await fetch_company_data(ticker)
    except Exception as exc:  # never let grounding hard-fail the climb
        logger.warning("Grounding: market data unavailable for %s: %s", ticker, exc)

    stress = await run_stress_test(
        # Normalise the broker ticker (e.g. NVDA_US_EQ -> NVDA, ASMLA_EQ ->
        # ASML.AS) so the bear case references a real symbol, not the T212 code.
        ticker=_normalize_ticker(ticker),
        draft_thesis=why_own_it,
        company_data=company_data,
    )

    # A thesis-driven user already reasons in metrics, and their decomposition
    # produces the numeric watches from their own words — so the stress-test's
    # numeric candidate signals are largely redundant for them (confirmed by the
    # decomposition-vs-stress-test audit). Offer them only the qualitative
    # news_watch signals: the blind-spot layer they can't derive themselves.
    # Hype/hearsay users keep the full set — it is their whole on-ramp.
    candidate_signals = stress.candidate_signals
    if investor_profile == "thesis_driven":
        news_only = [c for c in candidate_signals if c.signal_type == "news_watch"]
        candidate_signals = news_only or candidate_signals  # never leave them empty-handed

    return GroundingPayload(
        needs_grounding=True,
        reasons=assessment.reasons,
        suggested_questions=assessment.suggested_questions,
        bear_case=stress.bear_case,
        key_risks=stress.key_risks,
        what_to_watch=stress.what_to_watch,
        candidate_signals=candidate_signals,
    )
