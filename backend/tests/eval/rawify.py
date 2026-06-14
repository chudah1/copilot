"""
Build a raw-noise variant of the decomposition dataset for the surface-handling experiment.

The 30-case `dataset.json` was sourced from real Reddit/Twitter posts and then
LLM-cleaned — grammar normalized, fields neatly split into why_own_it /
must_remain_true / what_would_change_my_mind. That cleaning step stripped the
surface noise that real users actually produce, which means the existing eval
does not measure the pipeline's ability to handle raw investor writing.

This module produces a paired "raw" dataset by applying a small set of
deterministic transformations to a selected subset of cases. The transformation
is rule-based (not LLM-generated) so we are not authoring noise in shapes the
system already knows how to handle.

Transformations applied:
  - Merge the three structured text fields into a single `why_own_it` paragraph
    (real Reddit/Twitter posts are prose, not forms).
  - Empty out `must_remain_true` and `what_would_change_my_mind` (so the
    pipeline has to extract everything from the merged prose).
  - Lowercase the merged text.
  - Replace ". " with " and ".
  - Replace ", " with " ".
  - Insert "$TICKER" once near the start as a mid-stream ticker mention.
  - Prefix with a Reddit-style opener ("ok so" / "tbh").

Tag each raw case with `"surface": "raw"` and the original with `"surface":
"cleaned"` so we never confuse the two in results.
"""

from __future__ import annotations

import json
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "dataset.json"
RAW_DATASET_PATH = Path(__file__).parent / "dataset_raw.json"

# Subset chosen to span complexity, monitorability, and original style.
SELECTED_CASE_IDS = [
    "growth_nvda_001",
    "margins_aapl_005",
    "competitor_googl_008",
    "income_o_012",
    "qualitative_meta_016",
    "mixed_pltr_018",
    "uk_shel_021",
    "rambling_ba_028",
    "reddit_googl_031",
    "reddit_nvda_032",
    "reddit_diary_bidu_039",
    "reddit_bear_first_intc_041",
]

# Alternating openers so we don't bias toward one tone.
OPENERS = ["ok so", "tbh"]


def _rawify_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = text.lower()
    text = text.replace(". ", " and ")
    text = text.replace(",", "")
    text = text.replace(";", "")
    return text.strip(" .")


def rawify_case(case: dict, opener: str) -> dict:
    inp = case["input"]
    parts = [
        _rawify_text(inp.get("why_own_it", "")),
        _rawify_text(inp.get("must_remain_true", "")),
        _rawify_text(inp.get("what_would_change_my_mind", "")),
    ]
    parts = [p for p in parts if p]
    merged = " ".join(parts)

    ticker = inp.get("ticker", "")
    if ticker and merged:
        # Insert a mid-stream ticker mention after the first ~12 words so the
        # decomposer cannot rely on the structured ticker field alone.
        words = merged.split()
        insert_at = min(12, len(words))
        words.insert(insert_at, f"${ticker}")
        merged = " ".join(words)

    if merged:
        merged = f"{opener} {merged}"

    new_case = {
        "id": f"{case['id']}__raw",
        "description": f"{case['description']} (rawified)",
        "expected_reason_type": case.get("expected_reason_type"),
        "expected_monitorability": case.get("expected_monitorability"),
        "complexity": case.get("complexity"),
        "surface": "raw",
        "source_id": case["id"],
        "input": {
            "ticker": ticker,
            "name": inp.get("name", ""),
            "why_own_it": merged,
            "must_remain_true": "",
            "what_would_change_my_mind": "",
        },
    }
    return new_case


def build_raw_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        full = json.load(f)
    selected = {c["id"]: c for c in full if c["id"] in SELECTED_CASE_IDS}
    raw_cases = []
    for i, cid in enumerate(SELECTED_CASE_IDS):
        if cid not in selected:
            raise KeyError(f"Selected case '{cid}' not found in dataset.json")
        opener = OPENERS[i % len(OPENERS)]
        raw_cases.append(rawify_case(selected[cid], opener))
    return raw_cases


def main() -> None:
    raw_cases = build_raw_dataset()
    with open(RAW_DATASET_PATH, "w") as f:
        json.dump(raw_cases, f, indent=2)
    print(f"Wrote {len(raw_cases)} raw cases to {RAW_DATASET_PATH}")
    print("\nSample (first case):")
    print(json.dumps(raw_cases[0], indent=2))


if __name__ == "__main__":
    main()
