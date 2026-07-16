import pytest

from app.services.news_collector import (
    _parse_news_response_tolerant,
    filter_live_url_candidates,
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
        ],
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
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
        ],
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
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
        ],
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
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
        ],
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
    )

    assert len(candidates) == 1


def test_to_candidates_drops_off_ticker_articles_from_model_output():
    candidates = _to_candidates(
        [
            {
                "headline": "NVIDIA Corporation $NVDA Position Cut by ROI Financial Advisors LLC",
                "summary": "ROI Financial Advisors reduced its stake in NVIDIA after strong quarterly results.",
                "url": "https://example.com/nvda-only",
                "date": "2026-06-13",
                "relevant_signals": ["AMD Radeon consumer GPU share"],
                "relevance": "high",
            },
            {
                "headline": "AMD says Radeon channel demand keeps improving",
                "summary": "Management pointed to better gamer demand and healthier sell-through.",
                "url": "https://example.com/amd-radeon",
                "date": "2026-06-13",
                "relevant_signals": ["AMD Radeon consumer GPU share"],
                "relevance": "high",
            },
        ],
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
    )

    assert len(candidates) == 1
    assert candidates[0]["evidence"]["headline"] == "AMD says Radeon channel demand keeps improving"


def test_parse_news_response_tolerant_strict_path():
    """Well-formed JSON is parsed normally — tolerance does not change strict behavior."""
    payload = '{"articles": [{"headline": "X", "url": "u", "date": "2026-06-01", "summary": "s", "relevant_signals": ["sig"], "relevance": "high"}]}'
    items = _parse_news_response_tolerant(payload)
    assert len(items) == 1
    assert items[0]["headline"] == "X"


def test_parse_news_response_tolerant_salvages_truncated_mid_summary():
    """Gemini sometimes truncates structured output mid-string when nearing
    the token limit. We must salvage the complete articles before the cut
    rather than discarding the entire batch and writing a monitoring_gap."""
    payload = (
        '{"articles": [\n'
        '  {"headline": "First", "url": "u1", "date": "2026-06-01", "summary": "complete", "relevant_signals": ["a"], "relevance": "high"},\n'
        '  {"headline": "Second", "url": "u2", "date": "2026-06-02", "summary": "also complete", "relevant_signals": ["b"], "relevance": "medium"},\n'
        '  {"headline": "Third", "url": "u3", "date": "2026-06-03", "summary": "truncated mid stri'
    )
    items = _parse_news_response_tolerant(payload)
    assert len(items) == 2, f"Should salvage two complete articles, got {len(items)}"
    assert items[0]["headline"] == "First"
    assert items[1]["headline"] == "Second"


def test_parse_news_response_tolerant_returns_empty_on_unsalvageable_garbage():
    """If we can't find a single complete article, return empty instead of
    raising. Empty is a legitimate signal (no news) — the caller treats it
    the same as a genuinely empty response."""
    assert _parse_news_response_tolerant("") == []
    assert _parse_news_response_tolerant("not json at all") == []
    assert _parse_news_response_tolerant('{"articles": [{"truncated mid first article') == []


def test_parse_news_response_tolerant_accepts_bare_array():
    """Some Gemini calls return the articles list directly without the wrapper."""
    payload = '[{"headline": "X", "url": "u", "date": "2026-06-01", "summary": "s", "relevant_signals": ["sig"], "relevance": "high"}]'
    items = _parse_news_response_tolerant(payload)
    assert len(items) == 1


def test_parse_news_response_tolerant_skips_non_dict_array_entries():
    """Defensive: if the array contains non-object entries, drop them."""
    payload = '{"articles": [{"headline": "X", "url": "u", "date": "2026-06-01", "summary": "s", "relevant_signals": ["sig"], "relevance": "high"}, "junk", 42, null]}'
    items = _parse_news_response_tolerant(payload)
    assert len(items) == 1
    assert items[0]["headline"] == "X"


# ── URL liveness gate ────────────────────────────────────────────────────────


def _candidate(url):
    return {
        "event_type": "gemini_news",
        "description": "Headline — summary",
        "evidence": {"headline": "Headline", "url": url},
    }


def _transport(handler):
    import httpx

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_liveness_gate_keeps_resolving_urls_and_stores_final_url():
    import httpx

    def handler(request):
        if request.url.path == "/redirect":
            return httpx.Response(301, headers={"location": "https://real.example/article"})
        return httpx.Response(200)

    survivors = await filter_live_url_candidates(
        [_candidate("https://real.example/redirect")],
        transport=_transport(handler),
    )

    assert len(survivors) == 1
    assert survivors[0]["evidence"]["url"] == "https://real.example/article"


@pytest.mark.asyncio
async def test_liveness_gate_drops_404_urls():
    import httpx

    survivors = await filter_live_url_candidates(
        [_candidate("https://real.example/invented-path"), _candidate("https://real.example/live")],
        transport=_transport(
            lambda request: httpx.Response(404 if "invented" in request.url.path else 200)
        ),
    )

    assert [c["evidence"]["url"] for c in survivors] == ["https://real.example/live"]


@pytest.mark.asyncio
async def test_liveness_gate_drops_unreachable_urls():
    import httpx

    def handler(request):
        raise httpx.ConnectError("DNS failure")

    survivors = await filter_live_url_candidates(
        [_candidate("https://invented-domain.example/article")],
        transport=_transport(handler),
    )

    assert survivors == []


@pytest.mark.asyncio
async def test_liveness_gate_drops_items_without_url():
    survivors = await filter_live_url_candidates(
        [_candidate(None)],
        transport=_transport(lambda request: (_ for _ in ()).throw(AssertionError("no request expected"))),
    )

    assert survivors == []


@pytest.mark.asyncio
async def test_liveness_gate_passes_bot_blocked_urls():
    import httpx

    survivors = await filter_live_url_candidates(
        [_candidate("https://paywalled.example/article")],
        transport=_transport(lambda request: httpx.Response(403)),
    )

    assert len(survivors) == 1


@pytest.mark.asyncio
async def test_liveness_gate_stabilizes_article_id_and_dedupes_by_final_url():
    """The same article reached via two different per-run redirect URLs must
    collapse to one candidate with a URL-stable article_id, so story anchors
    stop churning across passes."""
    import hashlib

    import httpx

    def handler(request):
        return httpx.Response(301, headers={"location": "https://real.example/article"}) if "redirect" in request.url.path else httpx.Response(200)

    a = _candidate("https://vertex.example/redirect-run1")
    b = _candidate("https://vertex.example/redirect-run2")
    a["evidence"]["headline"] = b["evidence"]["headline"] = "Headline"
    a["evidence"]["article_id"] = "run1hash"
    b["evidence"]["article_id"] = "run2hash"

    survivors = await filter_live_url_candidates([a, b], transport=_transport(handler))

    assert len(survivors) == 1
    expected = hashlib.sha256("Headlinehttps://real.example/article".encode()).hexdigest()[:16]
    assert survivors[0]["evidence"]["article_id"] == expected
