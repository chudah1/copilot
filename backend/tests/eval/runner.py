"""
Eval runner for decomposition prompt quality.

Usage:
  python -m tests.eval.runner                          # run all cases
  python -m tests.eval.runner --case growth_nvda_001   # single case
  python -m tests.eval.runner --prompt-version v5      # tag results with version

Results saved to tests/eval/results/{prompt_version}_{timestamp}.json
Comparison table printed to stdout.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load API keys from .env into os.environ before any app imports
from app.config import settings
os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

from tests.eval.rubric import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE, DIMENSIONS

DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


async def _judge_output(input_case: dict, output: dict, judge_model: str) -> dict:
    """Send output to judge model, return scores dict."""
    import json as _json

    user_msg = JUDGE_USER_TEMPLATE.format(
        ticker=input_case["input"]["ticker"],
        name=input_case["input"]["name"],
        why_own_it=input_case["input"]["why_own_it"],
        must_remain_true=input_case["input"].get("must_remain_true") or "None provided",
        what_would_change_my_mind=input_case["input"].get("what_would_change_my_mind") or "None provided",
        output_json=_json.dumps(output, indent=2),
    )

    # Try Anthropic first, fall back to OpenAI
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    anthropic_succeeded = False
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
            raw = next((b.text for b in response.content if hasattr(b, "text")), "")
            # Strip markdown fences if model wraps JSON in ```json ... ```
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            anthropic_succeeded = True
        except Exception:
            pass  # fall through to OpenAI

    if not anthropic_succeeded and openai_key:
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
    elif not anthropic_succeeded:
        raise RuntimeError("No ANTHROPIC_API_KEY or OPENAI_API_KEY set")

    return json.loads(raw)


async def _run_decomposition(input_case: dict) -> dict | None:
    """Run thesis decomposition for a single case. Returns raw output or None on failure."""
    from app.services.reasoning.gateway import ThesisReasoningGateway
    from app.services.reasoning.types import ReasoningRequest, ReasoningTaskType

    gateway = ThesisReasoningGateway()
    request = ReasoningRequest(
        task_type=ReasoningTaskType.DECOMPOSE_THESIS,
        thesis_id=f"eval_{input_case['id']}",
        user_id="eval_runner",
        payload=input_case["input"],
    )
    result = await gateway.run(request)
    if result.success and result.raw_output:
        return result.raw_output
    return None


async def run_eval(
    case_ids: list[str] | None = None,
    prompt_version: str = "unknown",
    judge_model: str = "claude-sonnet-4-6",
    skip_decomposition: bool = False,
    precomputed_outputs: dict | None = None,
) -> list[dict]:
    """
    Run eval on the dataset. Returns list of result dicts.

    Args:
        case_ids: subset of case IDs to run; None = all
        prompt_version: tag for results file (e.g. "v5")
        judge_model: model to use for judging
        skip_decomposition: if True, precomputed_outputs must be provided
        precomputed_outputs: {case_id: output_dict} to use instead of live decomposition
    """
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    if case_ids:
        dataset = [c for c in dataset if c["id"] in case_ids]

    results = []
    for i, case in enumerate(dataset):
        cid = case["id"]
        # Small delay between cases to avoid Anthropic rate limiting on rapid sequential calls
        if i > 0:
            await asyncio.sleep(2)
        print(f"  Running {cid}...", flush=True)

        if skip_decomposition and precomputed_outputs:
            output = precomputed_outputs.get(cid)
        else:
            output = await _run_decomposition(case)

        if output is None:
            results.append({
                "id": cid,
                "description": case["description"],
                "complexity": case.get("complexity"),
                "expected_monitorability": case.get("expected_monitorability"),
                "decomposition_success": False,
                "scores": None,
                "reasons": None,
                "total": 0,
                "normalised_10": 0.0,
            })
            print(f"    FAILED to decompose", flush=True)
            continue

        try:
            judgment = await _judge_output(case, output, judge_model)
        except Exception as exc:
            print(f"    Judge error: {exc}", flush=True)
            continue

        result = {
            "id": cid,
            "description": case["description"],
            "complexity": case.get("complexity"),
            "expected_monitorability": case.get("expected_monitorability"),
            "actual_monitorability": output.get("monitorability"),
            "decomposition_success": True,
            "claims_extracted": len(output.get("claims", [])),
            "scores": judgment.get("scores", {}),
            "reasons": judgment.get("reasons", {}),
            "total": judgment.get("total", 0),
            "normalised_10": judgment.get("normalised_10", 0.0),
        }
        results.append(result)
        print(f"    Score: {result['normalised_10']:.1f}/10", flush=True)

    return results


def print_table(results: list[dict], prompt_version: str) -> None:
    """Print a readable comparison table."""
    print(f"\n{'='*80}")
    print(f"  Decomposition Eval — Prompt {prompt_version}")
    print(f"{'='*80}")
    header = f"{'ID':<28} {'Mono':>5} {'Clm':>4} {'Fals':>5} {'Grnd':>5} {'Srch':>5} {'Cvr':>4} {'Hal':>4} {'Cfg':>4} {'Score':>6}"
    print(header)
    print("-" * 80)

    scores_list = []
    for r in results:
        if not r["decomposition_success"]:
            print(f"{r['id']:<28} {'FAILED':>5}")
            continue
        s = r.get("scores") or {}
        score = r["normalised_10"]
        scores_list.append(score)
        mono = r.get("actual_monitorability", "?")[:4]
        print(
            f"{r['id']:<28} {mono:>5} {r['claims_extracted']:>4} "
            f"{s.get('falsifiability', '-'):>5} {s.get('grounding', '-'):>5} "
            f"{s.get('signal_searchability', '-'):>5} {s.get('coverage', '-'):>4} "
            f"{s.get('no_hallucination', '-'):>4} {s.get('config_population', '-'):>4} "
            f"{score:>5.1f}"
        )

    if scores_list:
        avg = sum(scores_list) / len(scores_list)
        failed = sum(1 for r in results if not r["decomposition_success"])
        print("-" * 80)
        print(f"{'AVERAGE':<28} {'':>5} {'':>4} {'':>5} {'':>5} {'':>5} {'':>4} {'':>4} {'':>4} {avg:>5.1f}")
        if failed:
            print(f"  ({failed} case(s) failed decomposition)")
    print(f"{'='*80}\n")


def save_results(results: list[dict], prompt_version: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{prompt_version}_{ts}.json"
    with open(path, "w") as f:
        json.dump({
            "prompt_version": prompt_version,
            "timestamp": ts,
            "results": results,
            "summary": {
                "total_cases": len(results),
                "success_rate": sum(1 for r in results if r["decomposition_success"]) / len(results) if results else 0,
                "avg_score": sum(r["normalised_10"] for r in results if r["decomposition_success"]) / max(1, sum(1 for r in results if r["decomposition_success"])),
            },
        }, f, indent=2)
    return path


async def _main():
    parser = argparse.ArgumentParser(description="Run decomposition prompt evals")
    parser.add_argument("--case", help="Run a single case by ID")
    parser.add_argument("--prompt-version", default="unknown", help="Prompt version tag (e.g. v5)")
    parser.add_argument("--judge", default="claude-sonnet-4-6", help="Judge model")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to file")
    args = parser.parse_args()

    case_ids = [args.case] if args.case else None
    print(f"\nRunning decomposition evals (prompt={args.prompt_version}, judge={args.judge})...")

    results = await run_eval(
        case_ids=case_ids,
        prompt_version=args.prompt_version,
        judge_model=args.judge,
    )

    print_table(results, args.prompt_version)

    if not args.no_save:
        path = save_results(results, args.prompt_version)
        print(f"Results saved to {path}\n")


if __name__ == "__main__":
    asyncio.run(_main())
