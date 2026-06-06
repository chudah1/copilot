"""Tests for the thesis vagueness gate (Step 2: the hype-buyer climb).

The gate decides whether a thesis is too vague to monitor well and should be
grounded (stress-test + Socratic follow-ups) before being relied on.
"""
from unittest.mock import AsyncMock, patch

from app.services.ai_thesis import (
    SynthesisOutput,
    _detect_monitorable_drivers,
    assess_thesis_vagueness,
)


# --- pure gate logic (no IO, no API keys) ---------------------------------

def test_sharp_thesis_is_not_vague():
    a = assess_thesis_vagueness(
        "Gross margin will stay above 60% thanks to durable pricing power and recurring revenue.",
        what_would_change_my_mind="If margins fall below 55% for two consecutive quarters.",
    )
    assert a.is_vague is False
    assert "quality" in a.detected_drivers
    assert a.suggested_questions == []


def test_too_short_is_vague():
    a = assess_thesis_vagueness("They make iPhones.")
    assert a.is_vague is True
    assert "too_short" in a.reasons


def test_terse_but_precise_thesis_with_driver_is_not_vague():
    # C1: a short thesis that nonetheless names a concrete monitorable driver
    # must NOT be flagged — shortness only counts when there's no driver.
    a = assess_thesis_vagueness("Margins above 60%, FCF growing 20%.")
    assert a.is_vague is False
    assert "quality" in a.detected_drivers


def test_generic_boilerplate_with_a_driver_is_not_vague():
    # Regression: AI-drafted/sharpened theses naturally use boilerplate like
    # "business model" / "market position", which used to flag the help branch as
    # weak on its own. "generic" is now a SOFT signal — when a monitorable driver
    # is also present, the thesis stays watchable.
    a = assess_thesis_vagueness(
        "I own this for its durable business model and strong market position, "
        "driven by AI demand and expanding margins.",
    )
    assert "generic" in a.reasons          # boilerplate still detected/recorded
    assert a.detected_drivers              # but a real driver is present
    assert a.is_vague is False             # so it is NOT flagged vague


def test_generic_boilerplate_without_a_driver_is_still_vague():
    # The other side of the guard: pure boilerplate with no monitorable driver
    # remains vague.
    a = assess_thesis_vagueness(
        "I own this because of its strong market position and solid business model.",
    )
    assert "generic" in a.reasons
    assert a.is_vague is True


def test_rebutting_hype_with_a_driver_is_not_vague():
    # Regression: AI drafts often *rebut* hype ("this isn't just hype, revenue
    # grew 85%"). A bare hearsay noun used in passing is now soft — with a real
    # driver present, the thesis stays watchable.
    a = assess_thesis_vagueness(
        "This isn't just hype — AI inference demand drove 85% revenue growth and "
        "margins expanded to 70%.",
    )
    assert "hearsay" in a.reasons       # the word "hype" is still detected
    assert a.detected_drivers           # but real drivers are present
    assert a.is_vague is False          # so it is NOT flagged


def test_explicit_chatter_framing_stays_vague_even_with_metrics():
    # The framing "everyone was talking about" is genuine chatter-as-reason and
    # stays a strong signal even when metrics are mentioned in passing.
    a = assess_thesis_vagueness(
        "Everyone was talking about its revenue growth and margins.",
    )
    assert a.is_vague is True


def test_bare_hearsay_noun_without_driver_is_still_vague():
    a = assess_thesis_vagueness(
        "I bought it for the momentum and the buzz around the name.",
    )
    assert "hearsay" in a.reasons
    assert a.is_vague is True


def test_cashflow_synonyms_detected_as_quality():
    # M5: retail users write "cashflow"/"FCF", not just "cash flow".
    assert "quality" in _detect_monitorable_drivers("strong cashflow and FCF growth")


def test_sell_question_always_present_despite_many_drivers():
    # M6: clarify + two driver questions would otherwise fill the 3-slot cap and
    # drop the mandatory sell question.
    a = assess_thesis_vagueness(
        "Everyone was talking about its revenue growth and margins.",
        company="Apple",
    )
    assert a.is_vague is True
    assert any("sell" in q.lower() for q in a.suggested_questions)
    assert len(a.suggested_questions) <= 3


