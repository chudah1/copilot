from app.services.news_collector import _signal_search_bullets, _to_candidates


def test_signal_search_bullets_include_alternate_phrasings():
    bullets = _signal_search_bullets(["AMD MI350 Instinct ramp commentary"])
    assert "AMD MI350 Instinct ramp commentary" in bullets
    assert "alternate phrasings" in bullets


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
