from app.services.news_collector import (
    _select_focused_signal_labels,
    _signal_search_bullets,
    _to_candidates,
)


def test_signal_search_bullets_include_alternate_phrasings():
    bullets = _signal_search_bullets(["AMD MI350 Instinct ramp commentary"])
    assert "AMD MI350 Instinct ramp commentary" in bullets
    assert "alternate phrasings" in bullets


def test_signal_search_bullets_include_claim_and_rationale_context():
    bullets = _signal_search_bullets(
        [
            {
                "label": "AMD customer deployment commentary",
                "claim_text": "AMD management describes customer deployments as strengthening.",
                "rationale": "Deployments validate real customer adoption.",
            }
        ]
    )

    assert "claim:" in bullets
    assert "why it matters:" in bullets


def test_select_focused_signal_labels_prefers_specific_qualitative_branches():
    labels = _select_focused_signal_labels(
        [
            "AMD data center revenue growth",
            "AMD AI accelerator demand commentary",
            "AMD customer deployment commentary",
            "AMD gross margin trend",
        ]
    )

    label_names = [entry["label"] for entry in labels]

    assert "AMD AI accelerator demand commentary" in label_names
    assert "AMD customer deployment commentary" in label_names
    assert len(labels) <= 3


def test_to_candidates_drops_roundup_noise():
    candidates = _to_candidates(
        [
            {
                "headline": "Why Intel, AMD, Arm, and Other Artificial Intelligence (AI) Stocks Popped Today",
                "summary": "A broad sector roundup discussing several chip stocks and the AI trade.",
                "url": "https://example.com/roundup",
                "date": "2026-06-13",
                "relevant_signals": ["AMD AI beneficiary news flow"],
                "relevance": "medium",
            },
            {
                "headline": "AMD says data center demand remains strong",
                "summary": "Management highlighted AI demand and durable customer traction.",
                "url": "https://example.com/amd-specific",
                "date": "2026-06-13",
                "relevant_signals": ["AMD AI beneficiary news flow"],
                "relevance": "high",
            },
        ]
    )

    assert len(candidates) == 1
    assert candidates[0]["evidence"]["headline"] == "AMD says data center demand remains strong"


def test_to_candidates_drops_low_relevance_and_requires_signal_match():
    candidates = _to_candidates(
        [
            {
                "headline": "AMD appears in a broad AI market note",
                "summary": "The company is only one of many names in the piece.",
                "url": "https://example.com/low-relevance",
                "date": "2026-06-13",
                "relevant_signals": ["AMD AI beneficiary news flow"],
                "relevance": "low",
            },
            {
                "headline": "AMD mentioned in passing",
                "summary": "No explicit matched signal was identified.",
                "url": "https://example.com/no-signal",
                "date": "2026-06-13",
                "relevant_signals": [],
                "relevance": "high",
            },
        ]
    )

    assert candidates == []


def test_to_candidates_adds_topic_context_from_relevant_signals():
    candidates = _to_candidates(
        [
            {
                "headline": "AMD says MI350 ramp remains on track",
                "summary": "Management highlighted strong accelerator demand.",
                "url": "https://example.com/mi350",
                "date": "2026-06-13",
                "relevant_signals": ["AMD MI350 Instinct ramp commentary"],
                "relevance": "high",
            }
        ]
    )

    assert len(candidates) == 1
    evidence = candidates[0]["evidence"]
    assert evidence["matched_topics"]
    assert "AMD MI350 Instinct ramp commentary" in evidence["topic_context"]


def test_to_candidates_dedupes_duplicate_articles_from_overlapping_searches():
    candidates = _to_candidates(
        [
            {
                "headline": "AMD says MI350 ramp remains on track",
                "summary": "Management highlighted strong accelerator demand.",
                "url": "https://example.com/mi350",
                "date": "2026-06-13",
                "relevant_signals": ["AMD MI350 Instinct ramp commentary"],
                "relevance": "high",
            },
            {
                "headline": "AMD says MI350 ramp remains on track",
                "summary": "Management highlighted strong accelerator demand.",
                "url": "https://example.com/mi350",
                "date": "2026-06-13",
                "relevant_signals": ["AMD AI accelerator demand commentary"],
                "relevance": "high",
            },
        ]
    )

    assert len(candidates) == 1
