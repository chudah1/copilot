from unittest.mock import MagicMock, patch

import pytest

from app.services.edgar_extractor import enrich_earnings_candidates


@pytest.mark.asyncio
async def test_enrich_8k_material_filing_adds_item_summary():
    candidate = {
        "event_type": "edgar_8k",
        "description": "SEC 8-K filed by HIMS: Material Agreement, Other Material Event (2026-05-29)",
        "evidence": {
            "url": "https://www.sec.gov/Archives/edgar/data/1773751/000177375126000091/hims-20260529.htm",
            "items": ["1.01", "8.01", "9.01"],
            "description": "Material Agreement, Other Material Event",
        },
    }
    filing_text = """
    ITEM 1.01 Entry into a Material Definitive Agreement.
    On May 28, 2026, Hims & Hers Health, Inc. entered into Amendment No. 3 to its Fifth Third Credit Agreement to permit and facilitate the previously announced acquisition of Eucalyptus.
    The amendment also requires certain foreign subsidiaries acquired in the transaction to join as borrowers or guarantors after closing.

    ITEM 8.01 Other Events.
    The amendment also increases flexibility for restricted subsidiary investments tied to the acquisition through the closing date.
    """

    with patch("app.services.edgar_extractor._fetch_text", return_value=filing_text):
        enriched = await enrich_earnings_candidates([candidate], MagicMock())

    assert len(enriched) == 1
    description = enriched[0]["description"]
    evidence = enriched[0]["evidence"]

    assert "permit and facilitate the previously announced acquisition of Eucalyptus" in description
    assert "foreign subsidiaries acquired in the transaction to join as borrowers or guarantors" in description
    assert evidence["extracted"]["item_summary"] == description
    assert "1.01" in evidence["extracted"]["item_summaries"]

