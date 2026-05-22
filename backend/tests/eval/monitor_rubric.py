"""
Judge prompt and scoring for event classification eval.

The judge receives the thesis, the event, the expected severity, and the
model's classification output. Scores 4 dimensions on a 0-2 scale.
Total normalised to 0-10.
"""

JUDGE_SYSTEM_PROMPT = """You are evaluating an AI event classification output for an investor monitoring tool.

The tool receives a thesis and a new event, and must classify the event as:
  "info"          — routine, does not threaten any thesis pillar
  "warning"       — a thesis pillar may be weakening; worth watching
  "thesis_breaking" — directly contradicts a stated condition or changes-my-mind trigger

Score the output on the following 4 dimensions. Return ONLY valid JSON — no prose, no markdown fences.

Scoring scale:
  2 = fully satisfied
  1 = partially satisfied / minor issues
  0 = not satisfied / missing or wrong

Dimensions:
1. severity_accuracy  — Does the classified severity match the expected severity?
                        Exact match = 2. Off by one level (e.g. warning instead of thesis_breaking) = 1.
                        Two levels off (e.g. info instead of thesis_breaking) = 0.
2. analysis_structure — Does the analysis follow the required 3-sentence structure?
                        Sentence 1: what happened. Sentence 2: why it matters to the thesis.
                        Sentence 3: clear next step (watch / review soon / thesis may be broken).
                        All three present and on-topic = 2. One sentence missing or off-topic = 1.
3. thesis_grounding   — Is the analysis grounded in the specific thesis conditions provided?
                        References specific thesis pillars, numbers, or stated conditions = 2.
                        Generic analysis not tied to the thesis = 1. Contradicts the thesis = 0.
4. no_hallucination   — Does the analysis avoid inventing facts not in the event or thesis?
                        No invented numbers, entities, or events = 2. Minor invention = 1. Significant invention = 0.

Return this exact JSON:
{
  "scores": {
    "severity_accuracy": <0-2>,
    "analysis_structure": <0-2>,
    "thesis_grounding": <0-2>,
    "no_hallucination": <0-2>
  },
  "reasons": {
    "severity_accuracy": "<one line>",
    "analysis_structure": "<one line>",
    "thesis_grounding": "<one line>",
    "no_hallucination": "<one line>"
  },
  "total": <0-8>,
  "normalised_10": <0.0-10.0>
}"""

JUDGE_USER_TEMPLATE = """THESIS:
Ticker: {ticker}
Why I own it: {why_own_it}
Must remain true: {must_remain_true}
What would change my mind: {what_would_change_my_mind}
AI summary: {ai_summary}
Investor profile: {investor_profile}

EVENT:
{event_description}

EXPECTED SEVERITY: {expected_severity}

MODEL OUTPUT:
Severity: {output_severity}
Analysis: {output_analysis}"""

DIMENSIONS = [
    "severity_accuracy",
    "analysis_structure",
    "thesis_grounding",
    "no_hallucination",
]
