"""
Eval runner for earnings review prompt quality.

Usage:
  python -m tests.eval.earnings_runner                        # run all 15 cases
  python -m tests.eval.earnings_runner --case intact_nvda_001  # single case
  python -m tests.eval.earnings_runner --prompt-version v2    # tag results

Results saved to tests/eval/results/earnings_{prompt_version}_{timestamp}.json
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

from tests.eval.earnings_rubric import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE, DIMENSIONS

DATASET_PATH = Path(__file__).parent / "earnings_dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _pct(value: float | None) -> str:
    if value is None:
        return "Not available"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{'+' if pct > 0 else ''}{pct:.1f}%"


async def _judge_output(case: dict, review_result, judge_model: str) -> dict:
    inp = case["input"]
    claims_str = "\n".join(f"  - [{c['id']}] {c['claim_text']}" for c in inp["claims"])
    ed = inp["earnings_data"]
    news_str = "\n".join(f"  - {h}" for h in ed.get("recent_news", [])[:5]) or "  - None"
    surprise = ed.get("earnings_surprise_pct")
    surprise_str = f"{'+' if surprise and surprise > 0 else ''}{surprise:.1f}%" if surprise is not None else "Not available"

    verdicts_str = "\n".join(
        f"  [{v.claim_id}] {v.verdict.upper()}: {v.explanation}"
        for v in review_result.verdicts
    )

    user_msg = JUDGE_USER_TEMPLATE.format(
        ticker=inp["ticker"],
        name=inp["name"],
        why_own_it=inp["why_own_it"],
        must_remain_true=inp.get("must_remain_true") or "Not specified",
        what_would_change_my_mind=inp.get("what_would_change_my_mind") or "Not specified",
        claims=claims_str,
        fiscal_quarter=ed.get("fiscal_quarter") or "Most recent quarter",
        earnings_surprise=surprise_str,
        revenue_growth=_pct(ed.get("revenue_growth_yoy")),
        earnings_growth=_pct(ed.get("earnings_growth_yoy")),
        news_headlines=news_str,
        expected_assessment=case["expected_assessment"],
        output_assessment=review_result.overall_assessment,
        output_summary=review_result.summary,
        output_verdicts=verdicts_str,
    )

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    raw = None

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            response = await client.messages.create(
                model=judge_model if "claude" in judge_model else "claude-sonnet-4-6",
                max_tokens=1024,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0,
            )
            text = next((b.text for b in response.content if hasattr(b, "text")), "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            raw = text
        except Exception:
            pass

    if raw is None and openai_key:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_key)
        response = await client.chat.completions.create(
            model=judge_model if "gpt" in judge_model else "gpt-4o-mini",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"

    if raw is None:
        raise RuntimeError("No ANTHROPIC_API_KEY or OPENAI_API_KEY set")

    return json.loads(raw)


async def _run_earnings_review(case: dict):
    """Run earnings review for a single case. Returns EarningsReviewResult or None."""
    from app.services.earnings_review import run_earnings_review
    from app.services.market_data import CompanyData
    inp = case["input"]
    ed = inp["earnings_data"]

    company_data = CompanyData(
        ticker=inp["ticker"],
        name=inp["name"],
        sector="Unknown",
        industry="Unknown",
        current_price=None,
        market_cap=ed.get("market_cap"),
        pe_ratio=ed.get("pe_ratio"),
        revenue_growth_yoy=ed.get("revenue_growth_yoy"),
        earnings_growth_yoy=ed.get("earnings_growth_yoy"),
        dividend_yield=None,
        description="",
        recent_news=ed.get("recent_news", []),
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=ed.get("earnings_surprise_pct"),
        news_items=[],
        recent_fiscal_quarter=ed.get("fiscal_quarter"),
    )

    try:
        result = await run_earnings_review(
            ticker=inp["ticker"],
            name=inp["name"],
            why_own_it=inp["why_own_it"],
            must_remain_true=inp.get("must_remain_true"),
            what_would_change_my_mind=inp.get("what_would_change_my_mind"),
            claims=inp["claims"],
            company_data=company_data,
        )
        return result
    except Exception as exc:
        print(f"    Review error: {exc}", flush=True)
        return None


async def run_eval(
    case_ids: list[str] | None = None,
    prompt_version: str = "unknown",
    judge_model: str = "claude-sonnet-4-6",
) -> list[dict]:
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    if case_ids:
        dataset = [c for c in dataset if c["id"] in case_ids]

    results = []
    for i, case in enumerate(dataset):
        cid = case["id"]
        if i > 0:
            await asyncio.sleep(2)
        print(f"  Running {cid}...", flush=True)

        review = await _run_earnings_review(case)
        if review is None:
            results.append({
                "id": cid,
                "description": case["description"],
                "expected_assessment": case["expected_assessment"],
                "review_success": False,
                "scores": None,
                "reasons": None,
                "total": 0,
                "normalised_10": 0.0,
            })
            print("    FAILED to review", flush=True)
            continue

        try:
            judgment = await _judge_output(case, review, judge_model)
        except Exception as exc:
            print(f"    Judge error: {exc}", flush=True)
            continue

        result = {
            "id": cid,
            "description": case["description"],
            "expected_assessment": case["expected_assessment"],
            "actual_assessment": review.overall_assessment,
            "assessment_match": review.overall_assessment == case["expected_assessment"],
            "verdict_count": len(review.verdicts),
            "review_success": True,
            "scores": judgment.get("scores", {}),
            "reasons": judgment.get("reasons", {}),
            "total": judgment.get("total", 0),
            "normalised_10": judgment.get("normalised_10", 0.0),
        }
        results.append(result)
        match = "✓" if result["assessment_match"] else "✗"
        print(f"    {match} {review.overall_assessment} (expected {case['expected_assessment']}) — {result['normalised_10']:.1f}/10", flush=True)

    return results


def print_table(results: list[dict], prompt_version: str) -> None:
    print(f"\n{'='*80}")
    print(f"  Earnings Review Eval — Prompt {prompt_version}")
    print(f"{'='*80}")
    header = f"{'ID':<28} {'Exp':>10} {'Act':>10} {'M':>2} {'Acc':>4} {'Vrd':>4} {'Evi':>4} {'Fmt':>4} {'Dir':>4} {'Score':>6}"
    print(header)
    print("-" * 80)

    scores_list = []
    correct = 0
    for r in results:
        if not r["review_success"]:
            print(f"{r['id']:<28} {'FAILED':>10}")
            continue
        s = r.get("scores") or {}
        score = r["normalised_10"]
        scores_list.append(score)
        if r["assessment_match"]:
            correct += 1
        match = "✓" if r["assessment_match"] else "✗"
        exp = r["expected_assessment"][:10]
        act = r["actual_assessment"][:10]
        print(
            f"{r['id']:<28} {exp:>10} {act:>10} {match:>2} "
            f"{s.get('assessment_accuracy', '-'):>4} {s.get('verdict_quality', '-'):>4} "
            f"{s.get('evidence_citation', '-'):>4} {s.get('explanation_format', '-'):>4} "
            f"{s.get('directness', '-'):>4} {score:>5.1f}"
        )

    if scores_list:
        avg = sum(scores_list) / len(scores_list)
        total = sum(1 for r in results if r["review_success"])
        accuracy = correct / total if total else 0
        failed = sum(1 for r in results if not r["review_success"])
        print("-" * 80)
        print(f"{'AVERAGE':<28} {'':>10} {'':>10} {'':>2} {'':>4} {'':>4} {'':>4} {'':>4} {'':>4} {avg:>5.1f}")
        print(f"  Assessment accuracy: {correct}/{total} ({accuracy:.0%})")
        if failed:
            print(f"  ({failed} case(s) failed review)")
    print(f"{'='*80}\n")


def save_results(results: list[dict], prompt_version: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"earnings_{prompt_version}_{ts}.json"
    successes = [r for r in results if r["review_success"]]
    with open(path, "w") as f:
        json.dump({
            "task": "earnings_review",
            "prompt_version": prompt_version,
            "timestamp": ts,
            "results": results,
            "summary": {
                "total_cases": len(results),
                "success_rate": len(successes) / len(results) if results else 0,
                "assessment_accuracy": sum(1 for r in successes if r["assessment_match"]) / len(successes) if successes else 0,
                "avg_score": sum(r["normalised_10"] for r in successes) / len(successes) if successes else 0,
            },
        }, f, indent=2)
    return path


async def _main():
    parser = argparse.ArgumentParser(description="Run earnings review evals")
    parser.add_argument("--case", help="Run a single case by ID")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version tag")
    parser.add_argument("--judge", default="claude-sonnet-4-6", help="Judge model")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    args = parser.parse_args()

    case_ids = [args.case] if args.case else None
    print(f"\nRunning earnings review evals (prompt={args.prompt_version}, judge={args.judge})...")

    results = await run_eval(case_ids=case_ids, prompt_version=args.prompt_version, judge_model=args.judge)
    print_table(results, args.prompt_version)

    if not args.no_save:
        path = save_results(results, args.prompt_version)
        print(f"Results saved to {path}\n")


if __name__ == "__main__":
    asyncio.run(_main())
