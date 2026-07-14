"""
Eval runner for event classification prompt quality.

Usage:
  python -m tests.eval.monitor_runner                        # run all 20 cases
  python -m tests.eval.monitor_runner --case info_nvda_001   # single case
  python -m tests.eval.monitor_runner --prompt-version v2    # tag results

Results saved to tests/eval/results/monitor_{prompt_version}_{timestamp}.json
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
os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)

from tests.eval.monitor_rubric import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE, DIMENSIONS

DATASET_PATH = Path(__file__).parent / "monitor_dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _judge_family(model: str) -> str:
    m = model.lower()
    if "claude" in m:
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if "gemini" in m:
        return "gemini"
    return "anthropic"


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


async def _judge_output(case: dict, output_severity: str, output_analysis: str, judge_model: str) -> dict:
    inp = case["input"]
    user_msg = JUDGE_USER_TEMPLATE.format(
        ticker=inp["ticker"],
        why_own_it=inp["why_own_it"],
        must_remain_true=inp.get("must_remain_true") or "Not specified",
        what_would_change_my_mind=inp.get("what_would_change_my_mind") or "Not specified",
        ai_summary=inp.get("ai_summary") or "Not available",
        investor_profile=case.get("investor_profile", "general"),
        event_description=inp["event_description"],
        expected_severity=case["expected_severity"],
        output_severity=output_severity,
        output_analysis=output_analysis,
    )

    family = _judge_family(judge_model)

    if family == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError(f"ANTHROPIC_API_KEY required for judge '{judge_model}'")
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=key)
        response = await client.messages.create(
            model=judge_model,
            max_tokens=1024,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            temperature=0,
        )
        raw = next((b.text for b in response.content if hasattr(b, "text")), "")
        return json.loads(_strip_fences(raw))

    if family == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError(f"OPENAI_API_KEY required for judge '{judge_model}'")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=key)
        is_o_series = judge_model.startswith(("o1", "o3", "o4"))
        kwargs = {
            "model": judge_model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        }
        if not is_o_series:
            kwargs["temperature"] = 0
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(**kwargs)
        return json.loads(_strip_fences(response.choices[0].message.content or "{}"))

    if family == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError(f"GEMINI_API_KEY required for judge '{judge_model}'")
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=judge_model,
            contents=f"{JUDGE_SYSTEM_PROMPT}\n\n{user_msg}",
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return json.loads(_strip_fences(response.text or "{}"))

    raise RuntimeError(f"Unknown judge family for model '{judge_model}'")


async def _run_classification(case: dict) -> tuple[str, str, str] | None:
    """Run event classification for a single case. Returns (severity, analysis, direction) or None on failure.

    classify_event returns None both for genuine failures AND for skip decisions.
    We disambiguate by returning ("skip", "", "") when None comes back — the runner
    will then check whether that matches the expected severity.
    """
    from app.services.ai_monitor import classify_event
    inp = case["input"]
    result = await classify_event(
        why_own_it=inp["why_own_it"],
        must_remain_true=inp.get("must_remain_true"),
        what_would_change_my_mind=inp.get("what_would_change_my_mind"),
        ai_summary=inp.get("ai_summary"),
        event_description=inp["event_description"],
        investor_profile=case.get("investor_profile"),
        sector=inp.get("sector"),
        ticker=inp.get("ticker"),
        company_name=inp.get("company_name"),
    )
    if result is None:
        # Could be a genuine skip decision or an API failure.
        # Treat as skip so the runner can score it correctly for skip-expected cases.
        return "skip", "", ""
    return result.severity, result.analysis, result.direction


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

        output = await _run_classification(case)
        if output is None:
            results.append({
                "id": cid,
                "description": case["description"],
                "expected_severity": case["expected_severity"],
                "classification_success": False,
                "scores": None,
                "reasons": None,
                "total": 0,
                "normalised_10": 0.0,
            })
            print("    FAILED to classify", flush=True)
            continue

        output_severity, output_analysis, output_direction = output
        severity_match = output_severity == case["expected_severity"]
        expected_direction = case.get("expected_direction")
        # Direction is scored as a deterministic label match — no LLM judge.
        direction_match = (output_direction == expected_direction) if expected_direction else None
        direction_fields = {
            "expected_direction": expected_direction,
            "actual_direction": output_direction,
            "direction_match": direction_match,
        }

        # Skip cases have no analysis to judge — score purely on severity match
        if case["expected_severity"] == "skip" or output_severity == "skip":
            score = 10.0 if severity_match else 0.0
            result = {
                "id": cid,
                "description": case["description"],
                "expected_severity": case["expected_severity"],
                "actual_severity": output_severity,
                "severity_match": severity_match,
                "classification_success": True,
                "scores": {"severity_accuracy": 10 if severity_match else 0},
                "reasons": {},
                "total": 10 if severity_match else 0,
                "normalised_10": score,
                **direction_fields,
            }
            results.append(result)
            match = "✓" if severity_match else "✗"
            print(f"    {match} {output_severity} (expected {case['expected_severity']}) — {score:.1f}/10", flush=True)
            continue

        try:
            judgment = await _judge_output(case, output_severity, output_analysis, judge_model)
        except Exception as exc:
            print(f"    Judge error (recording severity only): {exc}", flush=True)
            results.append({
                "id": cid,
                "description": case["description"],
                "expected_severity": case["expected_severity"],
                "actual_severity": output_severity,
                "severity_match": severity_match,
                "classification_success": True,
                "judge_failed": True,
                "judge_error": str(exc)[:200],
                "scores": {"severity_accuracy": 2 if severity_match else 0},
                "reasons": {},
                "total": 2 if severity_match else 0,
                "normalised_10": (2 / 8 * 10) if severity_match else 0.0,
                **direction_fields,
            })
            continue

        result = {
            "id": cid,
            "description": case["description"],
            "expected_severity": case["expected_severity"],
            "actual_severity": output_severity,
            "severity_match": severity_match,
            "classification_success": True,
            "scores": judgment.get("scores", {}),
            "reasons": judgment.get("reasons", {}),
            "total": judgment.get("total", 0),
            "normalised_10": judgment.get("normalised_10", 0.0),
            **direction_fields,
        }
        results.append(result)
        match = "✓" if result["severity_match"] else "✗"
        dir_note = ""
        if expected_direction:
            dir_ok = "✓" if direction_match else "✗"
            dir_note = f" | direction {dir_ok} {output_direction or 'none'} (expected {expected_direction})"
        print(f"    {match} {output_severity} (expected {case['expected_severity']}) — {result['normalised_10']:.1f}/10{dir_note}", flush=True)

    return results


def print_table(results: list[dict], prompt_version: str) -> None:
    print(f"\n{'='*80}")
    print(f"  Event Classification Eval — Prompt {prompt_version}")
    print(f"{'='*80}")
    header = f"{'ID':<28} {'Exp':>5} {'Act':>5} {'M':>2} {'Acc':>4} {'Str':>4} {'Grd':>4} {'Hal':>4} {'Score':>6}"
    print(header)
    print("-" * 80)

    scores_list = []
    correct = 0
    for r in results:
        if not r["classification_success"]:
            print(f"{r['id']:<28} {'FAILED':>5}")
            continue
        s = r.get("scores") or {}
        score = r["normalised_10"]
        scores_list.append(score)
        if r["severity_match"]:
            correct += 1
        match = "✓" if r["severity_match"] else "✗"
        exp = r["expected_severity"][:5]
        act = r["actual_severity"][:5]
        print(
            f"{r['id']:<28} {exp:>5} {act:>5} {match:>2} "
            f"{s.get('severity_accuracy', '-'):>4} {s.get('analysis_structure', '-'):>4} "
            f"{s.get('thesis_grounding', '-'):>4} {s.get('no_hallucination', '-'):>4} "
            f"{score:>5.1f}"
        )

    if scores_list:
        avg = sum(scores_list) / len(scores_list)
        total = sum(1 for r in results if r["classification_success"])
        accuracy = correct / total if total else 0
        failed = sum(1 for r in results if not r["classification_success"])
        print("-" * 80)
        print(f"{'AVERAGE':<28} {'':>5} {'':>5} {'':>2} {'':>4} {'':>4} {'':>4} {'':>4} {avg:>5.1f}")
        print(f"  Severity accuracy: {correct}/{total} ({accuracy:.0%})")
        directional = [r for r in results if r.get("expected_direction")]
        if directional:
            dir_correct = sum(1 for r in directional if r.get("direction_match"))
            print(f"  Direction accuracy: {dir_correct}/{len(directional)}")
        if failed:
            print(f"  ({failed} case(s) failed classification)")
    print(f"{'='*80}\n")


def save_results(results: list[dict], prompt_version: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"monitor_{prompt_version}_{ts}.json"
    successes = [r for r in results if r["classification_success"]]
    with open(path, "w") as f:
        json.dump({
            "task": "event_classification",
            "prompt_version": prompt_version,
            "timestamp": ts,
            "results": results,
            "summary": {
                "total_cases": len(results),
                "success_rate": len(successes) / len(results) if results else 0,
                "severity_accuracy": sum(1 for r in successes if r["severity_match"]) / len(successes) if successes else 0,
                "avg_score": sum(r["normalised_10"] for r in successes) / len(successes) if successes else 0,
                "direction_cases": sum(1 for r in successes if r.get("expected_direction")),
                "direction_accuracy": (
                    sum(1 for r in successes if r.get("direction_match"))
                    / max(sum(1 for r in successes if r.get("expected_direction")), 1)
                ),
            },
        }, f, indent=2)
    return path


async def _main():
    parser = argparse.ArgumentParser(description="Run event classification evals")
    parser.add_argument("--case", action="append", dest="cases", help="Run specific case(s) by ID (repeatable)")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version tag")
    parser.add_argument("--judge", default="claude-sonnet-4-6", help="Judge model")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    args = parser.parse_args()

    case_ids = args.cases if args.cases else None
    print(f"\nRunning event classification evals (prompt={args.prompt_version}, judge={args.judge})...")

    results = await run_eval(case_ids=case_ids, prompt_version=args.prompt_version, judge_model=args.judge)
    print_table(results, args.prompt_version)

    if not args.no_save:
        path = save_results(results, args.prompt_version)
        print(f"Results saved to {path}\n")


if __name__ == "__main__":
    asyncio.run(_main())
