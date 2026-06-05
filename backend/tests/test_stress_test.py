from unittest.mock import AsyncMock, patch

import pytest

from app.services.stress_test import run_stress_test, _cache


@pytest.fixture(autouse=True)
def clear_cache():
    _cache.clear()
    yield
    _cache.clear()


# --- Behavior 1: no thesis, no market data → non-empty bear_case ---

@pytest.mark.asyncio
async def test_no_thesis_returns_bear_case():
    mock_result = _make_counter_output(bear_case="The stock is overvalued.")

    with patch("app.services.stress_test._generate", new_callable=AsyncMock, return_value=mock_result):
        result = await run_stress_test(
            ticker="NVDA",
            draft_thesis=None,
            company_data=None,
        )

    assert result.bear_case == "The stock is overvalued."
    assert result.ticker == "NVDA"


# --- Behavior 2: with thesis → blind_spots non-empty ---

@pytest.mark.asyncio
async def test_with_thesis_returns_blind_spots():
    mock_result = _make_counter_output(blind_spots=["Ignores competitive moat erosion"])

    with patch("app.services.stress_test._generate", new_callable=AsyncMock, return_value=mock_result):
        result = await run_stress_test(
            ticker="NVDA",
            draft_thesis="I believe NVDA dominates AI chips.",
            company_data=None,
        )

    assert len(result.blind_spots) > 0


# --- Behavior 3: what_to_watch always has at least one signal ---

@pytest.mark.asyncio
async def test_what_to_watch_not_empty():
    mock_result = _make_counter_output(what_to_watch=["Watch gross margin trends quarterly"])

    with patch("app.services.stress_test._generate", new_callable=AsyncMock, return_value=mock_result):
        result = await run_stress_test(
            ticker="AAPL",
            draft_thesis=None,
            company_data=None,
        )

    assert len(result.what_to_watch) >= 1


# --- Behavior 4: same ticker, no thesis, same day → cached on second call ---

@pytest.mark.asyncio
async def test_no_thesis_result_is_cached():
    mock_result = _make_counter_output()
    generate_mock = AsyncMock(return_value=mock_result)

    with patch("app.services.stress_test._generate", generate_mock):
        await run_stress_test("TSLA", None)
        result = await run_stress_test("TSLA", None)

    assert generate_mock.call_count == 1
    assert result.cached is True


# --- Behavior 5: thesis provided → cached per-draft (identical drafts dedupe) ---

@pytest.mark.asyncio
async def test_identical_thesis_is_cached_by_draft():
    from app.services.stress_test import _cache
    _cache.clear()
    generate_mock = AsyncMock(return_value=_make_counter_output())

    with patch("app.services.stress_test._generate", generate_mock):
        r1 = await run_stress_test("RIVN", "I believe in the energy business.")
        r2 = await run_stress_test("RIVN", "I believe in the energy business.")

    assert generate_mock.call_count == 1  # second identical draft served from cache
    assert r1.cached is False
    assert r2.cached is True


@pytest.mark.asyncio
async def test_different_thesis_is_not_a_cache_hit():
    from app.services.stress_test import _cache
    _cache.clear()
    generate_mock = AsyncMock(return_value=_make_counter_output())

    with patch("app.services.stress_test._generate", generate_mock):
        await run_stress_test("LCID", "I believe in the energy business.")
        await run_stress_test("LCID", "A totally different reason about robotaxis.")

    assert generate_mock.call_count == 2  # distinct drafts → distinct cache keys


# --- Behavior 6: company_data passed through to generator ---

@pytest.mark.asyncio
async def test_market_context_passed_to_generator():
    from unittest.mock import MagicMock
    mock_result = _make_counter_output()
    generate_mock = AsyncMock(return_value=mock_result)

    mock_company_data = MagicMock()
    mock_company_data.current_price = 420.0

    with patch("app.services.stress_test._generate", generate_mock):
        await run_stress_test(
            ticker="MSFT",
            draft_thesis=None,
            company_data=mock_company_data,
        )

    call_kwargs = generate_mock.call_args
    assert call_kwargs.kwargs.get("company_data") is mock_company_data


@pytest.mark.asyncio
async def test_result_derives_risk_groups_and_source_notes_from_context():
    from types import SimpleNamespace

    mock_result = _make_counter_output(
        key_risks=[
            "Valuation leaves no margin of safety",
            "Competition could pressure margins",
            "Tariff exposure could hit demand",
        ]
    )
    mock_company_data = SimpleNamespace(
        current_price=420.0,
        pe_ratio=32.5,
        revenue_growth_yoy=0.18,
        earnings_growth_yoy=0.22,
        recent_earnings_surprise_pct=7.0,
        news_items=[],
        earnings_call=None,
    )

    with patch("app.services.stress_test._generate", new_callable=AsyncMock, return_value=mock_result):
        result = await run_stress_test(
            ticker="MSFT",
            draft_thesis="AI adoption keeps demand high.",
            company_data=mock_company_data,
        )

    assert result.risk_groups
    assert any(group.category == "Financial risk" for group in result.risk_groups)
    assert any(group.category == "Competitive risk" for group in result.risk_groups)
    assert result.source_notes
    assert any(note.label == "Valuation" for note in result.source_notes)
    assert any(note.label == "Revenue growth" for note in result.source_notes)


# --- helpers ---

def _make_counter_output(
    bear_case="Bears argue valuation is stretched.",
    key_risks=None,
    blind_spots=None,
    what_to_watch=None,
):
    from app.services.stress_test import StressTestOutput
    return StressTestOutput(
        bear_case=bear_case,
        key_risks=key_risks or ["Competition risk", "Margin pressure"],
        blind_spots=blind_spots or ["Regulatory exposure not addressed"],
        what_to_watch=what_to_watch or ["Watch gross margin trend"],
    )
