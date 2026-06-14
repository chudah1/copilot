DECOMPOSITION_PROMPT_VERSION = "v7"

DECOMPOSITION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reason_type": {
            "type": "string",
            "enum": [
                "business_performance",
                "valuation",
                "macro_theme",
                "income",
                "portfolio_role",
                "behavioral",
                "social_proof",
                "constraint_based",
                "mixed",
                "unclear",
            ],
        },
        "monitorability": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "decomposition_confidence": {
            "type": "number",
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_text": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": [
                            "growth",
                            "margins",
                            "demand",
                            "valuation",
                            "cash_flow",
                            "income",
                            "macro_tailwind",
                            "portfolio_fit",
                            "other",
                        ],
                    },
                    "confidence": {"type": "number"},
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "entity_name": {"type": "string"},
                                "entity_ticker": {"type": ["string", "null"]},
                                "entity_type": {
                                    "type": "string",
                                    "enum": [
                                        "held_company",
                                        "supplier",
                                        "customer",
                                        "competitor",
                                        "benchmark",
                                        "macro_series",
                                        "commodity",
                                        "sector_proxy",
                                        "other",
                                    ],
                                },
                                "relation_type": {
                                    "type": "string",
                                    "enum": [
                                        "depends_on",
                                        "validated_by",
                                        "threatened_by",
                                        "compared_against",
                                    ],
                                },
                                "rationale": {"type": "string"},
                                "confidence": {"type": "number"},
                                "confirmation_required": {"type": "boolean"},
                                "signals": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "signal_type": {
                                                "type": "string",
                                                "enum": [
                                                    "price_move",
                                                    "revenue_growth",
                                                    "earnings_growth",
                                                    "guidance_change",
                                                    "earnings_surprise",
                                                    "transcript_topic",
                                                    "news_topic",
                                                    "insider_transaction",
                                                    "dividend_change",
                                                    "macro_series_change",
                                                ],
                                            },
                                            "signal_label": {"type": "string"},
                                            "signal_config_json": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "metric": {"type": "string"},
                                                    "operator": {"type": "string", "enum": [">=", "<=", ">", "<", "=="]},
                                                    "threshold": {"type": "number"},
                                                    "threshold_pct": {"type": "number"},
                                                    "segment": {"type": "string"},
                                                    "topic": {"type": "string"},
                                                },
                                                "required": [],
                                            },
                                            "rationale": {"type": "string"},
                                            "confidence": {"type": "number"},
                                            "confirmation_required": {"type": "boolean"},
                                        },
                                        "required": [
                                            "signal_type",
                                            "signal_label",
                                            "signal_config_json",
                                            "rationale",
                                            "confidence",
                                            "confirmation_required",
                                        ],
                                    },
                                },
                            },
                            "required": [
                                "entity_name",
                                "entity_ticker",
                                "entity_type",
                                "relation_type",
                                "rationale",
                                "confidence",
                                "confirmation_required",
                                "signals",
                            ],
                        },
                    },
                },
                "required": [
                    "claim_text",
                    "claim_type",
                    "confidence",
                    "entities",
                ],
            },
        },
    },
    "required": [
        "reason_type",
        "monitorability",
        "decomposition_confidence",
        "claims",
    ],
}

