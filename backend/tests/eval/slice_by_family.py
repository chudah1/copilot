"""
Slice a decomposition eval result by `expected_reason_type` from the source
dataset, so we can see which thesis families the pipeline handles weakly.

The 30-case `dataset.json` already tags each case with `expected_reason_type`
(business_performance / margins / income / macro_theme / behavioral /
social_proof / portfolio_role / mixed / unclear). We don't author a new
taxonomy — that field is the family.

The results JSON omits `expected_reason_type`, so this script joins on case ID.

Usage:
  python -m tests.eval.slice_by_family --results <path> [--dataset <path>]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_DATASET = Path(__file__).parent / "dataset.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice eval results by thesis family")
    parser.add_argument("--results", required=True, help="Path to results JSON")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to source dataset JSON")
    args = parser.parse_args()

    with open(args.dataset) as f:
        dataset = json.load(f)
    # Cases in the raw dataset use IDs like `growth_nvda_001__raw`; join on the
    # source ID by stripping that suffix.
    id_to_family = {c["id"]: c.get("expected_reason_type", "unknown") for c in dataset}

    with open(args.results) as f:
        payload = json.load(f)
    results = payload.get("results", [])

    by_family: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    failed_by_family: dict[str, int] = defaultdict(int)

    for r in results:
        cid = r["id"]
        source_id = cid[:-5] if cid.endswith("__raw") else cid
        family = id_to_family.get(source_id, "unknown")
        if r.get("decomposition_success"):
            by_family[family].append((cid, r["normalised_10"], r.get("actual_monitorability", "?")))
        else:
            failed_by_family[family] += 1

    print("=" * 78)
    print(f"  Family Slice — {payload.get('prompt_version', '?')}")
    print("=" * 78)
    print(f"{'Family':<22} {'N':>4} {'Avg':>6} {'Min':>5} {'Max':>5} {'Failed':>7}")
    print("-" * 78)

    overall_scores: list[float] = []
    family_rows: list[tuple[str, int, float, float, float, int]] = []
    for family, rows in sorted(by_family.items(), key=lambda kv: -sum(s for _, s, _ in kv[1]) / max(1, len(kv[1]))):
        scores = [s for _, s, _ in rows]
        overall_scores.extend(scores)
        family_rows.append((
            family,
            len(rows),
            sum(scores) / len(scores),
            min(scores),
            max(scores),
            failed_by_family.get(family, 0),
        ))

    for family in failed_by_family:
        if family not in by_family:
            family_rows.append((family, 0, 0.0, 0.0, 0.0, failed_by_family[family]))

    for family, n, avg, mn, mx, failed in family_rows:
        avg_s = f"{avg:>6.2f}" if n else "    —"
        mn_s = f"{mn:>5.1f}" if n else "  —  "
        mx_s = f"{mx:>5.1f}" if n else "  —  "
        print(f"{family:<22} {n:>4} {avg_s} {mn_s} {mx_s} {failed:>7}")

    if overall_scores:
        print("-" * 78)
        print(f"{'OVERALL':<22} {len(overall_scores):>4} {sum(overall_scores) / len(overall_scores):>6.2f}")
    print("=" * 78)

    print("\nPer-case detail (lowest scoring first):")
    print(f"{'Case ID':<32} {'Family':<22} {'Score':>6} {'Mono':>6}")
    print("-" * 78)
    flat = [
        (cid, family, score, mono)
        for family, rows in by_family.items()
        for cid, score, mono in rows
    ]
    flat.sort(key=lambda t: t[2])
    for cid, family, score, mono in flat:
        print(f"{cid:<32} {family:<22} {score:>6.1f} {mono[:4]:>6}")


if __name__ == "__main__":
    main()
