"""
Judge prompt and scoring logic for decomposition eval.

The judge model receives the thesis input + decomposition output and scores
6 dimensions on a 0-2 scale. Total is normalised to 0-10.
"""

JUDGE_SYSTEM_PROMPT = """You are evaluating the quality of a thesis decomposition output produced by an AI model.

Score the output on the following 6 dimensions. Return ONLY valid JSON — no prose, no markdown fences.

Scoring scale:
  2 = fully satisfied
  1 = partially satisfied / minor issues
  0 = not satisfied / missing

Dimensions:
1. falsifiability     — Each claim_text is phrased as a testable assertion with an implied pass/fail condition
                        (e.g. "grows above 20%" not "is growing fast"). Vague claims score 0-1.
2. grounding          — Thresholds, entities, and tickers come from the user's text or obvious market knowledge,
                        not invented. Check that numeric thresholds in signal_config_json match numbers in the input.
3. signal_searchability — Each signal_label is specific enough to find real news
                         (e.g. "NVDA data center revenue growth" not "revenue"). Generic labels score 0-1.
4. coverage           — All three input fields (why_own_it, must_remain_true, what_would_change_my_mind)
                        that are non-empty contributed at least one claim. Missing field coverage scores 0-1.
5. no_hallucination   — No entities, tickers, or thresholds that have no basis in the user text
                        or plausible market knowledge. Any invented fact scores 0.
6. config_population  — Quantitative signals have metric + operator + threshold/threshold_pct filled.
                        Topic/news signals have topic filled. Unpopulated configs where data was available score 0-1.

For vague or minimal inputs (why_own_it is one sentence, must_remain_true and what_would_change_my_mind are empty):
- A good output correctly classifies monitorability as "low" and confidence as low
- Claims extracted from vague inputs should be marked confirmation_required: true
- Penalty: if the model invents elaborate signals for a one-sentence thesis, deduct from grounding and no_hallucination

Return this exact JSON:
{
  "scores": {
    "falsifiability": <0-2>,
    "grounding": <0-2>,
    "signal_searchability": <0-2>,
    "coverage": <0-2>,
    "no_hallucination": <0-2>,
    "config_population": <0-2>
  },
  "reasons": {
    "falsifiability": "<one line>",
    "grounding": "<one line>",
    "signal_searchability": "<one line>",
    "coverage": "<one line>",
    "no_hallucination": "<one line>",
    "config_population": "<one line>"
  },
  "total": <0-12>,
  "normalised_10": <0.0-10.0>
}"""


JUDGE_USER_TEMPLATE = """THESIS INPUT:
Ticker: {ticker}
Name: {name}
Why I own it: {why_own_it}
Must remain true: {must_remain_true}
What would change my mind: {what_would_change_my_mind}

DECOMPOSITION OUTPUT:
{output_json}"""


DIMENSIONS = [
    "falsifiability",
    "grounding",
    "signal_searchability",
    "coverage",
    "no_hallucination",
    "config_population",
]
