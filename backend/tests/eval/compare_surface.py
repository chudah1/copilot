"""
Compare cleaned vs raw decomposition scores for the surface-handling experiment.

Reads two results files from `tests/eval/results/` — one from running the cleaned
dataset (12-case subset) and one from running the rawified parallel dataset —
and reports per-case and aggregate score deltas.

Raw case IDs are formed by appending `__raw` to the cleaned case ID, so pairs
are matched on the cleaned ID.

Usage:
  python -m tests.eval.compare_surface --cleaned <path> --raw <path>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_results(path: Path) -> dict[str, dict]:
    with open(path) as f:
        payload = json.load(f)
    return {r["id"]: r for r in payload.get("results", [])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare cleaned vs raw eval results")
    parser.add_argument("--cleaned", required=True, help="Path to cleaned results JSON")
    parser.add_argument("--raw", required=True, help="Path to raw results JSON")
    args = parser.parse_args()

    cleaned = _load_results(Path(args.cleaned))
    raw = _load_results(Path(args.raw))

    cleaned_to_raw = {cid: f"{cid}__raw" for cid in cleaned}

    rows = []
    deltas = []
    cleaned_scores = []
    raw_scores = []
    mono_changes = []

    for cid, raw_id in cleaned_to_raw.items():
        c = cleaned.get(cid)
        r = raw.get(raw_id)
        if not c or not r:
            continue
        if not c.get("decomposition_success") or not r.get("decomposition_success"):
            rows.append((cid, c.get("normalised_10", 0.0), r.get("normalised_10", 0.0), None, c.get("actual_monitorability", "?"), r.get("actual_monitorability", "?")))
            continue
        cs = c["normalised_10"]
        rs = r["normalised_10"]
        delta = rs - cs
        cleaned_scores.append(cs)
        raw_scores.append(rs)
        deltas.append(delta)
        cm = c.get("actual_monitorability", "?")
        rm = r.get("actual_monitorability", "?")
        if cm != rm:
            mono_changes.append((cid, cm, rm))
        rows.append((cid, cs, rs, delta, cm, rm))

    print("=" * 78)
    print("  Surface-Handling Comparison — Cleaned vs Raw")
    print("=" * 78)
    print(f"{'Case ID':<32} {'Cleaned':>8} {'Raw':>6} {'Delta':>7} {'Mono (C→R)':>16}")
    print("-" * 78)
    for cid, cs, rs, delta, cm, rm in rows:
        delta_s = f"{delta:+.1f}" if delta is not None else "  —  "
        mono_s = f"{cm[:4]}→{rm[:4]}"
        print(f"{cid:<32} {cs:>8.1f} {rs:>6.1f} {delta_s:>7} {mono_s:>16}")
    print("-" * 78)

    if cleaned_scores:
        c_avg = sum(cleaned_scores) / len(cleaned_scores)
        r_avg = sum(raw_scores) / len(raw_scores)
        d_avg = r_avg - c_avg
        print(f"{'AVERAGE':<32} {c_avg:>8.2f} {r_avg:>6.2f} {d_avg:>+7.2f}")
        print(f"\nCases with monitorability change: {len(mono_changes)} / {len(rows)}")
        for cid, cm, rm in mono_changes:
            print(f"  {cid}: {cm} → {rm}")

    print("=" * 78)


if __name__ == "__main__":
    main()
