"""
Prompt quality gate for event classification (ai_monitor).

Skipped in default pytest runs. Invoke with:
  pytest tests/eval/test_monitor_evals.py -m eval -v

Requires ANTHROPIC_API_KEY (or OPENAI_API_KEY for the judge fallback).

Fails if:
  - Classification call fails on any case
  - Severity label accuracy drops below MIN_SEVERITY_ACCURACY
  - Average judge score drops below MIN_AVG_SCORE
"""
import os

import pytest

from app.config import settings
from tests.eval.monitor_runner import run_eval, save_results

MIN_SEVERITY_ACCURACY = 0.90
MIN_AVG_SCORE = 8.0
MIN_CLASSIFICATION_SUCCESS_RATE = 1.0


def _require_api_keys() -> None:
    if not settings.anthropic_api_key and not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY or OPENAI_API_KEY required for monitor eval tests")


@pytest.mark.eval
@pytest.mark.asyncio
async def test_monitor_classification_quality():
    """Live monitor prompt must match expected severity on the eval dataset."""
    _require_api_keys()

    results = await run_eval(prompt_version="ci")

    successes = [r for r in results if r["classification_success"]]
    success_rate = len(successes) / len(results) if results else 0
    assert success_rate >= MIN_CLASSIFICATION_SUCCESS_RATE, (
        f"Classification success rate {success_rate:.0%} is below "
        f"{MIN_CLASSIFICATION_SUCCESS_RATE:.0%}. "
        f"Failed: {[r['id'] for r in results if not r['classification_success']]}"
    )

    severity_matches = sum(1 for r in successes if r["severity_match"])
    severity_accuracy = severity_matches / len(successes) if successes else 0
    mismatches = [r["id"] for r in successes if not r["severity_match"]]
    assert severity_accuracy >= MIN_SEVERITY_ACCURACY, (
        f"Severity accuracy {severity_accuracy:.0%} is below {MIN_SEVERITY_ACCURACY:.0%}. "
        f"Mismatches: {mismatches}"
    )

    avg = sum(r["normalised_10"] for r in successes) / len(successes)
    assert avg >= MIN_AVG_SCORE, (
        f"Average judge score {avg:.1f} is below minimum {MIN_AVG_SCORE}. "
        f"Lowest: {sorted(successes, key=lambda r: r['normalised_10'])[:3]}"
    )

    save_results(results, "ci")
