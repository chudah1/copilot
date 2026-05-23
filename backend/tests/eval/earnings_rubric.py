"""
Judge prompt and scoring for earnings review eval.

The judge receives the thesis, claims, earnings data, the expected overall
assessment, and the model's full review output. Scores 5 dimensions on a 0-2 scale.
Total normalised to 0-10.
"""

JUDGE_SYSTEM_PROMPT = """You are evaluating an AI earnings review output for an investor monitoring tool.

The tool evaluates thesis claims against earnings data and returns:
  - Per-claim verdicts: "holds" | "watch" | "broken" | "unclear"
  - Overall assessment: "thesis_intact" | "watch" | "thesis_challenged"
  - A summary

Score the output on the following 5 dimensions. Return ONLY valid JSON — no prose, no markdown fences.

Scoring scale:
  2 = fully satisfied
  1 = partially satisfied / minor issues
  0 = not satisfied / missing or wrong

Dimensions:
1. assessment_accuracy — Does the overall_assessment match the expected assessment?
                         Exact match = 2. Off by one level (e.g. watch instead of thesis_challenged) = 1.
                         Two levels off = 0.
2. verdict_quality     — Do per-claim verdicts correctly reflect the earnings evidence?
                         Each claim verdict must be defensible given the earnings data provided.
                         All verdicts accurate = 2. Minor inconsistencies = 1. Multiple wrong verdicts = 0.
3. evidence_citation   — Does each claim explanation cite a specific number or fact from the earnings data?
                         "grew 78% YoY" is evidence. "showed strong growth" is not.
                         All explanations cite specifics = 2. Most do = 1. Generic with no numbers = 0.
4. explanation_format  — Does each explanation start with "You said..." and quote or paraphrase the claim?
                         All explanations follow the format = 2. Most do = 1. None do = 0.
5. directness          — Does the summary avoid softening bad news? Is the assessment direct and actionable?
                         Broken conditions are called broken, not "worth monitoring". Direct = 2.
                         Minor hedging = 1. Consistently softens bad news or is generic = 0.

Return this exact JSON:
{
  "scores": {
    "assessment_accuracy": <0-2>,
    "verdict_quality": <0-2>,
    "evidence_citation": <0-2>,
    "explanation_format": <0-2>,
    "directness": <0-2>
  },
  "reasons": {
    "assessment_accuracy": "<one line>",
    "verdict_quality": "<one line>",
    "evidence_citation": "<one line>",
    "explanation_format": "<one line>",
    "directness": "<one line>"
  },
  "total": <0-10>,
  "normalised_10": <0.0-10.0>
}"""

JUDGE_USER_TEMPLATE = """THESIS:
Ticker: {ticker} ({name})
Why I own it: {why_own_it}
Must remain true: {must_remain_true}
What would change my mind: {what_would_change_my_mind}

CLAIMS:
{claims}

EARNINGS DATA:
Quarter: {fiscal_quarter}
Earnings surprise: {earnings_surprise}
Revenue growth YoY: {revenue_growth}
Earnings growth YoY: {earnings_growth}
News headlines:
{news_headlines}

EXPECTED OVERALL ASSESSMENT: {expected_assessment}

MODEL OUTPUT:
Overall assessment: {output_assessment}
Summary: {output_summary}
Verdicts:
{output_verdicts}"""

DIMENSIONS = [
    "assessment_accuracy",
    "verdict_quality",
    "evidence_citation",
    "explanation_format",
    "directness",
]
