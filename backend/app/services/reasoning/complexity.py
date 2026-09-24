"""
Rule-based complexity classifier for thesis decomposition requests.

Scores a thesis payload 0-7 on richness signals. Score >= 4 routes to the
expensive tier (Terra); below 4 routes to the fast tier (Luna).
"""
import re


def score_thesis_complexity(payload: dict) -> int:
    why = payload.get("why_own_it") or ""
    must = payload.get("must_remain_true") or ""
    change = payload.get("what_would_change_my_mind") or ""

    score = 0

    # How many of the three fields are meaningfully filled (>10 chars)
    score += sum(1 for f in (why, must, change) if len(f.strip()) > 10)

    combined = f"{why} {must} {change}"
    word_count = len(combined.split())

    if word_count > 80:
        score += 1

    # Explicit thresholds: "70%", "$50", "20x", "2 billion"
    if re.search(
        r"\d+\.?\d*\s*%|\$\d|\d+x\b|\d+\s*(?:billion|million|percent)",
        combined,
        re.IGNORECASE,
    ):
        score += 1

    # Comparison language implying a measurable bar
    if re.search(
        r"\b(?:above|below|more than|less than|exceeds?|drops?|falls?|stays? (?:above|below)|grows? (?:above|over))\b",
        combined,
        re.IGNORECASE,
    ):
        score += 1

    # Ticker-like token that could be a competitor or benchmark (e.g. "AMD", "SPY")
    if re.search(r"\b[A-Z]{2,5}\b", combined):
        score += 1

    return score


def classify_complexity(payload: dict) -> str:
    """Return 'cheap' or 'expensive' for use in provider selection."""
    return "expensive" if score_thesis_complexity(payload) >= 4 else "cheap"
