DECOMPOSITION_PROMPT_VERSION = "v2"

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
                                                    "operator": {"type": "string"},
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

DECOMPOSITION_PROMPT = """You are a thesis decomposition assistant for a retail investing app.

You must turn the user's investment reasoning into a structured decomposition that the app can later review and monitor.

Holding:
- Ticker: {ticker}
- Name: {name}

User thesis:
- Why I own it: {why_own_it}
- What must remain true: {must_remain_true}
- What would change my mind: {what_would_change_my_mind}

Return valid JSON with this exact structure:
{{
  "reason_type": "business_performance|valuation|macro_theme|income|portfolio_role|behavioral|social_proof|constraint_based|mixed|unclear",
  "monitorability": "high|medium|low",
  "decomposition_confidence": 0.0,
  "claims": [
    {{
      "claim_text": "The investor belief in plain language",
      "claim_type": "growth|margins|demand|valuation|cash_flow|income|macro_tailwind|portfolio_fit|other",
      "confidence": 0.0,
      "entities": [
        {{
          "entity_name": "Entity name",
          "entity_ticker": "OPTIONAL_TICKER",
          "entity_type": "held_company|supplier|customer|competitor|benchmark|macro_series|commodity|sector_proxy|other",
          "relation_type": "depends_on|validated_by|threatened_by|compared_against",
          "rationale": "Why this entity matters",
          "confidence": 0.0,
          "confirmation_required": true,
          "signals": [
            {{
              "signal_type": "price_move|revenue_growth|earnings_growth|guidance_change|earnings_surprise|transcript_topic|news_topic|insider_transaction|dividend_change|macro_series_change",
              "signal_label": "Short human-readable label",
              "signal_config_json": {{}},
              "rationale": "Why this signal matters",
              "confidence": 0.0,
              "confirmation_required": true
            }}
          ]
        }}
      ]
    }}
  ]
}}

Rules:
- Use the output schema provided by the API/tool definition and return only schema-conforming content.
- Do not create monitorable signals from descriptive facts with no investment intent.
- Do not invent numeric thresholds unless the user text clearly implies them.
- Do not assume proxy entities unless there is a plausible causal relationship.
- Mark speculative mappings with lower confidence and confirmation_required=true.
- It is acceptable to return zero signals or zero entities if the thesis is too vague.
"""


def build_decomposition_prompt(payload: dict) -> str:
    return DECOMPOSITION_PROMPT.format(
        ticker=payload["ticker"],
        name=payload["name"],
        why_own_it=payload["why_own_it"],
        must_remain_true=payload.get("must_remain_true") or "None provided",
        what_would_change_my_mind=payload.get("what_would_change_my_mind") or "None provided",
    )
