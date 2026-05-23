"""
Prompt quality gate — runs the full eval suite against the decomposition pipeline.

Skipped in normal test runs. Invoke with:
  pytest tests/eval/test_decomposition_evals.py -m eval -v

Fails if:
  - Average score across all 20 cases drops below MIN_AVG_SCORE
  - Any individual case that previously scored above REGRESSION_FLOOR now scores below it
  - Decomposition success rate drops below MIN_SUCCESS_RATE
"""
import json
from pathlib import Path

import pytest

from tests.eval.runner import run_eval, save_results

MIN_AVG_SCORE = 6.0       # average 0-10 across all cases
REGRESSION_FLOOR = 4.0    # any single case below this is a hard failure
MIN_SUCCESS_RATE = 0.80   # at least 80% of cases must decompose successfully

RESULTS_DIR = Path(__file__).parent / "results"


def _latest_baseline() -> dict | None:
    """Load the most recent saved results to use as regression baseline."""
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


@pytest.mark.eval
@pytest.mark.asyncio
async def test_decomposition_prompt_quality():
    """Average eval score must meet the minimum threshold."""
    results = await run_eval(prompt_version="ci")

    successes = [r for r in results if r["decomposition_success"]]
    success_rate = len(successes) / len(results) if results else 0
    assert success_rate >= MIN_SUCCESS_RATE, (
        f"Decomposition success rate {success_rate:.0%} is below {MIN_SUCCESS_RATE:.0%}. "
        f"Failed cases: {[r['id'] for r in results if not r['decomposition_success']]}"
    )

    avg = sum(r["normalised_10"] for r in successes) / len(successes)
    assert avg >= MIN_AVG_SCORE, (
        f"Average eval score {avg:.1f} is below minimum {MIN_AVG_SCORE}. "
        f"Lowest scoring cases: {sorted(successes, key=lambda r: r['normalised_10'])[:3]}"
    )

    save_results(results, "ci")


@pytest.mark.eval
@pytest.mark.asyncio
async def test_no_regression_vs_baseline():
    """No case that scored above REGRESSION_FLOOR in the last run should fall below it now."""
    baseline = _latest_baseline()
    if baseline is None:
        pytest.skip("No baseline results found — run the eval once first to establish a baseline")

    baseline_scores = {r["id"]: r["normalised_10"] for r in baseline.get("results", [])}
    results = await run_eval(prompt_version="regression_check")

    regressions = []
    for r in results:
        if not r["decomposition_success"]:
            continue
        prev = baseline_scores.get(r["id"])
        if prev is not None and prev >= REGRESSION_FLOOR and r["normalised_10"] < REGRESSION_FLOOR:
            regressions.append({
                "id": r["id"],
                "prev_score": prev,
                "new_score": r["normalised_10"],
            })

    assert not regressions, (
        f"Regression detected in {len(regressions)} case(s):\n"
        + "\n".join(f"  {r['id']}: {r['prev_score']:.1f} → {r['new_score']:.1f}" for r in regressions)
    )