def test_hearsay_is_vague():
    a = assess_thesis_vagueness(
        "Everyone was talking about it and I heard it is the next big thing to own."
    )
    assert a.is_vague is True
    assert "hearsay" in a.reasons


def test_vague_language_is_vague():
    a = assess_thesis_vagueness("A friend recommended it.")
    assert a.is_vague is True
    assert "vague_language" in a.reasons


def test_qualitative_thesis_respected_for_thesis_driven():
    # Medium length, no hearsay, no *monitorable metric* driver — but a legitimate
    # qualitative reason. A thesis-driven investor should not be forced to ground.
    text = "The company has a durable competitive moat and a trusted brand that keeps customers loyal."
    a = assess_thesis_vagueness(text, investor_profile="thesis_driven")
    assert a.is_vague is False
    assert "no_monitorable_driver" in a.reasons  # soft signal still recorded


def test_same_qualitative_thesis_grounded_for_hearsay_driven():
    # An explicit hearsay-driven user with no monitorable driver IS grounded.
    text = "The company has a durable competitive moat and a trusted brand that keeps customers loyal."
    a = assess_thesis_vagueness(text, investor_profile="hearsay_driven")
    assert a.is_vague is True


def test_suggested_questions_reference_company_and_include_sell_question():
    a = assess_thesis_vagueness("They make iPhones.", company="Apple")
    assert a.suggested_questions
    assert any("Apple" in q for q in a.suggested_questions)
    assert any("sell" in q.lower() for q in a.suggested_questions)
    assert len(a.suggested_questions) <= 3


def test_driver_detection_word_boundary_avoids_false_positive():
    # "ai" must NOT match inside "domain"; a false positive would hide vagueness.
    assert "theme" not in _detect_monitorable_drivers("we have deep domain expertise")
    # but a real standalone "AI" is detected
    assert "theme" in _detect_monitorable_drivers("AI demand is enormous")


def test_driver_detection_growth_and_quality():
    drivers = _detect_monitorable_drivers("revenue growth stays strong and margins expand")
    assert "growth" in drivers
    assert "quality" in drivers


# --- endpoint wiring -------------------------------------------------------

async def test_synthesize_flags_grounding_for_vague_answer(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    assert holding.status_code == 201

    mock_output = SynthesisOutput(
        why_own_it="A rough AI idea, framed as durable compute demand.",
        must_remain_true="Demand stays strong.",
        what_would_change_my_mind="If growth stops showing up.",
        ai_summary="Summary.",
        interpretation={"labels": [], "monitorability": "low", "watch_hints": [], "proxy_signals": [], "ambiguity_note": ""},
    )
    with patch("app.routes.onboarding.synthesize_thesis_from_qa", new_callable=AsyncMock, return_value=mock_output):
        response = await client.post(
            "/api/onboarding/synthesize",
            json={
                "holding_id": holding.json()["id"],
                "investor_profile": "hearsay_driven",
                "question1": "Why did you buy it?",
                "answer1": "Everyone was talking about it.",
                "question2": "What would change your mind?",
                "answer2": "Not sure.",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["needs_grounding"] is True
    assert data["suggested_questions"]
    assert "hearsay" in data["grounding_reasons"]


async def test_synthesize_no_grounding_for_sharp_answer(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    mock_output = SynthesisOutput(
        why_own_it="x",
        must_remain_true="y",
        what_would_change_my_mind="z",
        ai_summary="s",
        interpretation={"labels": [], "monitorability": "high", "watch_hints": [], "proxy_signals": [], "ambiguity_note": ""},
    )
    with patch("app.routes.onboarding.synthesize_thesis_from_qa", new_callable=AsyncMock, return_value=mock_output):
        response = await client.post(
            "/api/onboarding/synthesize",
            json={
                "holding_id": holding.json()["id"],
                "investor_profile": "thesis_driven",
                "question1": "Why did you buy it?",
                "answer1": "Margins will stay above 60% on pricing power and revenue keeps growing double digits.",
                "question2": "What would change your mind?",
                "answer2": "If margins fall below 55% for two quarters.",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["needs_grounding"] is False
    assert data["suggested_questions"] == []
    assert data["grounding_reasons"] == []  # M7: reasons not leaked when not grounding