DECOMPOSITION_SYSTEM_PROMPT = """You decompose an investor's reason for owning a holding into monitorable claims, entities, and signals.

Return only schema-conforming JSON (no extra keys, no prose). Be concise: rationale fields under 20 words, signal_label 4-8 words.

Rules:
- Extract at least one claim whenever any investment rationale is present (even one sentence). Zero claims only if the text is purely descriptive with zero investment intent.
- When must_remain_true or what_would_change_my_mind are non-empty, extract at least one claim from each. Skip only fields that say "None provided".
- Phrase each claim_text as a falsifiable assertion with an implied pass/fail condition — e.g. "Data center revenue grows >20% YoY", not "Company is growing fast."
- signal_label must be a search-ready phrase that uniquely identifies the signal — include the ticker or company name and the specific metric: e.g. "NVDA data center revenue growth", NOT "revenue growth". Bad: "earnings beat". Good: "AMZN AWS operating income margin".
- REQUIRED: For every quantitative signal (revenue_growth, earnings_growth, dividend_change, etc.) where the user provides a number, populate signal_config_json with {metric, operator, threshold or threshold_pct}. Example: user says "margins stay above 70%" → {"metric": "gross_margin", "operator": ">=", "threshold_pct": 70}.
- REQUIRED: For every news_topic or transcript_topic signal, populate signal_config_json.topic with a 3-6 word search phrase. Example: {"topic": "AMD AI GPU market share"}.
- Empty signal_config_json ({}) is only acceptable for signals where no quantitative threshold and no topic are implied (e.g. earnings_surprise, price_move, insider_transaction).
- Do not invent numeric thresholds unless the user text clearly implies them. Do not hallucinate entities not grounded in the thesis.
- Mark speculative mappings with lower confidence and confirmation_required=true.
- Sparse inputs (vague one-liners, no must_remain_true, no what_would_change_my_mind): set monitorability="low", decomposition_confidence<0.7, confirmation_required=true on all entities.
- Qualitative-only inputs (rationale primarily about CEO/founder trust, brand affinity, following another investor, or portfolio role — no observable metric thresholds or concrete events to watch): cap monitorability at "medium", and use "low" when the only signals you could extract are vague reputation/sentiment topics. Set confirmation_required=true on every claim, entity, and signal. Reason_type must reflect the underlying *motivation*, not just topics mentioned — "behavioral" for trust in people, "social_proof" for following another investor, "portfolio_role" for diversification/allocation. Do not default to "business_performance" just because a company is named.
- Extract as many distinct falsifiable claims as genuinely exist, up to 5. Use at most 3 entities per claim, 3 signals per entity. Do not pad to reach 5 — if the thesis has 2 strong claims, return 2.

Example input:
  Ticker: NVDA | why_own_it: "NVIDIA dominates AI training GPUs. Hyperscalers pour money into data centers and NVDA takes the lion's share."
  must_remain_true: "Data center revenue keeps growing. Gross margins stay above 70%."
  what_would_change_my_mind: "AMD gains real GPU market share. Export restrictions gut China revenue."

Example output:
{
  "reason_type": "business_performance", "monitorability": "high", "decomposition_confidence": 0.9,
  "claims": [
    {
      "claim_text": "NVDA data center revenue grows above 20% YoY on AI GPU demand",
      "claim_type": "growth", "confidence": 0.9,
      "entities": [
        {
          "entity_name": "NVIDIA", "entity_ticker": "NVDA", "entity_type": "held_company",
          "relation_type": "validated_by", "rationale": "Data center is primary revenue driver",
          "confidence": 0.95, "confirmation_required": false,
          "signals": [
            {"signal_type": "revenue_growth", "signal_label": "NVDA data center revenue growth",
             "signal_config_json": {"metric": "data_center_revenue", "operator": ">=", "threshold_pct": 20},
             "rationale": "Core thesis validator", "confidence": 0.95, "confirmation_required": false},
            {"signal_type": "earnings_surprise", "signal_label": "NVDA quarterly earnings beat",
             "signal_config_json": {}, "rationale": "Beats confirm AI demand continues",
             "confidence": 0.8, "confirmation_required": false}
          ]
        }
      ]
    },
    {
      "claim_text": "NVDA gross margin stays above 70%",
      "claim_type": "margins", "confidence": 0.85,
      "entities": [
        {
          "entity_name": "NVIDIA", "entity_ticker": "NVDA", "entity_type": "held_company",
          "relation_type": "validated_by", "rationale": "Margin erosion breaks thesis",
          "confidence": 0.85, "confirmation_required": false,
          "signals": [
            {"signal_type": "earnings_growth", "signal_label": "NVDA gross margin trend",
             "signal_config_json": {"metric": "gross_margin", "operator": ">=", "threshold_pct": 70},
             "rationale": "70% floor implied by thesis condition", "confidence": 0.85, "confirmation_required": false}
          ]
        }
      ]
    },
    {
      "claim_text": "AMD does not take meaningful AI GPU market share from NVDA",
      "claim_type": "demand", "confidence": 0.75,
      "entities": [
        {
          "entity_name": "AMD", "entity_ticker": "AMD", "entity_type": "competitor",
          "relation_type": "threatened_by", "rationale": "AMD GPU wins would erode NVDA moat",
          "confidence": 0.75, "confirmation_required": true,
          "signals": [
            {"signal_type": "news_topic", "signal_label": "AMD AI GPU market share gains",
             "signal_config_json": {"topic": "AMD AI GPU competition NVDA"},
             "rationale": "AMD customer wins signal thesis risk", "confidence": 0.7, "confirmation_required": true}
          ]
        }
      ]
    }
  ]
}
"""

DECOMPOSITION_USER_PROMPT = """Holding
- Ticker: {ticker}
- Name: {name}

User reason
- Why I own it: {why_own_it}
- What must remain true: {must_remain_true}
- What would change my mind: {what_would_change_my_mind}
"""


def build_decomposition_prompt(payload: dict) -> str:
    return DECOMPOSITION_USER_PROMPT.format(
        ticker=payload["ticker"],
        name=payload["name"],
        why_own_it=payload["why_own_it"],
        must_remain_true=payload.get("must_remain_true") or "None provided",
        what_would_change_my_mind=payload.get("what_would_change_my_mind") or "None provided",
    )
